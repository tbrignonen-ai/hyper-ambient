"""Un seul résident MLX dans le processus host-agent (ASR ou TTS).

Le serveur texte et JeV ont des processus/moteurs distincts ; leurs pics réels
restent à mesurer sur Mac. Une annulation abandonne la réponse, mais la tâche
Metal en cours finit avant la prochaine famille, sans chevauchement caché.
"""
from __future__ import annotations

import asyncio
import gc
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class ModelRuntime:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mother-mlx")
        self._guard = Lock()
        self._pending = False
        self._family = None
        self._model = None
        self._evict = None

    def _run(self, family, loader, action, on_evict):
        if self._family != family:
            if self._evict:
                self._evict()
            self._model = None
            self._family = None
            self._evict = None
            gc.collect()
            try:
                import mlx.core as mx

                mx.clear_cache()
            except ImportError:
                pass
            self._model = loader()
            self._family = family
            self._evict = on_evict
        return action(self._model)

    async def run(self, family, loader, action=lambda model: model, on_evict=None):
        with self._guard:
            if self._pending:
                raise RuntimeError("Inférence MLX déjà en cours ; tour rejeté sans file cachée")
            self._pending = True
        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(self._executor, self._run, family, loader, action, on_evict)
        except Exception:
            with self._guard:
                self._pending = False
            raise

        def done(_):
            with self._guard:
                self._pending = False

        future.add_done_callback(done)
        return await asyncio.shield(future)

    async def close(self):
        if self._pending:
            raise RuntimeError("Inférence MLX encore active : arrêt différé")
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._model = None
        self._family = None
        self._evict = None


runtime = ModelRuntime()
