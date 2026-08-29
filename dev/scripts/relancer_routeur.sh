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

echo "cle de ${#BRAIN_API_KEY} caracteres, routeur arme"
nohup python dev/scripts/serve_hostagent.py > /tmp/hostagent.log 2>&1 &
echo "host-agent relance, pid $!"
