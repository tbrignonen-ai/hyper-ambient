---
date: 2026-09-20
heure: ~21:15 Europe/Paris
type: out
lane: CARTE-DOSSIER
auteur: Cursor (Grok)
perimetre: lecture seule du depot ; un seul fichier ecrit (celui-ci)
interdit: git ; redaction du dossier ; modification de tout autre fichier
---

# Carte du dossier de soutenance — ce que le depot contient deja

**Ce fichier n'est pas le dossier.** Il ne remplit aucune case. Il dit ou
prendre, ce qui manque, et ce qui est faux si on le recopie.

Le fondateur n'ouvre pas une page blanche. Deux artefacts sont deja rediges
a sa place (voix d'agent, a reformuler) :

1. `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` — brouillon d'annexe
   technique 15–30 p. (C4, flux, RGPD, tests, roadmap). C'est le document le
   plus proche d'un memoire.
2. `nights/2026-09-20-TAQUET-BGB-COLLER.md` — blocs prets a coller dans le
   formulaire BC02, case par case. Complement :
   `nights/2026-09-20-TAQUET-BGB-PREFILL.md` et
   `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md`.

Le travail restant n'est pas « inventer le recit ». C'est : (a) ecrire a sa
voix, (b) ne coller que des chiffres de la carte figee du 19/09, (c) barrer
ce que les docs racine affirment encore et qui est faux.

Modele de reference produit **au 19 septembre 2026, test live**
(`nights/2026-09-19-CARTE-FIGEE.md`) :

| Brique | Modele | Mesure live |
|---|---|---|
| Cerveau | IBM Granite 4.2 3B Q4_K_M | 1er jeton 25–70 ms |
| Oreille | Whisper large-v3 int8 (faster-whisper) | 0,45–0,7 s / phrase |
| Voix | Magpie 357M, Sofia, CUDA | ~1,1 s avant le 1er son |
| GPU au repos | les trois + Windows | **7,3 Go / 12** |

Tout document qui dit encore LFM2.5, Pocket TTS `estelle`, Piper en voix
principale, ou « 500 ms round-trip » decrit **une autre stack**, celle d'aout /
du 2 septembre. La citer comme etat actuel du produit est un mensonge.

Le nom produit est **Hyper Ambient** (parfois « hyper-ambient »,
« Hyper-Ambiant »). « MOTHER » survit comme nom de depot, d'image Docker
(`mother-core-dev`), d'alias llama (`mother-local`), de variable
(`MOTHER_HOSTAGENT_SECRET`) et de hotword JeV. Ce n'est plus le nom a ecrire
sur la couverture.

---

## Inventaire du corpus documentaire

| Famille | Volume approx. | Role pour le dossier |
|---|---|---|
| Docs racine (`README.md`, `README.en.md`, `ARCHITECTURE.md`, `STACK.md`, `SETUP.md`, `STATUS.md`) | 6 fichiers | Intention : architecture / stack / setup. Realite : **cinq sur six sont depasses** (seul `README.en.md` est aligne sur la carte du 19/09). |
| Annexe technique | 1 fichier, ~370 lignes | Squelette du memoire. Brouillon, quelques paragraphes internes se contredisent. |
| Carte figee + protocole + resultats de degustation | 4 fichiers du 19/09 | Justification des choix de modeles. Precieux. |
| Bancs chiffres (oreille, voix, Magpie, Whisper, JeV, a11y, tests) | ~25 OUT dates | Matiere premiere des « resultats ». |
| Briefs / WRAP / ORGA / CONTACT / accountability | ~150 notes `nights/` | Methode de travail, pas a coller telles quelles. |
| Prefill / coller BC02 | 3 fichiers | Formulaire certif, pas le memoire. |
| Hors `nights/` | `dev/sessions/2026-08-21-implementation.md`, `dev/measurements/MEASUREMENT_PLAN.md`, `workers/night_health_vault_note/README.md`, `resources/bpmn/night_health_vault_note.bpmn` | Journal aout (stack ancienne) ; plan de mesure **jamais execute tel quel** ; automatisation Camunda. |
| Spec produit | **hors depot** : `D:\BGB Training\Projet MOTHER\` (cite par `README.md` / `STATUS.md`) | Cahier des charges original. Non inventorie ici. |
| Licence du depot | **absente** (aucun `LICENSE`) | Trou. Les licences des *modeles* sont dans la carte figee. |

`nights/` compte ~190 fichiers `.md` (plus `macos/` et `searxng/`). La majorite
sont des briefs d'agents. Pour ecrire, une dizaine de fichiers suffisent
(liste en fin de rapport). Le reste est archive de production.

Il n'y a pas de dossier `docs/`. Il n'y a pas d'ADR numerotes au-dela des
trois mentions dans `ARCHITECTURE.md` (ADR-001, 006, 012, 017).

---

## 1. Carte du dossier

Colonnes : section type d'un dossier technique de fin d'etudes ; ce qui existe
deja ; ce qui manque ; effort estime pour **Thomas** (pas un agent) afin de
combler — en partant du materiau, sans re-mesurer.

Echelle d'effort : **< 1 h** / **2–4 h** / **une soiree (4–8 h)** /
**journee+**. Les durees supposent qu'il reformule, pas qu'il invente.

| Section type | Ce qui existe deja et OU | Ce qui manque | Effort estime pour combler |
|---|---|---|---|
| **Couverture, identite, perimetre** | Nom et perimetre 0.1 dans `README.en.md` (19/09) et l'annexe §1. Cas d'organisation deja formule dans `TAQUET-BGB-COLLER.md` (« assistant vocal pour petite equipe tech »). Carte modeles figee. | Une phrase d'identite **a sa voix** (pas « Hyper Ambient (MOTHER) »). Etat civil / cohorte. Choix assume Camunda = low-code, le reste = code. | **< 1 h** — coller le bloc COLLER, barrer « (MOTHER) », signer. |
| **Contexte et probleme** | Annexe §1 (resume executif). COLLER section 1. `SUGGESTIONS-CASES-BGB.md` §1. Contraintes eliminees : FR, Windows, 12 Go, RGPD, pas d'audio cloud. | Un paragraphe « avant / apres » organisationnel (combien d'outils, quelle perte de contexte) **sans chiffre invente**. Le depot n'a pas d'enquete utilisateur ni de mesure de temps gagne. | **2–4 h** si recit personnel ; **< 1 h** si on reste sur le bloc COLLER. |
| **Etat de l'art** | Materiau **empirique**, pas bibliographique : `nights/2026-09-19-VEILLE-HF.md` (top HF 120 j, API, aucun poids telecharge) ; `nights/2026-09-19-WS-OREILLE.md` (Open ASR Leaderboard + taux d'erreur live Thomas) ; comparatifs mesures oreille/voix/cerveau (bancs 19/09) ; rejet Qwen3-TTS et Piper vs Magpie dans `STACK.md` (stack ancienne) ; `nights/2026-09-19-NOTE-JEV.md` (TypeSafe vs NanoJev). | **Aucun chapitre « etat de l'art ».** Pas de revue Alexa / Siri / Google / Pipecat LiveKit / Open-WebUI. Pas d'articles cites (hors CNIL / ANSSI / OWASP dans l'annexe). La veille HF n'est pas une revue de litterature. | **Une soiree** pour un etat de l'art honnete de 3–5 pages (partir des bancs + 5–8 refs). **Journee+** si on veut une revue academique. Ne pas transformer la veille HF en « etat de l'art » sans le dire. |
| **Choix d'architecture et justification** | `ARCHITECTURE.md` : idee « noyau conteneurise + host-agent natif », GATE, duplex — **mais schema et Next Steps faux**. `STACK.md` : principe « un protocole, deux deploiements » encore juste. Annexe §2 : C4 niveau 1 et 2 **a jour** (Granite / Whisper large-v3 / Magpie). Carte figee § « Pourquoi ces choix ». ADR cites : 001 (deux composants), 012 (pas de secret dans l'audit), 017 (budget 26–37 ms acoustique). | Justification **alignee sur la carte du 19/09** (Granite vs Ministral vs Luciole ; Whisper large-v3 vs Parakeet vs Nemotron ; Magpie Sofia vs F5 vs Pocket). Les raisons sont dans la degustation et les bancs, pas redigees en chapitre. Les ADR ne sont pas des fichiers. | **2–4 h** : copier les deux Mermaid de l'annexe + 1 page « pourquoi ces trois modeles » depuis `CARTE-FIGEE` + `DEGUSTATION-CERVEAUX-RESULTATS`. Ne **pas** copier `ARCHITECTURE.md` tel quel. |
| **Stack technique** | `STACK.md` (dense, mesure, **stack 2 sept**). `SETUP.md` (Docker, GPU, ports — encore utile pour le *comment lancer*, faux sur les modeles). `STATUS.md` (tableau capacites **2 sept**). `README.en.md` (vrai au 19/09). `dev/scripts/carte_figee.env` (config, pas de la prose). Worker Camunda : `workers/night_health_vault_note/README.md` + BPMN. Ports : 8001 host-agent, 8090 cerveau, 8092 Magpie (COLLER ; les docs racine disent encore Piper in-process). | Un tableau stack **unique** date du 19/09. Les docs racine se contredisent entre eux (voir §3). Pas de schema de deploiement « Presence / Docker / ponts / Camunda » hors annexe. | **2–4 h** de reecriture des docs racine (hors perimetre dossier, mais **bloquant** si le jury ouvre le README). Pour le dossier : **< 1 h** a partir de l'annexe §1–2 + carte figee. |
| **Methode de travail** | Tres riche, trop riche. `nights/2026-09-19-ORGA-SESSION.md` (roles Thomas / Claude / Cursor / Codex). `nights/2026-09-20-MAKINGOF-ACCOUNTABILITY.md` + `dev/scripts/account.py` (lanes, OUT, EXIT). `nights/2026-09-19-PROTOCOLE-DEGUSTATION.md` (choix a l'aveugle). `nights/2026-09-18-ORGA-BOUCLE.md` (anti-fiasco). Bancs reproductibles (`dev/scripts/bench_*.py`, `loopback_test.py`). Audit honnete des tests : `nights/2026-09-20-OUT-AUDIT-QUALITE-TESTS.md` (couverture en trompe-l'oeil). Lot A 20/09 : sondes d'onboarding, 19 tests verts. | Une page « comment j'ai travaille » a la 1re personne, avec la flotte d'agents declaree (le COLLER le fait deja). Le jury BC02 veut aussi une **methode de gestion des risques** (grille proba × impact) : l'annexe §6 a le tableau, pas les notes 1–4. | **< 1 h** (COLLER § contributions + 1 paragraphe protocole aveugle). Grille de risques : **2–4 h** si on note vraiment. |
| **Resultats et mesures** | C'est le point fort du depot. Voir **§2 ci-dessous** (chaque chiffre, date, fichier). Sources prioritaires : `CARTE-FIGEE` (live), bancs oreille/voix du 19/09, C9 Magpie CUDA, C2 sondes, contrastes 20/09, pytest dates. | **Pas de synthese unique.** Les 500 ms / 75 ms / 96,01 % trainent encore dans README/STATUS et pollueront le dossier s'ils sont copies. Pas de courbe, pas de graphique (sauf captures Presence hors markdown). Relance pytest **la veille de la soutenance** exigee par l'annexe, pas faite ici. | **2–4 h** pour un chapitre « resultats » de 4–6 pages qui ne cite que le §2.A. Relance live + pytest : **1–2 h** le 24/09. |
| **Limites connues** | Carte figee « Reserves » + « Problemes ouverts » : 1re requete perdue ; web « rien trouve » ; Magpie sans debit ; Granite nul en calcul mental (d'ou outil `calculer`) ; hotwords Whisper non cables. Annexe [A PROUVER] : Camunda bout-en-bout, C1 tour vocal vers pont, lecteur d'ecran, retention RGPD, droits du coffre. Audit tests 20/09 : pytest ≠ parcours vocal reel. C7 : Docker n'est pas un installeur Windows. | Un chapitre limites **assume**, 1–2 pages, sans les deguiser en « perspectives ». Le WRAP soir 19/09 est partiellement **perime** (C4/C8 ont ete livres ensuite). | **< 1 h** a partir de la carte figee + annexe [A PROUVER]. Resiste a la tentation de dire que C1 est prouve. |
| **Perspectives / roadmap** | Annexe §10 (RICE **qualitatif**, pas de scores). ORGA-SESSION : Mac, EN/ES, Hyper-Ambient-XL ~20 Go. C7 etude Windows natif sans Docker. `nights/macos/` (portage, pas livre). EN **deja livre** en 0.1 (`HA_LANG=en`, 13 tests C8 + suite parite 20/09) — la roadmap « EN/ES » de l'annexe est donc **fausse pour l'anglais**. | Scores RICE chiffres (l'annexe refuse de les inventer). Decision Mac : etude seulement. ES : rien. XL : une ligne. | **< 1 h** : recopier le tableau RICE en corrigeant « EN deja en 0.1, ES et Mac en P1 ». Chiffrer RICE : **2–4 h** et ce sera du doigt mouille — l'annexe a eu raison de ne pas le faire. |
| **Interop / SI / automatisation** *(case BC02, pas un chapitre academique classique)* | Annexe §3 et §5. Table interop COLLER. BPMN + worker. Ponts `:8765/:8766/:8767`. SearXNG + replis (`nights/searxng/`). GATE. | Preuve **live** Camunda (health → note) encore [A PROUVER]. Tour vocal C1 vers Claude/Codex encore [A PROUVER] (37 tests = chargement des cles, pas un tour parle). Auth Camunda [A PROUVER]. | Redaction : **< 1 h** (deja ecrit). Preuves live : **une soiree** de repetition de demo. |
| **Securite, RGPD, accessibilite** | Annexe §4 (flux), §6 (risques), §9. Contrastes mesures 20/09. Clavier Presence. Secrets hors git. ADR-012. Host-agent ecoute `0.0.0.0` (defaut confirme 20/09). Feedback = bouton qui ouvre une issue, **pas** une collecte auto. | Base legale, notice, duree de conservation, procedure d'effacement : **absents**. Pas de DPIA. Lecteur d'ecran [A PROUVER]. Politique du coffre [A PROUVER]. | Redaction prudente (reformuler en « cible ») : **< 1 h**. Formaliser RGPD pour de vrai : **journee+** et ce n'est pas du code. |
| **Tests, preuves, journal de versions** | Annexe §7 (T1–T7). OUT dates avec `N passed`. `git log` cite dans l'annexe (S27) — **non relu ici** (consigne : aucune commande git). Captures : `nights/2026-09-18-cursor-ui-*.png` (citees, non reouvertes) ; degustation `degustation-19/`. | Sortie pytest **fraiche** (19/09 = 1105/11/2 ; 20/09 barge-in = 1313/5 — le chiffre bouge). Journal de versions a extraire le 24/09. Captures relues (pas de secret, pas de PII). | **2–4 h** la veille (pytest + 4 captures propres + 10 lignes de `git log`). |
| **Demos soutenance (C1 / C2)** | C2 : `nights/2026-09-19-C2-ALERTE.md` — 7 tests, 3 captures, sondes 41 / 1560 / 52 ms. C1 : `nights/2026-09-19-C1-OUTILS.md` — 37 tests, registre 0→3 outils. Plan de fil unique dans SUGGESTIONS-CASES. | C1 **vocal** vers pont externe : pas d'OUT. Fil unique jamais rejoue de bout en bout dans un seul document. | Repetition : **2–4 h**. Sans C1 live, le plan B (captures) est deja prevu. |

Lecture honnete de la colonne « manque » : le fondateur a **deja** le squelette
(annexe + COLLER). Les trous reels sont (1) l'etat de l'art redige,
(2) l'alignement des docs racine, (3) trois preuves live (C1 vocal, Camunda
E2E, lecteur d'ecran), (4) sa voix. Tout le reste est de la selection, pas
de l'invention.

---

## 2. Chiffres disponibles

Regle de lecture de ce tableau.

- **§2.A** = chiffres a citer dans le dossier (stack actuelle, 19–20/09).
- **§2.B** = bancs comparatifs (justifient un choix ; ce ne sont pas des
  perfs du produit en service).
- **§2.C** = tests automatises (preuves de non-regression, pas de latence).
- **§2.D** = JeV / accessibilite / ponts.
- **§2.E** = **historiques — ne pas citer comme etat du produit**.
- **§2.F** = chiffres d'editeur ou de classement public, pas mesures ici.

Les dates sont celles du fichier porteur. Une valeur sans fichier n'est pas
dans ce tableau.

### 2.A — Stack actuelle (a citer)

| Mesure | Valeur | Date | Fichier |
|---|---|---|---|
| Oreille, transcription / phrase (live, voix Thomas) | 0,45 a 0,7 s | 2026-09-19 ~20h | `nights/2026-09-19-CARTE-FIGEE.md` |
| Cerveau, temps au 1er jeton (live) | 25 a 70 ms | 2026-09-19 ~20h | idem |
| Voix, temps au 1er son, phrase courte (live) | ~1,1 s | 2026-09-19 ~20h | idem |
| Voix, phrase longue / nombres (live) | 3,2 a 4,8 s | 2026-09-19 ~20h | idem |
| VRAM au repos, stack complete + Windows | 7,3 Go / 12 Go | 2026-09-19 ~20h | idem |
| Taille cerveau Granite Q4_K_M | 2,24 Go | 2026-09-19 | `nights/2026-09-19-CARTE-FIGEE.md` ; octets exacts `nights/2026-09-20-TAQUET-SSD-E.md` : 2 244 011 552 |
| Taille oreille Whisper large-v3 (cache HF) | 2,9 Go (carte) / 3 087 284 237 octets (SSD) | 2026-09-19 / 20 | carte figee ; `TAQUET-SSD-E.md` |
| Taille Magpie + codec | 449 Mo + 79 Mo | 2026-09-19 / 20 | idem |
| Magpie Sofia CUDA, TTFA `synthesize` | 1341,1 ms | 2026-09-19 | `nights/2026-09-19-C9-MAGPIE-OUT.md` |
| Magpie Sofia CUDA, 1er morceau stream | 1498,8 ms | 2026-09-19 | idem |
| Magpie Sofia CUDA, prechauffage mouth | 218 ms | 2026-09-19 | idem |
| Magpie Sofia CPU, TTFA (meme phrase) | 4473,2 ms | 2026-09-19 | idem |
| Magpie Sofia CPU, prechauffage | 947 ms | 2026-09-19 | idem |
| VRAM avant relance Magpie CUDA | 6181 MiB used / 5830 MiB free | 2026-09-19 | idem |
| VRAM apres boot CUDA Magpie | 7310 MiB used / 4701 MiB free (+1129 MiB) | 2026-09-19 | idem |
| VRAM apres synthese test CUDA | 8512 MiB used / 3498 MiB free (+2331 MiB) | 2026-09-19 | idem |
| Score degustation Granite 4.2 3B (retenu) | 4,57 / 5 (notes 5, 5, 4, 4, 5, 5, 4) | 2026-09-19 | `nights/2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS.md` |
| Score degustation Ministral-3-8B | 5,0 / 5 — **repli seulement**, juge trop ancien | 2026-09-19 | idem |
| Score degustation NeoHorse-1-9B | 4,0 / 5 (repli 2e choix) | 2026-09-19 | idem |
| Score degustation Luciole-8B | 2,7 / 5 | 2026-09-19 | idem |
| Score degustation NeoHorse-1-4B | 2,0 / 5 | 2026-09-19 | idem |
| VRAM Granite Q4_K_M (avec cache, banc cerveau) | ≈ 3 Go | 2026-09-19 | idem |
| VRAM Ministral Q4_K_M | ≈ 5,5 Go | 2026-09-19 | idem |
| Chargement Granite (preseletion ecrite) | 15 s | 2026-09-19 | idem |
| Whisper large-v3 a chaud, latence phrases 1–5 | 0,569 / 0,488 / 0,431 / 0,424 / 0,545 s | 2026-09-19 | `nights/2026-09-19-BANC-OREILLE-2-OUT.md` |
| Whisper large-v3, VRAM propre | +1977 MiB (6356 → 8333) | 2026-09-19 | idem |
| Whisper large-v3, chargement a chaud | 16,183 s | 2026-09-19 | idem |
| Whisper large-v3, 1er chargement a froid | 263,079 s | 2026-09-19 | idem (ne pas citer comme latence de tour) |
| Contraste texte principal Presence | 12,9:1 | 2026-09-20 | `nights/2026-09-20-TAQUET-PRODUIT-OUT.md` (recopie annexe) |
| Contraste texte secondaire | 6,1:1 | 2026-09-20 | idem |
| Contraste texte sur bouton clair | 14,3:1 | 2026-09-20 | idem |
| Contraste bandeau alerte C2 (`#fff8e8` sur `#7a1212`) | 10,32:1 | 2026-09-20 | `nights/2026-09-20-TAQUET-README-DEV.md` §5 — **autre couple de couleurs** que les 12,9:1 |
| Sonde sante C2 AVANT (UP) | 41 ms | 2026-09-19 | `nights/2026-09-19-C2-ALERTE.md` |
| Sonde sante C2 PENDANT (pont Codex coupe) | 1560 ms | 2026-09-19 | idem |
| Sonde sante C2 APRES (UP) | 52 ms | 2026-09-19 | idem |
| Image Docker (CUDA devel + compile) | 32,3 Go | 2026-08-21 | `SETUP.md` ; `dev/sessions/2026-08-21-implementation.md` — **non remesure depuis** |

Les ~1,1 s live et les 1341 ms C9 mesurent des choses voisines mais pas
identiques (tour complet vs synthese isolee). Pour le dossier : citer le
**live 1,1 s** comme perce, et C9 comme banc moteur.

### 2.B — Bancs comparatifs (justification, pas perf produit)

Oreille, 1er banc, wav 13,026 s (`nights/2026-09-19-BANC-OREILLE-OUT.md`,
2026-09-19) — RTF et VRAM **pendant que llama + host-agent occupent deja le
GPU** ; ne pas lire ces RTF comme « l'oreille en service » :

| Candidat | Temps | RTF | VRAM max |
|---|---|---|---|
| faster-whisper large-v3-turbo | 47,990 s | 3,684 | 6769 MiB |
| Qwen3-ASR-0.6B | 87,754 s | 6,737 | 6647 MiB |
| parakeet-tdt-0.6b-v3 INT8 | 108,020 s | 8,292 | 3841 MiB |
| nemotron-3.5-asr GGUF | 5,319 s | 0,408 | 10355 MiB |
| stepaudio-2.5-asr HTTP | 3,535 s | 0,271 | 3776 MiB |
| kyutai/stt-1b (SIGSEGV, exit 139) | 254,980 s | 19,574 | 6495 MiB |

Oreille, 2e banc, phrases reelles Thomas
(`nights/2026-09-19-BANC-OREILLE-2-OUT.md`) :

| Candidat | Chargement | Latence p1–p5 | VRAM propre |
|---|---|---|---|
| parakeet | 24,621 s | 0,618 / 0,326 / 0,316 / 0,313 / 0,743 s | 0 MiB (delta) |
| whisper-large-v3 (retenu) | 16,183 s chaud | 0,569 / 0,488 / 0,431 / 0,424 / 0,545 s | +1977 MiB |
| canary-1b-v2 | 35,956 s | 1,775 / 0,247 / 0,168 / 0,139 / 0,281 s (p1 = warmup) | +4406 MiB |

Taux d'erreur **live FR, voix Thomas**, modeles **avant** le choix final
(`nights/2026-09-19-WS-OREILLE.md`) : Parakeet 11 % · Whisper-turbo 13 % ·
Nemotron-3.5 19 % · StepASR 23 % · Qwen3-ASR 28 %. Ce n'est **pas** le WER
de Whisper large-v3 retenu. Le large-v3 a ete choisi ensuite, sur les
propres enregistrements (noms propres, nombres) — qualitatif dans la carte
figee, pas un WER %.

Voix, banc 2 (`nights/2026-09-19-BANC-VOIX2-OUT.md`) : Edge0/audio8-TTS
132,3 s CPU · Magpie Aria CPU 7,4 s · OmniVoice-GGUF 74,1 s. Magpie nombres
(`nights/2026-09-19-MAGPIE-NOMBRES-OUT.md`) : F0 Sofia 197 Hz, synthese
8,275 s pour 9,845 s d'audio.

StepAudio 2.5 TTS distant : ~3,8 s / phrase
(`nights/2026-09-19-C5-OUT.md`). Ce n'est pas Magpie.

### 2.C — Resultats de tests (dates, ca bouge)

| Mesure | Valeur | Date | Fichier |
|---|---|---|---|
| pytest conteneur, soir carte figee | 1105 passed / 11 skipped / 2 failed (Presence Windows) | 2026-09-19 ~20h | `nights/2026-09-19-WRAP-SOIR.md` ; annexe [S03] |
| pytest Presence hote Windows | 32 / 32 | 2026-09-19 | idem |
| pytest conteneur, barge-in | 1313 passed / 5 failed | 2026-09-20 | `nights/2026-09-20-OUT-CURSOR-BARGE-IN.md` |
| pytest onboarding configurable (ref.) | 1323 / 5 | 2026-09-20 | `nights/2026-09-20-OUT-CODEX-ONBOARDING-CONFIGURABLE.md` |
| Lot A sondes onboarding | 19 passed (conteneur 5,76 s ; Windows 5,28 s) | 2026-09-20 | `nights/2026-09-20-OUT-CURSOR-LOT-A.md` |
| C1 outils / `.env.local` | 37 passed ; registre 0 → 3 outils | 2026-09-19 | `nights/2026-09-19-C1-OUTILS.md` |
| C2 alerte / reprise | 7 passed in 2,76 s | 2026-09-19 | `nights/2026-09-19-C2-ALERTE.md` |
| C3 JeV module | 6 passed | 2026-09-19 | `nights/2026-09-19-C3-OUT.md` |
| C4 web (mocks, pas reseau) | 74 passed | 2026-09-19 | `nights/2026-09-19-C4-OUT.md` |
| C5 remote TTS | 8 passed | 2026-09-19 | `nights/2026-09-19-C5-OUT.md` |
| C8 i18n EN | 13 passed ; regression 14 puis 27 | 2026-09-19 | `nights/2026-09-19-C8-EN-OUT.md` |
| Parite anglaise | 29 passed / 2 xfail | 2026-09-20 | `nights/2026-09-20-OUT-TESTS-ANGLAIS.md` |
| C9 Magpie | 12 passed (CPU) puis 9 passed (GPU) ; 4 failed avant correctif | 2026-09-19 | `nights/2026-09-19-C9-MAGPIE-OUT.md` |
| C10 premier tour | 2 passed (+ regression 10) | 2026-09-19 | `nights/2026-09-19-C10-PREMIER-TOUR-OUT.md` |
| C11 identite | 2 passed ; regression 69 | 2026-09-19 | `nights/2026-09-19-C11-OUT.md` |
| C12 calculer | 30 passed ; regression 133 | 2026-09-19 | `nights/2026-09-19-C12-OUT.md` |
| JeV V2 corpus | 0 FN / 0 FP sur 24 adressees + 22 non ; 36 passed | 2026-09-20 | `nights/2026-09-20-OUT-JEV-V2-POSE.md` |
| Tool-memory | 146 + 64 passed | 2026-09-20 | `nights/2026-09-20-OUT-FIX-TOOL-MEMORY.md` |
| Presence JeV mains libres | 52 + 40 passed | 2026-09-20 | `nights/2026-09-20-OUT-PRESENCE-JEV-MAINS-LIBRES.md` |
| VAD bande voix | 15 passed | 2026-09-20 | `nights/2026-09-20-OUT-VAD-BANDE-VOIX.md` |
| Ecoute continue | 8 + 28 passed | 2026-09-20 | `nights/2026-09-20-OUT-ECOUTE-CONTINUE.md` |
| Reveil court | 29 passed | 2026-09-20 | `nights/2026-09-20-OUT-REVEIL-COURT.md` |
| Taquet produit | 7 passed ; regression 32 | 2026-09-20 | `nights/2026-09-20-TAQUET-PRODUIT-OUT.md` |
| Smoke 20/09 simple / complexe | « ok » **sans chiffre** | 2026-09-20 | `nights/2026-09-20-SMOKE-SIMPLE-OUT.md`, `SMOKE-COMPLEX-OUT.md` |

Le « 9/9 ✓ » du `README.md` / `SETUP.md` **n'apparait dans aucune sortie
reelle**. `nights/2026-09-20-TAQUET-README-DEV.md` §8 : `smoke_test.py`
imprime « N ok, M failed, K skipped », et 2 des 9 lignes sondent encore
Piper et `whisper-cli` (heritages), pas Magpie ni Whisper large-v3.

### 2.D — JeV, ponts, VAD

| Mesure | Valeur | Date | Fichier |
|---|---|---|---|
| JeV API, connexion neuve | 701 ms (C3) / 692 ms (NOTE) | 2026-09-19 | `nights/2026-09-19-C3-OUT.md` ; `NOTE-JEV.md` |
| JeV API, mediane keep-alive | 325 ms (5 phrases) / ~280 ms (36 appels) | 2026-09-19 | idem |
| JeV phrases C3 | 288 / 328 / 268 / 344 / 325 ms | 2026-09-19 | `C3-OUT.md` |
| JeV, surcout 1300 jetons de contexte | +40 ms | 2026-09-19 | `NOTE-JEV.md` |
| JeV prechauffage, connexion a 60 s / 90 s | 351 ms / 601 ms | 2026-09-20 | `nights/2026-09-20-OUT-JEV-PRECHAUFFAGE.md` |
| Seuil JeV recommande (calibrage) | 0,60 (0 FN? **4 FN / 0 FP** sur le corpus) vs 0,75 actuel (9 FN) | 2026-09-20 | `nights/2026-09-20-OUT-CALIBRAGE-JEV.md` |
| Exemples scores JeV (extrait) | « Hyper Ambient, explique-moi la photosynthese » 0,96 ; « MOTHER, annule… » 0,96 ; « Hyper Ambient » seul 0,39 ; non-adressee recette 0,06 ; FP potentiel « et maintenant, place au film » 0,55 | 2026-09-20 | idem (table complete dans le fichier, ~30 phrases) |
| NanoJev 5 phrases FR | 0,33–0,79, **aucune discrimination** | 2026-09-19 | `NOTE-JEV.md` |
| PONG ponts :8765 / :8766 / hermes | 5,3 s / 11,0 s / 0,0 s | 2026-09-18 | `nights/2026-09-18-HARNAIS.md` |
| Plancher segment VAD (anti-hallucination Whisper) | 700 ms ; mesure « Realise par Neo035 » 1,06–1,12 s | 2026-09-20 | `nights/2026-09-20-OUT-VAD-BANDE-VOIX.md` |
| Bande voix VAD | 85–3400 Hz | 2026-09-20 | idem |
| Voix continue avant barge-in | 400 ms | 2026-09-20 | `nights/2026-09-20-OUT-CURSOR-BARGE-IN.md` |
| Accountability ledger | 16 evenements au 20/09 10h40 (11 open, 2 pulse, 3 close) | 2026-09-20 | annexe §2.4 ; `nights/ACCOUNTABILITY-LEDGER.jsonl` |

### 2.E — Historiques : ne pas citer comme etat du produit

Ces chiffres sont **vrais a leur date**, sur **une autre stack** (Luth /
LFM2.5, Piper ou Pocket `estelle`, Whisper **turbo**, pas large-v3). Les
coller dans le dossier a cote de Granite/Magpie produit un document qui se
contredit.

| Mesure | Valeur | Date | Fichier | Pourquoi c'est perime |
|---|---|---|---|---|
| Round-trip percu chaine complete | **500 ms** | 2026-08-21 | `STACK.md`, `STATUS.md`, `README.md`, `dev/sessions/2026-08-21-implementation.md` | Piper + turbo + LFM2.5. Live 19/09 = **~1,1 s** au 1er son. |
| EARS turbo | 370 ms, RTF 0,087, WER 2,6 % | 2026-08-21 | idem | Oreille changee. WER 2,6 % = boucle Piper→Whisper, pas voix humaine. |
| MOUTH Piper TTFA | 102 ms | 2026-08-21 | `STACK.md` | Voix changee. |
| MOUTH Pocket `estelle` TTFA | 75 ms (63 ms chaud), 1,49 Go | 2026-08-21 / 2026-09-02 | `STATUS.md`, `README.md` | Voix changee. |
| BRAIN LFM2.5-2.6B TTFT | 27 ms ; 26–38 ms ; ~1,9 Go | 2026-09-02 | `STACK.md`, `STATUS.md` | Cerveau change. |
| Comparatif 5 cerveaux (TTFT / car/s / VRAM) | LFM2.5-VL 26 ms 667 c/s 2,0 Go · Luth 38 ms 697 1,5 Go · Ministral 39 ms 331 5,4 Go · Luciole 120 ms 341 5,1 Go · Qwen3-4B 43 ms 389 2,8 Go | 2026-08-21 | `STACK.md` | Banc utile comme **methode**, pas comme choix actuel. Granite n'y figure pas. |
| Arithmetique 5 cerveaux | 0/5 (tous repondent 15 h 20 au lieu de 15 h 40) | 2026-08-21 | `STACK.md`, `STATUS.md` | Toujours pedagogiquement vrai (Granite aussi se trompe → outil `calculer`), mais le tableau cite de mauvais modeles. |
| Distant primaire + repli 600 ms | 1477 ms vs 876 ms local | 2026-08-21 | `STATUS.md` | Decision « local d'abord » encore tenue ; les ms sont d'une autre chaine. |
| Smart Turn v3 FR | 96,01 % acc, 1,60 % FP, 2,39 % FN, 12 ms, 1253 ech. | 2026-08-21 | `STATUS.md`, `README.md` | **Non installe** au 2 sept ; absent de la carte figee. Ne pas ecrire « 96 % d'endpointing » comme capacite livree. |
| MiniMax-M3 TTFC p50 | 612 ms | 2026-08-21 | `STATUS.md` | Escalade MiniMax n'est plus le recit produit (l'utilisateur decide). |
| Piper vs Qwen3-TTS llama-tts | RTF 0,03 vs 0,21–0,30 ; 1er audio 102 vs 1040 ms | 2026-08-21 | `STACK.md` | Argument « pourquoi pas ce TTS-la » encore valable ; Piper n'est plus la voix. |
| VRAM libre, Luth + bureau | 7996 MiB | 2026-08-21 | `STACK.md` (le fichier dit lui-meme que ce n'est plus la stack) | Remplace par 7,3/12 du 19/09. |
| Smoke attendu SETUP | TURN 20 ms, EARS 370 ms WER 2,6 %, BRAIN 27 ms, Pocket 75 ms | (exemple dans SETUP, copie aout) | `SETUP.md` | Sortie **inventee comme attendue**, pas une mesure du 20/09. |
| Tour « Bonjour » classe REFLEXE | 618 ms | 2026-09-17 | `nights/2026-09-17-CURSOR-HARNAIS-BF.md` | Routeur d'escalade abandonne le 19/09 (`NOTE-JEV.md`). |
| Supertonic 1er son | ~3 s | 2026-09-15 | `nights/2026-09-15-WRAP-CLAUDE.md` | Repli documente, pas la voix 0.1. |
| Chargement Pocket TTS | 81,9 s | 2026-09-14 | `nights/2026-09-14-CODEX-VOLUME.md` | Voix changee. |
| pytest conteneur 15 sept | 1001 passed / 2 failed | 2026-09-15 | `nights/2026-09-15-WRAP-CLAUDE.md` | Compteur mort. |

`STACK.md` se contredit **dans la meme page** : « EARS is now the dominant
cost (370 of 500 ms) » puis « MOUTH is now the dominant cost (515 of 912 ms) ».
Deux campagnes, un seul fichier presente comme etat courant.

### 2.F — Chiffres d'ailleurs (citer comme tels, ou pas)

| Mesure | Valeur | Date | Fichier | Nature |
|---|---|---|---|---|
| WER board HF Parakeet FLEURS-fr / MCV-fr / MLS-fr | 4,68 / 6,35 / 5,12 % | 2026-09-19 | `nights/2026-09-19-WS-OREILLE.md` | Open ASR Leaderboard, pas ce GPU |
| WER board HF Whisper-turbo FLEURS-fr / MCV-fr / MLS-fr | 4,90 / 11,06 / 4,22 % | 2026-09-19 | idem | idem |
| WER board HF Canary-1b-v2 FLEURS-fr / MLS-fr | 4,35 / 3,45 % | 2026-09-19 | idem | idem |
| RTFx board HF Parakeet FR / EN | 3618 / 6076 | 2026-09-19 | idem | machine du classement, pas la 4070 |
| JeV latence « annoncee » editeur | 70–500 ms | 2026-09-19 | `NOTE-JEV.md` | fiche TypeSafe, pas une mesure |
| OpenJev / Verdict p50 CPU (tiers) | 35,6 ms | 2026-09-19 | `NOTE-JEV.md` | projet tiers, anglais seulement |
| Qwen TTS « 97 ms first-packet » | 97 ms | 2026-08-21 | `STACK.md` | claim editeur ; mesure locale 1040 ms via llama-tts |

---

## 3. Depasse ou faux dans la documentation existante

Un document qui se contredit est pire qu'un document absent. Liste pour
**ne pas coller**, pas pour reecrire ici.

### 3.1 Nom du produit

| Fichier | Ce qu'il dit | Verite |
|---|---|---|
| `README.md` | Spec dans `D:\BGB Training\Projet MOTHER\` ; alias `mother-local` ; conteneur `mother-core` | Chemins/alias techniques encore vrais. Le **produit** s'appelle Hyper Ambient. |
| `STACK.md` | Schema `mother-core (container)` | Idem. |
| `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` §1 | « MOTHER reste un composant logiciel » | Phrase a barrer ou remplacer par Hyper Ambient. |
| `nights/2026-09-20-TAQUET-BGB-COLLER.md` | « Hyper Ambient **(MOTHER)** » dans la case low-code | Ne pas coller les parentheses. |
| `nights/2026-09-20-TAQUET-BGB-PREFILL.md` | Idem | Idem. |
| `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md` | « MOTHER est du code » | Reformuler. |
| `nights/2026-09-20-CONTACT-CARD.md` | Vault `10-Projects\MOTHER` | Chemin Obsidian, pas le nom produit. |
| Code / env | `MOTHER_HOSTAGENT_SECRET`, hotword JeV « MOTHER », dossier `MOTHER-dev` | Survivances techniques. Acceptables en annexe « glossaire interne », pas en couverture. |

`README.en.md` est le seul doc racine qui dit « Hyper Ambient » sans
presenter l'ancienne stack comme actuelle.

### 3.2 Stack presentee comme actuelle alors qu'elle ne l'est plus

| Fichier | Date affichee | Ce qu'il affirme encore | Remplace par (19/09) |
|---|---|---|---|
| `README.md` | 2026-08-21 | Pocket TTS `estelle`, LFM2.5-2.6B, MiniMax-M3, round-trip 500 ms, Smart Turn 96,01 %, smoke 9/9, `make models` ~1,2 Go | Granite / large-v3 / Magpie Sofia ; 1,1 s ; 7,3 Go ; ~5,9 Go de modeles |
| `STATUS.md` | 2026-09-02 | Meme stack. « Prochaines etapes » n°4 : **agent hote natif** — il existe depuis des semaines. MOUTH 75 ms Pocket **et** 102 ms Piper dans le meme fichier. | Carte figee. Presence + host-agent sont livres. |
| `STACK.md` | (maj 2026-09-02) | Piper = MOUTH ; LFM2.5 selectionne ; 500 ms ; contradiction 370/500 vs 515/912 | Principe « un protocole deux deploiements » encore juste. Chiffres a archiver. |
| `ARCHITECTURE.md` | (non date) | whisper.cpp ~10 MB + nemotron ; Pocket TTS + **MOSS-TTS** ; BRAIN = Claude / GPT-4o / Gemini ; « Next Steps : Implement EARS… » ; arborescence `nemotron.py`, `moss_tts.py` | Document de **cible initiale**, pas d'architecture livree. Le coller = dire que le projet n'est pas construit. |
| `SETUP.md` | (aligne 2 sept) | `make llama` → LFM2.5 ; smoke attendu Pocket 75 ms ; image 32,3 Go ; chemin `D:\BGB Training\MOTHER-dev` | Procedure Docker / GPU encore utile. Modeles et sortie smoke faux. |
| `dev/measurements/MEASUREMENT_PLAN.md` | (aout) | Mesurer whisper.cpp `tiny` sur 30 min ; Pocket TTS TTFA ; Pipecat FPR | **Jamais execute tel quel.** Les vrais bancs sont dans `nights/2026-09-19-BANC-*`. |
| `.env.example` (signale, non relu ici) | — | D'apres `TAQUET-README-DEV.md` §8.7 : `BRAIN_SERVICE=stepfun`, `EARS=qwen3/0.6B`, `MOUTH=pocket/estelle`, `MODEL=MiniCPM5-2B` | Un `copy .env.example .env.local` + `make demo` rate. Defaut de configuration deja identifie (Lot A / taquet README). |

### 3.3 Contradictions **internes** a un meme document

| Fichier | Contradiction |
|---|---|
| `STACK.md` | EARS dominant (370/500 ms) **et** MOUTH dominant (515/912 ms). |
| `STATUS.md` | MOUTH Pocket 75 ms dans le tableau capacites, Piper 102 ms dans la decomposition « latence globale ». |
| `ARCHITECTURE.md` | Titre hyper-ambient, schema encore plein de composants jamais livres (MOSS-TTS, FunASR, PROFILE_LARGE A100). « [A VERIFIER] RTF / TTFA » alors que des mesures existent ailleurs depuis aout, puis ont change en septembre. |
| Annexe technique | §1 : anglais livre en 0.1. §10 RICE : « EN/ES … hors perimetre francais actuel ». Les deux phrases ne peuvent pas rester. |
| Annexe technique | §7 T2 / intro : C2 **PROUVE**. §8 dernier paragraphe : « ne pas decrire C2 comme realisee tant que OUT et captures ne sont pas disponibles ». L'OUT existe (`C2-ALERTE.md`). Paragraphe stale. |
| Annexe technique | §1 : host-agent « n'ecoute pas uniquement en localhost » (`0.0.0.0`). COLLER table interop : « localhost uniquement » pour le cerveau — vrai pour `:8090`, faux si on generalise au host-agent. |
| `README.md` vs `README.en.md` | Le FR raconte LFM2.5/Pocket/500 ms (21/08). L'EN raconte Granite/Magpie (19/09). Deux produits. `TAQUET-README-DEV.md` le dit deja. |
| WRAP soir 19/09 | « C3 JeV pas branche ; C4/C8 en attente ». Des OUT du 19 et 20/09 montrent C4, C8, puis le branchement JeV. Le WRAP est un instantane, pas une source. |

### 3.4 Decisions changees (ne plus raconter l'ancienne)

| Ancienne decision | Nouvelle | Ou c'est ecrit |
|---|---|---|
| Routeur d'escalade autonome (local vs MiniMax) | L'utilisateur decide ; le local repond pendant l'attente | `nights/2026-09-19-NOTE-JEV.md` |
| Cerveau Luth puis LFM2.5 | Granite 4.2 3B | `CARTE-FIGEE.md` |
| Oreille turbo | Whisper large-v3 | idem |
| Voix Pocket / Piper / Supertonic F5 | Magpie Sofia CUDA | idem |
| FR only | FR defaut + EN 0.1 (`HA_LANG=en`) | `README.en.md` ; `C8-EN-OUT.md` |
| Smart Turn v3 « prochain gain » | Toujours pas dans la carte 0.1 | `STATUS.md` vs `CARTE-FIGEE.md` |
| `make smoke` 9/9 = preuve de la carte | 9 sondes dont 2 heritages ; pas Magpie | `TAQUET-README-DEV.md` §8 |

### 3.5 Ce qui reste vrai dans les docs racine (pour ne pas tout jeter)

- Separation conteneur / host-agent, absence d'ALSA dans Docker Desktop Windows.
- Reservation GPU obligatoire dans Compose.
- Ports 8000 / 8001 / 8090 / 8091 (8092 Magpie s'est ajoute).
- GATE, audit sans secret (intention ADR-012).
- Principe « un outil absent du registre si la cle est vide ».
- Image ~32 Go, bind-mount `./models`.
- Machine cible RTX 4070 12 Go.

Ces points peuvent etre cites. Les tableaux de modeles et les 500 ms non.

---

## 4. Ordre de lecture pour ecrire (et rien d'autre)

Dix fichiers, dans cet ordre. Le reste de `nights/` est du bruit de
production.

1. `nights/2026-09-19-CARTE-FIGEE.md` — ce qui est le produit.
2. `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` — squelette, en barrant
   les phrases §3.3.
3. `nights/2026-09-20-TAQUET-BGB-COLLER.md` — cases du formulaire, en barrant
   « (MOTHER) ».
4. `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md` — correspondance case ↔ preuve.
5. `nights/2026-09-19-PROTOCOLE-DEGUSTATION.md` + `DEGUSTATION-CERVEAUX-RESULTATS.md` — methode et notes.
6. `nights/2026-09-19-C2-ALERTE.md` + `C1-OUTILS.md` — demos.
7. `nights/2026-09-20-TAQUET-PRODUIT-OUT.md` — contrastes.
8. `nights/2026-09-20-OUT-AUDIT-QUALITE-TESTS.md` — pour ne pas sur-vendre pytest.
9. `README.en.md` — seul racine a jour (perimetre EN, lanceur, feedback).
10. Le present fichier — pour les chiffres et les interdits.

`STACK.md` / `STATUS.md` / `README.md` / `ARCHITECTURE.md` : a lire seulement
comme **histoire du projet** (chapitre « ce que nous avons mesure en aout, et
pourquoi nous avons change »). Pas comme description du livrable.

---

## 5. Trous — formulation directe

Ce que le depot **n'a pas**, meme en creusant :

- Un memoire redige a la 1re personne.
- Un etat de l'art academique ou concurrentiel.
- Un WER % de Whisper large-v3 sur la voix de Thomas (le live est qualitatif :
  noms propres, nombres).
- Un round-trip unique de la stack 19/09 comparable au 500 ms d'aout (on a
  des etapes, pas la somme publiee).
- Une execution Camunda nocturne bout-en-bout consignee.
- Un tour vocal C1 vers Claude ou Codex consigne (cles chargees ≠ conversation).
- Un essai lecteur d'ecran.
- Une politique RGPD operationnelle (base legale, retention, effacement).
- Un fichier `LICENSE` du code.
- Des ADR sous forme de fichiers.
- Un README francais vrai.
- Des scores RICE numeriques.
- Une mesure fraiche de la taille d'image Docker (32,3 Go date du 21/08).

Ce que le depot **a**, et qui suffit a ne pas rendre une copie blanche :

- Une carte de modeles choisie a l'aveugle, datee, avec VRAM et latences live.
- Des bancs comparatifs oreille / voix / cerveau avec RTF et MiB.
- Une annexe C4 + flux + risques + T1–T7.
- Des blocs BC02 deja ecris (a signer, pas a inventer).
- Une demo C2 avec captures et millisecondes.
- Des contrastes WCAG mesures, pas declares.
- Un journal de production (`nights/`) qui prouve la methode, y compris
  quand un test est en trompe-l'oeil.

Le risque principal n'est pas le manque de matiere. C'est de recopier
`README.md` ou `STATUS.md` et d'ecrire 500 ms / Pocket / LFM2.5 a cote de
Granite / Magpie / 1,1 s.
)
