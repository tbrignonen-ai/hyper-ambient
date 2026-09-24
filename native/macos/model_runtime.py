"""Résidents MLX du processus host-agent (ASR et TTS), un calcul à la fois.

Le serveur texte et JeV ont des processus/moteurs distincts ; leurs pics réels
restent à mesurer sur Mac. Une annulation abandonne la réponse, mais la tâche
Metal en cours finit avant la suivante, sans chevauchement caché.

MOTHER_MAC_MLX_RESIDENTS vaut 1 (défaut : une famille résidente, recharge à
chaque changement ASR↔TTS) ou 2 (ASR et TTS gardés, ~5,4 Go de poids). Le
choix se tranche sur Mac par la pression mémoire, pas ici.

La file est bornée à un tour en attente derrière le calcul en cours : après une
interruption, la transcription suivante passe derrière la synthèse abandonnée
au lieu d'être jetée ; au-delà, le tour est rejeté explicitement.
"""
from __future__ import annotations

import asyncio
import gc
import os
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

MAX_EN_VOL = 2  # un calcul actif + un tour en attente


def _residents_env() -> int:
    try:
        value = int(os.getenv("MOTHER_MAC_MLX_RESIDENTS", "1"))
    except ValueError:
        return 1
    return min(max(value, 1), 2)


class ModelRuntime:
    def __init__(self, residents: int | None = None):
        self.residents = residents if residents is not None else _residents_env()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mother-mlx")
        self._guard = Lock()
        self._inflight = 0
        self._models: OrderedDict = OrderedDict()  # famille -> (modèle, éviction)
        self._model = None

    def _clear_metal(self):
        gc.collect()
        try:
            import mlx.core as mx

            mx.clear_cache()
        except ImportError:
            pass

    def _run(self, family, loader, action, on_evict):
        if family in self._models:
            self._models.move_to_end(family)
        else:
            evicted = False
            while len(self._models) >= self.residents:
                _, (_, evict) = self._models.popitem(last=False)
                if evict:
                    evict()
                evicted = True
            if evicted:
                self._clear_metal()
            self._models[family] = (loader(), on_evict)
        model = self._models[family][0]
        self._model = model
        return action(model)

    async def run(self, family, loader, action=lambda model: model, on_evict=None):
        with self._guard:
            if self._inflight >= MAX_EN_VOL:
                raise RuntimeError("Inférence MLX : file pleine ; tour rejeté")
            self._inflight += 1
        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(self._executor, self._run, family, loader, action, on_evict)
        except Exception:
            with self._guard:
                self._inflight -= 1
            raise

        def done(_):
            with self._guard:
                self._inflight -= 1

        future.add_done_callback(done)
        return await asyncio.shield(future)

    async def close(self):
        if self._inflight:
            raise RuntimeError("Inférence MLX encore active : arrêt différé")
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._models.clear()
        self._model = None


runtime = ModelRuntime()
