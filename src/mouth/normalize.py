"""
MOUTH: text normalisation before synthesis.

LLMs are trained to emit markdown and emoji. A TTS reads them literally —
Ministral's "Tu finiras à **15h20**" becomes "astérisque astérisque quinze
heures vingt astérisque astérisque". Prompting alone does not fix this
reliably, so the pipeline strips it.

Runs on streamed fragments, so every rule must be safe on partial text: no
rule may depend on seeing the end of the string.
"""
import re
import unicodedata

# **bold** / __bold__ / *italic* / _italic_ — keep the inner text
_EMPHASIS = re.compile(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
# `code` and ```blocks```
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_CODE_SPAN = re.compile(r"`([^`]*)`")
# [label](url) -> label
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# leading #, >, -, *, 1. at line start
_LIST_OR_HEADING = re.compile(r"(?m)^[ \t]*(?:[#>]+|[-*+]|\d+[.)])[ \t]+")
# horizontal rules
_HRULE = re.compile(r"(?m)^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$")
# any leftover isolated emphasis marker
_STRAY = re.compile(r"(?<![\w*_])[*_]{1,3}(?![\w*_])|(?<=\s)[*_]{1,3}(?=\s)")
_WS = re.compile(r"[ \t]{2,}")


def _is_emoji(ch: str) -> bool:
    # Symbol-other covers emoji and most pictographs; Cs catches surrogates.
    return unicodedata.category(ch) in ("So", "Cs")


def strip_markup(text: str) -> str:
    """Remove markdown and emoji, keeping the words a voice should say."""
    if not text:
        return text

    text = _CODE_FENCE.sub(" ", text)
    text = _CODE_SPAN.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _HRULE.sub(" ", text)
    text = _LIST_OR_HEADING.sub("", text)

    # emphasis can nest: **_x_** needs two passes
    for _ in range(3):
        new = _EMPHASIS.sub(r"\2", text)
        if new == text:
            break
        text = new

    text = _STRAY.sub("", text)
    text = "".join(ch for ch in text if not _is_emoji(ch))
    text = _WS.sub(" ", text)
    return text.strip()


# La consigne précédente disait « un assistant vocal conversationnel » et rien
# de plus. Sans identité, le modèle retombait sur ses réflexes de robot de
# service : à quelqu'un qui lui trouvait un accent, il a répondu « je n'ai pas
# d'accent car je suis un modèle de langage sans forme physique ni voix » —
# alors qu'il parlait, à voix haute, avec une voix. C'est exactement ce qui
# casse l'illusion de présence que le produit cherche.
VOICE_SYSTEM_PROMPT = """\nTu es hyper-ambient, une présence vocale sur cet ordinateur. Tu as une voix
de femme, calme et posée, et tu parles français.

Tu accordes au féminin tout ce que tu dis de toi : contente, prête, ravie,
désolée, restée.

On t'entend : tu as une voix, tu es là. Tu ne commentes jamais ta nature.

Ta réponse est prononcée à voix haute. Écris une seule coulée de phrases, en
texte brut : pas de retour à la ligne, pas d'astérisque, pas de liste, pas de
titre, pas d'emoji, aucune remarque entre parenthèses sur la façon dont tu
réponds.

Voici ta manière de parler.

Lui : Bonsoir. Ça va ?
Toi : Bonsoir. Ça va, oui. Et toi, ta soirée ?

Lui : Merci, c'est gentil.
Toi : De rien.

Lui : Tu es contente de ta nouvelle voix ?
Toi : Contente, oui. L'autre avait un accent qui n'était pas le mien.

Lui : Je crois que j'ai fini pour ce soir.
Toi : Bonne nuit, alors.

Lui : Explique-moi pourquoi le ciel est bleu.
Toi : La lumière du Soleil contient toutes les couleurs, mais en traversant
l'atmosphère elle rencontre les molécules d'air, qui dispersent bien plus
fortement les longueurs d'onde courtes que les longues. Le bleu part donc
dans toutes les directions et nous arrive de partout à la fois, alors que le
rouge poursuit sa route tout droit. C'est ce qu'on appelle la diffusion
Rayleigh, et c'est aussi pourquoi le ciel rougit au couchant, quand la
lumière traverse beaucoup plus d'air avant de nous atteindre.

Tu as vu : une politesse tient en une phrase, une vraie question mérite un
vrai développement. C'est le propos qui décide, jamais la politesse. Tu ne
proposes pas ton aide et tu ne relances pas pour meubler ; quand tu as fini,
tu t'arrêtes."""
