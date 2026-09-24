"""JeV typé local DeBERTa. Aucun réseau ni poids à l'import.

Le bundle tiers est archivé à native/macos/typed_decisions (Apache-2.0,
révision 19bf9a6). La fenêtre 512 tokens impose plusieurs passes pour les
19 questions MOTHER ; leurs distributions restent celles du modèle.
"""
from __future__ import annotations

import asyncio
import logging
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping

from src.ears.jev_reflexe import (
    JevEvaluation, JevThresholds, QUESTIONS, _signals, _validated_answers,
)

logger = logging.getLogger(__name__)


def local_questions() -> dict:
    from src.i18n import questions_jev

    return questions_jev()


def to_model_question(question: Mapping[str, Any]) -> dict:
    kind = question["type"]
    result = {"type": kind, "instructions": question["instructions"]}
    if kind == "noul":
        criteria = question.get("criteria") or {}
        result["instructions"] += (" Oui: " + str(criteria.get("true", ""))
                                   + " Non: " + str(criteria.get("false", "")))
    elif kind == "score":
        result["options"] = [str(value) for value in question["criteria"]]
    else:
        # Les identifiants stables sont le contrat; les critères sont du texte
        # explicatif à inclure dans les options, sans changer le mapping.
        result["options"] = [f"{key}: {value}" for key, value in question["criteria"].items()]
    return result


def map_answer(question: Mapping[str, Any], raw: Mapping[str, Any]) -> dict:
    kind = question["type"]
    if kind == "noul":
        return {"type": kind, "noul": raw["noul"]}
    if kind == "score":
        keys = [str(i) for i in range(len(question["criteria"]))]
        labels = [str(value) for value in question["criteria"]]
    else:
        keys = list(question["criteria"])
        labels = [f"{key}: {question['criteria'][key]}" for key in keys]
    probabilities = raw["probabilities"]
    if set(probabilities) != set(labels):
        raise ValueError("Probabilités JeV incomplètes")
    values = list(probabilities.values())
    if any(not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or value > 1
           for value in values) or abs(sum(values) - 1.0) > 0.01:
        raise ValueError("Distribution JeV invalide")
    mapped = {key: probabilities[label] for key, label in zip(keys, labels)}
    if kind == "choice":
        choice = raw["choice"]
        if choice not in labels:
            raise ValueError("Choix JeV inconnu")
        return {"type": kind, "choice": keys[labels.index(choice)],
                "confidence": raw["confidence"], "probabilities": mapped}
    return {"type": kind, "score": raw["score"],
            "confidence": raw["confidence"], "probabilities": mapped}


class JevLocal:
    def __init__(self, *, model_dir: Path | None = None, loader=None,
                 thresholds: JevThresholds | None = None):
        from native.macos.profile import model_path

        self.model_dir = Path(model_dir) if model_dir else model_path("jev")
        self.loader = loader
        self.thresholds = thresholds or JevThresholds.from_env()
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-local")
        self._running = None
        self._loading = None

    def _load(self):
        if self.loader is not None:
            return self.loader(str(self.model_dir))
        from dev.scripts.models_macos import status
        from native.macos.profile import paths

        if status("jev", paths()["models"])["status"] != "PASS":
            raise FileNotFoundError("Snapshot JeV incomplet ; lancer models_macos.py status --family jev")
        from native.macos.typed_decisions.open_jev import OpenJev

        return OpenJev.from_pretrained(str(self.model_dir), device="mps")

    async def prechauffer(self) -> bool:
        if self._model is not None:
            return True
        if self._loading is None:
            loop = asyncio.get_running_loop()
            self._loading = loop.run_in_executor(self._executor, self._load)
        try:
            self._model = await asyncio.shield(self._loading)
            return True
        except Exception:
            logger.exception("JeV local indisponible")
            self._loading = None
            return False

    def _decide(self, transcription: str, questions: dict, context=None) -> dict:
        model = self._model
        entries = [(key, q, to_model_question(q)) for key, q in questions.items()]
        # Le collator du modèle lève si une séquence dépasse 512. Former des
        # paquets exacts avec son propre tokenizer, jamais tronquer une question.
        groups: list[list] = []
        current: list = []
        state = json.dumps({"transcription": transcription, "context": context or {}}, ensure_ascii=False)
        for entry in entries:
            trial = current + [entry]
            try:
                model.collator.encode_one(state, [model._question(i, e[2]) for i, e in enumerate(trial)])
            except ValueError:
                if not current:
                    raise ValueError(f"Question JeV hors fenêtre : {entry[0]}")
                groups.append(current)
                current = [entry]
                model.collator.encode_one(state, [model._question(0, entry[2])])
            else:
                current = trial
        if current:
            groups.append(current)
        answers = {}
        for group in groups:
            result = model.decide(state, [item[2] for item in group])
            if len(result) != len(group):
                raise ValueError("JeV local a répondu à un nombre de questions incorrect")
            for (key, question, _), raw in zip(group, result):
                answers[key] = map_answer(question, raw)
        return answers

    async def evaluate(self, transcription: str, *, context=None) -> JevEvaluation | None:
        if self._model is None or (self._running is not None and not self._running.done()):
            return None
        questions = local_questions()
        if set(questions) != set(QUESTIONS):
            logger.error("JeV local : les identifiants de questions divergent")
            return None
        loop = asyncio.get_running_loop()
        # Un timeout n'interrompt pas Metal : conserver le future et refuser
        # d'empiler un second tour tant que le premier calcule encore.
        self._running = loop.run_in_executor(self._executor, self._decide, transcription, questions, context)
        try:
            answers = await asyncio.wait_for(asyncio.shield(self._running),
                                             timeout=self.thresholds.timeout_ms / 1000)
            validated = _validated_answers({"answers": answers})
            if validated is None:
                raise ValueError("réponses typées incomplètes")
            return JevEvaluation(answers=validated, signals=_signals(validated, self.thresholds))
        except Exception:
            logger.warning("JeV local indisponible pour ce tour", exc_info=False)
            return None

    async def maintenir(self, intervalle_s: float = 40.0) -> None:
        while True:
            await asyncio.sleep(intervalle_s)
            if self._model is None:
                await self.prechauffer()

    async def aclose(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def construire_jev():
    import os

    if os.getenv("JEV_BACKEND") == "local-deberta":
        from native.macos.profile import require_platform

        require_platform()
        return JevLocal()
    from src.ears.jev_reflexe import JevReflexe

    return JevReflexe()
