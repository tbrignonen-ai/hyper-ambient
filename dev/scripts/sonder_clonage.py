"""Ce que Pocket TTS sait faire d'un enregistrement de reference."""
import inspect

import pocket_tts

noms = [n for n in dir(pocket_tts) if not n.startswith("_")]
print("module :", noms)
for nom in noms:
    objet = getattr(pocket_tts, nom)
    if not inspect.isclass(objet):
        continue
    interessants = [
        m for m in dir(objet)
        if not m.startswith("_")
        and any(mot in m.lower() for mot in ("audio", "state", "voice", "prompt", "clone"))
    ]
    if interessants:
        print(f"\n{nom} : {interessants}")
        for m in interessants:
            try:
                print(f"   {m}{inspect.signature(getattr(objet, m))}")
            except (TypeError, ValueError):
                pass
