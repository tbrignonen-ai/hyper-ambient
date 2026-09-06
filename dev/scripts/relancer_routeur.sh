#!/usr/bin/env bash
# Relance le host-agent avec le routeur, sans sourcer .env.local en entier.
#
# Sourcer tout le fichier casse le cache Hugging Face : EARS ne retrouve plus
# large-v3-turbo et rapporte une taille de modele invalide. Seule la cle est lue
# du fichier ; le reste est pose ici, en clair, ou on peut le relire.
#
# Ce fichier doit rester en fins de ligne UNIX. Ecrit depuis Windows sans
# precaution il finit en CRLF, et bash refuse alors la premiere option qu'il lit.
set -eu
cd /workspace

# Le tr n'est pas decoratif : .env.local est edite sous Windows, ses lignes
# finissent en CRLF, et le retour chariot reste colle a la cle. L'en-tete
# Authorization devient alors illegal et les DEUX voies du routeur tombent, la
# locale comme la distante. Symptome : Illegal header value sur le Bearer.
BRAIN_API_KEY="$(grep -E '^BRAIN_API_KEY=' .env.local | head -1 | cut -d= -f2- | tr -d '\015')"
export BRAIN_API_KEY
export BRAIN_SERVICE=router
export BRAIN_API_ENDPOINT=https://api.commandcode.ai/provider/v1/chat/completions
export BRAIN_MODEL=MiniMaxAI/MiniMax-M3
export BRAIN_MODEL_LOCAL=mother-local

# estelle est la seule locutrice francaise native du catalogue Pocket
# (unmute-prod-website/developpeuse-3.wav). Toutes les autres voix dites
# francaises viennent de VCTK ou d Expresso, des corpus anglais : eponine, qui
# tenait ce poste, est VCTK p262, et son accent etait la locutrice, pas le
# modele. Retenue a l oreille par Thomas le 6 septembre 2026, avec le profil
# aurora — presque sec, presence a 3,4 kHz — la ou le profil mother pose une
# coque d ordinateur de bord qui assombrit et masculinise.
#
# La forme :- laisse la ligne de commande gagner : passer une autre voix ou un
# autre profil devant l appel suffit a l essayer.
export MOUTH_VOICE_NAME=${MOUTH_VOICE_NAME:-estelle}
export MOUTH_PROFILE=${MOUTH_PROFILE:-aurora}

echo "cle de ${#BRAIN_API_KEY} caracteres, routeur arme"
nohup python dev/scripts/serve_hostagent.py > /tmp/hostagent.log 2>&1 &
echo "host-agent relance, pid $!"
