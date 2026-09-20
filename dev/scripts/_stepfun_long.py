import json, urllib.request, pathlib, time, sys

PROMPT = sys.argv[1]
SORTIE = pathlib.Path(sys.argv[2])
JOURNAL = pathlib.Path(sys.argv[3])

K = next(l.split('=',1)[1].strip() for l in open('.env.local', encoding='utf-8')
         if l.startswith('STEPFUN_API_KEY='))
d = json.loads(pathlib.Path(PROMPT).read_text(encoding='utf-8'))
d['model'] = 'step-5-preview'
d['stream'] = True
URL = "https://api.stepfun.ai/step_plan/v1/chat/completions"

req = urllib.request.Request(URL, data=json.dumps(d).encode('utf-8'),
    headers={"Authorization": "Bearer " + K, "Content-Type": "application/json"})

t = time.time()
contenu, n_raison, n_evt = [], 0, 0
dernier_journal = 0.0

def trace(msg):
    with JOURNAL.open('a', encoding='utf-8') as f:
        f.write("[%6.0fs] %s\n" % (time.time()-t, msg))

JOURNAL.write_text("", encoding='utf-8')
trace("connexion...")
try:
    with urllib.request.urlopen(req, timeout=3600) as r:
        trace("flux ouvert, lecture")
        for ligne in r:
            ligne = ligne.decode('utf-8', 'replace').strip()
            if not ligne.startswith('data: '):
                continue
            charge = ligne[6:]
            if charge == '[DONE]':
                trace("DONE recu")
                break
            try:
                o = json.loads(charge)
            except Exception:
                continue
            n_evt += 1
            delta = (o.get('choices') or [{}])[0].get('delta', {})
            if delta.get('reasoning_content') or delta.get('reasoning'):
                n_raison += 1
            bout = delta.get('content') or ''
            if bout:
                contenu.append(bout)
            if time.time() - dernier_journal > 20:
                dernier_journal = time.time()
                trace("vivant : %d evenements, %d deltas de raisonnement, %d car. de contenu"
                      % (n_evt, n_raison, sum(len(c) for c in contenu)))
except Exception as e:
    trace("ERREUR %s : %s" % (type(e).__name__, e))

txt = ''.join(contenu)
trace("fin : %d evenements, %d raisonnement, %d car. de contenu" % (n_evt, n_raison, len(txt)))
if txt:
    SORTIE.write_text(txt, encoding='utf-8')
    trace("ecrit dans %s" % SORTIE)
else:
    sys.exit(1)
