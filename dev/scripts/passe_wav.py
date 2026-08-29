"""Un tour de parole complet a partir d'un fichier, sans micro.

talk.py exige un micro et une frappe au clavier : impossible a verifier depuis un
run autonome. Ce client rejoue un WAV sur le meme canal WebSocket, avec la meme
poignee de main, et mesure ce qui compte : le delai jusqu'au premier son, la
reponse prononcee, et les etats de presence emis en chemin.
"""
from __future__ import annotations

import json
import sys
import time
import wave
from pathlib import Path

import numpy as np
from websockets.sync.client import connect

URL = "ws://127.0.0.1:8001/hostagent"
SECRET = "partage-installation"
FRAME_SAMPLES = 320
SORTIE = Path("/workspace/data/out")


def lire_wav(chemin: Path) -> np.ndarray:
    with wave.open(str(chemin), "rb") as w:
        brut = w.readframes(w.getnframes())
        canaux = w.getnchannels()
    x = np.frombuffer(brut, dtype="<i2").astype(np.float32) / 32768.0
    return x.reshape(-1, canaux).mean(axis=1) if canaux > 1 else x


def ecrire_wav(chemin: Path, x: np.ndarray, taux: int = 16000) -> None:
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(np.clip(x * 32768.0, -32768, 32767).astype("<i2").tobytes())


def passe(nom: str) -> None:
    audio = lire_wav(Path(f"/workspace/data/in/{nom}.wav"))
    n = (len(audio) // FRAME_SAMPLES) * FRAME_SAMPLES
    trames = audio[:n].reshape(-1, FRAME_SAMPLES).tolist()

    with connect(URL, max_size=32 * 1024 * 1024) as ws:
        ws.send(json.dumps({"type": "hello", "secret": SECRET}))
        if json.loads(ws.recv()).get("type") != "ready":
            print("poignee de main refusee")
            return

        t0 = time.perf_counter()
        ws.send(json.dumps({
            "type": "invoke", "primitive": "audio.capture", "frames": trames
        }))

        premier_son = None
        recu: list[float] = []
        etats: list[str] = []
        rapport: dict = {}
        while True:
            message = json.loads(ws.recv())
            if message.get("type") == "state":
                etats.append(message["etat"])
                continue
            if message.get("type") == "report":
                rapport = message
                continue
            frames = message.get("frames")
            if frames is None:
                continue
            if not frames:
                break
            if premier_son is None:
                premier_son = (time.perf_counter() - t0) * 1000.0
            for trame in frames:
                recu.extend(trame)

    SORTIE.mkdir(parents=True, exist_ok=True)
    ecrire_wav(SORTIE / f"tour_{nom}.wav", np.asarray(recu, dtype=np.float32))
    print(f"=== {nom} ===")
    print(f"  entendu      : {rapport.get('transcript', '')}")
    print(f"  repondu      : {rapport.get('reply', '')}")
    print(f"  premier son  : {premier_son:.0f} ms" if premier_son else "  AUCUN SON")
    print(f"  etages       : {rapport.get('timings_ms', {})}")
    print(f"  etats emis   : {' -> '.join(etats) or 'AUCUN'}")
    print(f"  audio        : data/out/tour_{nom}.wav", flush=True)


if __name__ == "__main__":
    for nom in sys.argv[1:] or ["reflexe"]:
        passe(nom)
