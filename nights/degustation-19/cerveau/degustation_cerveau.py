# Dégustation à l'oral des cerveaux locaux — à l'aveugle, questions improvisées par Thomas.
# Chaque cerveau est chargé sous une lettre ; 7 thèmes ; note 1–5 + commentaire ; captures d'écran (making-of).
import json, os, random, subprocess, time, datetime, sys
from PIL import ImageGrab
D = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(D, "captures")
CANDIDATS = sys.argv[1:] or ["NeoHorse-1-9B-Q4_K_M.gguf", "NeoHorse-1-4B-Q4_K_M.gguf",
             "Ministral-3-8B-Instruct-2512-Q4_K_M.gguf", "Luciole-8B-Instruct-1.1-Q4_K_M.gguf"]
THEMES = [
    ("Conversation / personnalité", "Parle-lui comme à une amie : salut, comment elle va, une banalité…"),
    ("Culture générale", "Une question de connaissance (histoire, science, cinéma…)."),
    ("Consigne de forme", "Impose une forme : « en une phrase », « détaille », « trois points »…"),
    ("Info à jour", "Une question qui demande le web : météo, actu, prix… (doit chercher, pas inventer)."),
    ("Suite de conversation", "Enchaîne sur sa réponse précédente : « et lui ? », « pourquoi ça ? »…"),
    ("Raisonnement concret", "Un petit problème : horaires, calcul, organisation…"),
    ("Question d'onboarding", "Une question de débutant : « comment je te parle ? », « tu sais faire quoi ? »…"),
]
def capture(nom):
    try:
        ImageGrab.grab(all_screens=True).save(os.path.join(CAP, nom + ".png"))
    except Exception as e:
        print("   (capture impossible :", e, ")")
def dx(cmd):
    return subprocess.run(["docker", "exec", "mother-core-dev", "sh", "-c", cmd], capture_output=True, text=True).stdout
def pret():
    return '"ok"' in dx("curl -s -m 3 localhost:8080/health")
random.seed(int(time.time())); ordre = CANDIDATS[:]; random.shuffle(ordre)
lettres = ["W", "X", "Y", "Z", "V", "U"][:len(ordre)]; SUF = "-" + time.strftime("%H%M")
carte = dict(zip(lettres, ordre)); json.dump(carte, open(os.path.join(D, ".carte-secrete" + SUF + ".json"), "w"), indent=1)
res = {"debut": datetime.datetime.now().isoformat(timespec="seconds"), "cerveaux": {}}
print("\n=========== DÉGUSTATION DES CERVEAUX — à l'aveugle ===========")
print(f"{len(ordre)} cerveau(x) ({', '.join(lettres)}). Pour chacun, 7 thèmes : tu improvises ta question à MOTHER,")
print("à la voix dans l'appli, puis tu notes de 1 à 5. (Entrée vide = passer le thème)\n")
for L in lettres:
    print(f"\n──────── Cerveau {L} : chargement… (1 à 3 min) ────────")
    subprocess.run(["docker", "exec", "mother-core-dev", "sh", "/tmp/brain.sh", carte[L]], capture_output=True)
    t = time.time()
    while not pret() and time.time() - t < 900: time.sleep(4)
    if not pret():
        print("   ⚠ échec de chargement, on passe."); continue
    print(f"   ✅ Cerveau {L} prêt ({round(time.time()-t)} s). Tu peux lui parler.")
    capture(f"{L}{SUF}-0-pret")
    notes = []
    for i, (th, aide) in enumerate(THEMES, 1):
        print(f"\n  Thème {i}/7 — {th}\n     {aide}")
        debut = datetime.datetime.now().isoformat(timespec="seconds")
        n = input("     Pose ta question, écoute… puis ta NOTE 1–5 : ").strip()
        capture(f"{L}{SUF}-{i}")
        c = input("     Commentaire (optionnel) : ").strip() if n else ""
        notes.append({"theme": th, "debut": debut, "fin": datetime.datetime.now().isoformat(timespec="seconds"), "note": n, "commentaire": c})
    g = input(f"\n  Impression générale sur {L} (optionnel) : ").strip()
    res["cerveaux"][L] = {"notes": notes, "general": g}
    json.dump(res, open(os.path.join(D, "notes" + SUF + ".json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("\n=========== FINI — merci ! Claude lève l'aveugle. ===========")
capture("fin"); input()
