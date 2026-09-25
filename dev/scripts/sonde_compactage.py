"""Sonde en conteneur : 40 tours, Granite puis MiniMax, mémoire et TTFT."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.brain.compactage import Compacteur, budget_pour_modele, lire_fenetre_locale
from src.brain.contexte import estimer_jetons, projeter_messages, projeter_kw
from src.i18n import system_prompt


async def premier_mot(client, url, payload, headers=None):
    debut = time.perf_counter()
    texte = ""
    ttft = None
    async with client.stream("POST", url, json={**payload, "stream": True}, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
            morceau = delta.get("content") or ""
            if morceau:
                ttft = ttft or round((time.perf_counter() - debut) * 1000)
                texte += morceau
    return ttft, texte


async def main():
    complet = "--full" in sys.argv
    local = os.getenv("LLAMA_SERVER_HOST", "http://localhost:8080").rstrip("/")
    class Modele:
        api_endpoint = local + "/v1/chat/completions"
    fenetre = await lire_fenetre_locale(Modele())
    modele_local = Modele()
    modele_local.n_ctx = fenetre
    budget_reflexe = budget_pour_modele(modele_local, canal="reflex")
    systeme_local = system_prompt()
    compact = Compacteur(budget_reflexe)
    url = local + "/v1/chat/completions"
    async with httpx.AsyncClient(timeout=60.0) as client:
        mesures = {}
        for i in range(1, 41):
            question = ("Je m'appelle Thomas et ma soutenance est à 14 h." if i == 2
                        else ("Bonjour." if i == 1 else "Merci." if i == 3
                              else f"Échange {i} : parle brièvement du suivi du projet."))
            if i == 3:
                message_reflexe = [{"role": "system", "content": systeme_local},
                                   *compact.messages(), {"role": "user", "content": "Merci."}]
                payload = {"model": os.getenv("BRAIN_MODEL_LOCAL", "local"),
                           "messages": projeter_kw({"history": compact.messages(), "messages": message_reflexe}, "reflex", budget_reflexe)["messages"],
                           "max_tokens": 32, "chat_template_kwargs": {"enable_thinking": False}}
                mesures["ttft_reflexe_3_ms"], _ = await premier_mot(client, url, payload)
            if i == 40:
                message_reflexe = [{"role": "system", "content": systeme_local},
                                   *compact.messages(), {"role": "user", "content": "Merci."}]
                reflex = projeter_kw({"history": compact.messages(), "messages": message_reflexe}, "reflex", budget_reflexe)["messages"]
                payload = {"model": os.getenv("BRAIN_MODEL_LOCAL", "local"),
                           "messages": reflex,
                           "max_tokens": 32, "chat_template_kwargs": {"enable_thinking": False}}
                mesures["ttft_reflexe_40_ms"], _ = await premier_mot(client, url, payload)
                mesures["historique_reflexe_jetons_estimes"] = estimer_jetons(payload["messages"][1:])
                mesures["prompt_reflexe_jetons_estimes"] = estimer_jetons(payload["messages"])
                deep = projeter_messages(compact.messages(), "deep")
                distant_url = os.environ["BRAIN_API_ENDPOINT"]
                distant_payload = {"model": os.environ["BRAIN_MODEL"],
                                   "messages": [{"role": "system", "content": "Réponds brièvement et factuellement en français."},
                                                *deep,
                                                {"role": "user", "content": "Quel est mon prénom et à quelle heure est ma soutenance ?"}],
                                   "max_tokens": 100}
                _, reponse = await premier_mot(client, distant_url, distant_payload,
                                                {"Authorization": "Bearer " + os.environ["BRAIN_API_KEY"]})
                mesures["reponse_40"] = reponse.strip()
                mesures["fait_restitue"] = "Thomas" in reponse and "14" in reponse
                mesures["resume_chars"] = len(compact.resume)
                mesures["resume"] = compact.resume
                break
            reponse = f"Réponse parlée {i} : nous suivons le projet."
            if complet:
                reflex = i in (1, 3)
                historique = projeter_messages(compact.messages(), "reflex" if reflex else "deep", budget_reflexe if reflex else None)
                if reflex:
                    endpoint = url
                    headers = None
                    modele = os.getenv("BRAIN_MODEL_LOCAL", "local")
                else:
                    endpoint = os.environ["BRAIN_API_ENDPOINT"]
                    headers = {"Authorization": "Bearer " + os.environ["BRAIN_API_KEY"]}
                    modele = os.environ["BRAIN_MODEL"]
                requete = {
                    "model": modele,
                    "messages": [{"role": "system", "content": systeme_local if reflex else "Réponds en une phrase brève en français."},
                                 *historique, {"role": "user", "content": question}],
                    "max_tokens": 60,
                }
                if reflex:
                    requete["chat_template_kwargs"] = {"enable_thinking": False}
                _, reponse = await premier_mot(client, endpoint, requete, headers)
            compact.retenir(question, reponse)
            compact.planifier()
            await compact.attendre()
    mesures["delta_ttft_ms"] = mesures["ttft_reflexe_40_ms"] - mesures["ttft_reflexe_3_ms"]
    mesures["tours_generes"] = 40 if complet else 1
    print(json.dumps(mesures, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
