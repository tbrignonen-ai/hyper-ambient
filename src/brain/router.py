"""
BRAIN: the two-channel router.

hyper-ambient is the room's authority, not its quickest voice. It is allowed to take
its time — what it is not allowed to do is leave silence. So the realtime
budget applies to the **acknowledgment**, not to the answer:

    user stops speaking
      -> classify locally           (~90 ms, prefix-cached, grammar-constrained)
      -> REFLEX  : local answers, streams straight to MOUTH
      -> ESCALATE: local speaks a filler NOW, remote answers behind it

The filler is what buys the right to be intelligent. Without it, escalation is
just latency; with it, escalation is deliberation.

Why the classifier is binary
----------------------------
A three-way SIMPLE/FAST/DEEP split was measured and rejected: asked to grade
"il est 14 h 40, réunion dans 20 min, durée 40 min, à quelle heure je finis ?",
the 2 B classifier answered FAST — routing to local the one question every
local model gets wrong (0/5 across five models, see STACK.md). A small model
cannot grade a difficulty it cannot itself handle.

So the only judgement asked of it is one it can actually make: "is this
small talk?" Everything else escalates. Ambiguity escalates. The cost of a
wrong escalation is a few hundred milliseconds; the cost of a wrong local
answer is hyper-ambient being confidently wrong, which is the one thing it must
never be.
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from src.brain.contexte import fenetre_classifieur, projeter_kw
from src.brain.mandat import NOMS_HARNAIS

logger = logging.getLogger(__name__)

# Grammar-constrained: the model cannot emit anything but these two tokens.
CLASSIFY_GRAMMAR = 'root ::= "REFLEXE" | "ESCALADE"'

CLASSIFY_PREFIX = """Tu tries des demandes adressées à hyper-ambient, une voix ambiante locale.

REFLEXE = salutation, politesse, remerciement, acquiescement, ou ordre direct
          sans aucun raisonnement (répète, plus fort, arrête, annule).
ESCALADE = tout le reste. Toute question de connaissance, de calcul, de
          comparaison, d'analyse, toute demande nécessitant un outil, et tout
          cas douteux.

Dans le doute, réponds ESCALADE.

Demande: Bonjour hyper-ambient.
Classe: REFLEXE
Demande: Merci, c'est noté.
Classe: REFLEXE
Demande: Répète plus fort.
Classe: REFLEXE
Demande: Quelle est la capitale de la Norvège ?
Classe: ESCALADE
Demande: Il est 14 h 40, ma réunion dure quarante minutes et commence dans vingt minutes, à quelle heure je finis ?
Classe: ESCALADE
Demande: Quel temps fait-il à Paris demain ?
Classe: ESCALADE
Demande: """

CLASSIFY_SUFFIX = "\nClasse:"

# Le réflexe local n'a que les formules : au-delà de quatre mots, c'est une
# conversation, et le 3B y répondait « Je suis là. » ou « Oui. » (séance du
# 24/09). Le distant converse ; le local salue.
MAX_MOTS_REFLEXE = 4

# Canned, not generated. Generating a filler would cost a round-trip of the
# very latency the filler exists to hide, and would risk a filler that does not
# fit. These are short, level, and in hyper-ambient's register: never apologetic,
# never chatty.
FILLERS = [
    "Je regarde.",
    "Une seconde.",
    "Je vérifie.",
]

# One filler covers about a second of audio. The remote channel was measured at
# 612 ms median on short prompts but 13.8 s on a hard one — so a single filler
# leaves ten seconds of silence, which reads as a crash, not as deliberation.
# A second line keeps presence without turning into chatter.
HOLDING = [
    "C'est un peu plus long que prévu, je reste dessus.",
]



# Un enonce plus court que ceci est probablement anaphorique : « vas-y », « oui »,
# « et alors ? » ne veulent rien dire seuls. Au-dela, l'enonce porte sa propre
# difficulte et le tour precedent n'est plus qu'un parasite.
LONGUEUR_ANAPHORIQUE = 25


def nomme_un_harnais(prompt: str) -> bool:
    return bool(re.search(r"\b" + NOMS_HARNAIS + r"\b", prompt or "", re.IGNORECASE))


def sans_outils(kw: Dict[str, Any]) -> Dict[str, Any]:
    """Retire `tools` / `tool_choice` d'un appel.

    Un tour REFLEXE n'a pas d'outils. Les laisser dans la charge utile
    transforme un « Bonjour. » en tempete d'appels (mesure 17 sept, Luciole 8B
    classé REFLEXE, 30+ web_search/ask_codex, aucun tour BRAIN final).
    """
    propre = dict(kw)
    propre.pop("tools", None)
    propre.pop("tool_choice", None)
    return propre


def est_une_suite_d_outil(messages: Optional[List[Dict[str, Any]]]) -> bool:
    """Cet appel prolonge-t-il un tour de parole deja annonce ?

    `run_tool_loop` rappelle `query_streaming` apres chaque outil, avec
    l'historique enrichi du resultat. Le role `tool` n'apparait qu'a ce
    moment-la : un tour neuf n'en porte jamais. C'est donc le signe le plus sur,
    et il ne demande aucun etat partage entre la boucle et le routeur — ce qui
    compte, puisque la boucle est volontairement neutre sur le harnais.
    """
    return any((message or {}).get("role") == "tool" for message in (messages or []))


def doit_joindre_contexte(prompt: str) -> bool:
    """Le tour precedent doit-il peser sur la classification de celui-ci ?

    Le contexte etait joint systematiquement, et cela deregle le jugement de
    difficulte : mesure en conditions reelles, la question horaire escalade
    correctement apres un tour vide, mais se fait classer REFLEXE des qu'une
    politesse la precede — et recoit alors une reponse locale fausse. Un enonce
    qui se suffit a lui-meme doit donc se juger seul.
    """
    return 0 < len(prompt.strip()) < LONGUEUR_ANAPHORIQUE

class RouterBrain:
    """
    Local reflex channel + remote deliberation channel.

    Exposes the same surface as OpenAICompatBrain, so MOUTH and the core loop
    never learn which channel answered.
    """

    name = "router"

    def __init__(
        self,
        reflex,                    # OpenAICompatBrain — local llama.cpp
        deep,                      # OpenAICompatBrain — remote
        classify_host: Optional[str] = None,
        enable_filler: bool = True,
        deep_timeout_ms: Optional[int] = None,
        reflex_answers: Optional[bool] = None,
    ):
        self.reflex = reflex
        self.deep = deep
        # False : le reflexe local trie mais ne repond plus. Mesure du 15 sept,
        # MiniCPM5-2B recopiait les exemples du prompt et se trompait sans eux.
        self.reflex_answers = (
            reflex_answers if reflex_answers is not None
            else os.getenv("BRAIN_REFLEX_ANSWERS", "1") != "0"
        )
        self.classify_host = (classify_host or os.getenv(
            "LLAMA_SERVER_HOST", "http://localhost:8080")).rstrip("/")
        self.enable_filler = enable_filler
        # Generous on purpose: hyper-ambient may deliberate. This is the point at
        # which we give up on the remote entirely, not a latency target.
        self.deep_timeout_ms = deep_timeout_ms or int(
            os.getenv("BRAIN_DEEP_TIMEOUT_MS", "20000"))
        # Silence tolerated after the last spoken word before another holding
        # line goes out. ~1 s of filler audio plus this is the perceived gap.
        # 6000, pas 2500 : le commentaire de HOLDING ci-dessus dimensionne la
        # relance sur le tour dur mesure a 13,8 s, pas sur les tours a 4-5 s. A
        # 2500, un tour de 5,4 s recevait mecaniquement une seconde ligne alors
        # que l'amorce couvrait deja ~1 s — entendu comme du remplissage, pas
        # comme de la presence. A 6000, un tour de 5,4 s ne declenche plus rien,
        # un tour de 13,8 s recoit toujours ses deux lignes (6 s, 12 s).
        self.holding_after_ms = int(os.getenv("BRAIN_HOLDING_AFTER_MS", "6000"))
        # Sous ce délai, le distant répond avant qu'une phrase d'attente ait un
        # sens : on se tait (notes voix/UX, 24/09).
        self.progression_apres_ms = int(os.getenv("BRAIN_PROGRESSION_APRES_MS", "1500"))
        self._filler_i = 0
        self._client = None
        self.stats = {"reflex": 0, "escalate": 0, "deep_failed": 0}

    @property
    def api_endpoint(self) -> str:
        return f"reflex={self.reflex.api_endpoint} deep={self.deep.api_endpoint}"

    async def initialize(self):
        import httpx

        self._client = httpx.AsyncClient(timeout=10.0)
        await self.reflex.initialize()
        await self.deep.initialize()
        logger.info(f"router: reflex={self.reflex.name} deep={self.deep.name}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        await self.reflex.close()
        await self.deep.close()

    async def health(self):
        r = await self.reflex.health()
        d = await self.deep.health()
        return {
            "ok": r["ok"],  # the reflex channel is the one hyper-ambient cannot lose
            "detail": f"reflex {r['detail']}, deep {d['detail']}",
            "latency_ms": r["latency_ms"],
        }

    # -- classification ----------------------------------------------------

    async def classify(
        self, prompt: str, contexte: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Decide REFLEXE vs ESCALADE on the local model.

        Uses /completion (not /v1/chat/completions) because it takes a GBNF
        grammar and a stable prefix, so llama-server's prompt cache covers
        everything but the transcript — measured 335 ms cold, ~90 ms warm.
        """
        # Nommer un harnais est par definition une demande d'action, jamais un
        # reflexe ; et la voie reflexe est la seule qui n'a pas d'outils, donc
        # la seule ou la demande ne peut pas aboutir.
        if nomme_un_harnais(prompt):
            return {"route": "escalate", "latency_ms": 0.0, "verdict": "HARNAIS"}

        if len(prompt.split()) > MAX_MOTS_REFLEXE:
            return {"route": "escalate", "latency_ms": 0.0, "verdict": "CONVERSATION"}

        if self._client is None:
            return {"route": "escalate", "latency_ms": 0.0, "reason": "no client"}

        # « Oui, vas-y » n'est un reflexe que si rien ne precede. Apres une
        # question de connaissance, c'est la SUITE de cette question, et la
        # router en local fait repondre une politesse creuse a la place du
        # sujet. Le dernier tour suffit a lever l'ambiguite ; le prefixe reste
        # stable, donc le cache de prompt de llama-server tient toujours.
        # Fenêtre adaptative : énoncé seul si > 25 car. ; sinon + tour
        # précédent. Troncature à 160 (mesure déjà inscrite), pas 80.
        fenetre = fenetre_classifieur(prompt, contexte)
        body = {
            "prompt": CLASSIFY_PREFIX + fenetre + CLASSIFY_SUFFIX,
            "grammar": CLASSIFY_GRAMMAR,
            "n_predict": 4,
            "temperature": 0,
            "cache_prompt": True,
        }
        t0 = time.perf_counter()
        try:
            r = await self._client.post(f"{self.classify_host}/completion", json=body)
            elapsed = (time.perf_counter() - t0) * 1000
            verdict = (r.json().get("content") or "").strip()
            route = "reflex" if verdict == "REFLEXE" else "escalate"
            return {"route": route, "latency_ms": elapsed, "verdict": verdict}
        except Exception as e:
            # Failing open means escalating — never silently answering locally.
            logger.warning(f"classify failed ({e}); escalating")
            return {
                "route": "escalate",
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "reason": str(e)[:80],
            }

    def _next_filler(self) -> str:
        f = FILLERS[self._filler_i % len(FILLERS)]
        self._filler_i += 1
        return f

    # -- inference ---------------------------------------------------------

    async def query_streaming(
        self, prompt: str, system: Optional[str] = None, **kw
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Yield deltas. Chunks carry `channel` ("reflex" | "filler" | "deep") so
        callers can log or style them; MOUTH just speaks the text.
        """
        decision = await self.classify(prompt, kw.get("history"))
        route = decision["route"]
        if route == "reflex" and not self.reflex_answers:
            route = "escalate"
        logger.info(f"router: {route} ({decision['latency_ms']:.0f} ms)")

        if route == "reflex":
            self.stats["reflex"] += 1
            async for chunk in self.reflex.query_streaming(
                prompt, system=system, **projeter_kw(sans_outils(kw), "reflex")
            ):
                chunk["channel"] = "reflex"
                yield chunk
            return

        self.stats["escalate"] += 1

        # Speak first, think second. The filler goes out before the remote
        # request is even awaited, so MOUTH starts synthesising immediately.
        #
        # Sauf quand ce tour prolonge un appel d'outil : l'attente a deja ete
        # annoncee AVANT l'outil (« Je demande a Codex... »), et une amorce
        # ici tomberait APRES l'attente qu'elle est censee couvrir. Mesure du
        # 13/09 sur la chaine reelle : trois phrases d'attente pour une seule
        # question, dont la derniere a 18,1 s sur un outil rendu a 17,8 s.
        # Une seule annonce d'attente par tour harnais : l'accusé du mandat.
        # L'amorce ici dirait la même chose. est_une_suite_d_outil ne couvre
        # pas ce cas : les trois phrases naissent au premier query_streaming,
        # avant tout message role=tool — le garde du 13/09 ne les voit pas.
        # Notes voix/UX du 24/09 : la phrase d'attente n'est plus dite d'office.
        # Elle part seulement si le distant n'a encore rien produit après
        # `progression_apres_ms` — un état réel, pas un tic avant chaque réponse.
        annoncer = (
            self.enable_filler
            and not est_une_suite_d_outil(kw.get("messages"))
            and not nomme_un_harnais(prompt)
        )

        immediate = annoncer and self.progression_apres_ms <= 0
        if immediate:
            # BRAIN_PROGRESSION_APRES_MS=0 : l'ancien comportement, amorce dite
            # avant même d'attendre le distant.
            yield {
                "delta": self._next_filler(),
                "stop_reason": None,
                "ttft_ms": decision["latency_ms"],
                "channel": "filler",
                "flush": True,   # MOUTH: synthesise this now, do not buffer
            }

        emitted = False
        try:
            stream = self.deep.query_streaming(
                prompt, system=system, **projeter_kw(kw, "deep")
            )
            holding = 0
            async for chunk in _with_holding(
                stream, self.deep_timeout_ms, self.holding_after_ms,
                (len(HOLDING) if immediate else 1 + len(HOLDING)) if annoncer else 0,
                premier_ms=None if immediate else self.progression_apres_ms,
            ):
                if chunk.get("_holding"):
                    premiere = holding == 0 and not immediate
                    yield {
                        "delta": self._next_filler() if premiere
                        else HOLDING[max(0, holding - (0 if immediate else 1)) % len(HOLDING)],
                        "stop_reason": None,
                        "ttft_ms": None,
                        "channel": "filler" if premiere else "holding",
                        "flush": True,
                    }
                    holding += 1
                    continue
                if chunk["stop_reason"] == "error":
                    raise RuntimeError(chunk.get("error", "deep channel error"))
                if chunk["delta"]:
                    emitted = True
                chunk["channel"] = "deep"
                yield chunk
            return
        except Exception as e:
            self.stats["deep_failed"] += 1
            logger.warning(f"deep channel failed ({str(e)[:100]}) — falling back to reflex")
            if emitted:
                # Already speaking the remote's answer; cannot restart cleanly.
                yield {"delta": "", "stop_reason": "error", "ttft_ms": None,
                       "channel": "deep", "error": str(e)[:200]}
                return

        # Nothing spoken past the filler — the local channel can still answer,
        # and "Un instant." followed by a local answer stays coherent.
        async for chunk in self.reflex.query_streaming(
            prompt, system=system, **projeter_kw(sans_outils(kw), "reflex")
        ):
            chunk["channel"] = "reflex"
            yield chunk

    async def query(self, prompt: str, system: Optional[str] = None, **kw):
        """Non-streaming convenience — no filler, since nothing is spoken."""
        decision = await self.classify(prompt)
        target = self.reflex if decision["route"] == "reflex" else self.deep
        canal = "reflex" if target is self.reflex else "deep"
        cible_kw = kw if target is self.deep else sans_outils(kw)
        result = await target.query(
            prompt, system=system, **projeter_kw(cible_kw, canal)
        )
        result["channel"] = decision["route"]
        if result["stop_reason"] == "error" and target is self.deep:
            self.stats["deep_failed"] += 1
            result = await self.reflex.query(
                prompt, system=system, **projeter_kw(sans_outils(kw), "reflex")
            )
            result["channel"] = "reflex"
        return result


async def _with_holding(
    agen: AsyncIterator, timeout_ms: int, holding_after_ms: int, max_holding: int,
    premier_ms: Optional[int] = None,
):
    """
    Forward an async generator, emitting a `_holding` marker whenever it stays
    silent for `holding_after_ms`, and giving up entirely at `timeout_ms`.

    Two separate clocks on purpose: the holding clock resets on every chunk
    (silence since the last word), the deadline clock does not (total patience).
    """
    deadline = time.perf_counter() + timeout_ms / 1000.0
    holdings = 0
    a_parle = False
    pending: Optional[asyncio.Future] = None

    try:
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError(f"deep channel silent for {timeout_ms} ms")

            if pending is None:
                pending = asyncio.ensure_future(agen.__anext__())

            attente_ms = holding_after_ms
            if holdings == 0 and premier_ms is not None and not a_parle:
                attente_ms = premier_ms
            step = attente_ms / 1000.0 if holdings < max_holding else remaining
            # asyncio.wait — NOT wait_for. wait_for CANCELS its awaitable on
            # timeout, and cancelling __anext__() tears down the generator and
            # its HTTP stream: the holding line would kill the very channel it
            # exists to cover. asyncio.wait leaves the task running so the next
            # iteration can keep waiting on the same one.
            done, _ = await asyncio.wait({pending}, timeout=min(step, remaining))

            if not done:
                if holdings < max_holding:
                    holdings += 1
                    yield {"_holding": True}
                    continue
                raise TimeoutError(f"deep channel silent for {timeout_ms} ms")

            try:
                item = pending.result()
            except StopAsyncIteration:
                pending = None
                return
            pending = None
            # Une fois qu'il parle, plus aucune relance : « Encore quelques
            # instants » au milieu d'une réponse est du bruit (24/09).
            if premier_ms is not None:
                a_parle = True
                holdings = max_holding
            else:
                holdings = 0  # it spoke; reset the silence clock
            yield item
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration):
                pass
            except Exception:
                pass
        try:
            await agen.aclose()
        except RuntimeError:
            # aclose() refuse un generateur encore dans __anext__ ; la tache
            # ci-dessus a deja ete annulee, le flux HTTP ne doit plus rester ouvert.
            pass
