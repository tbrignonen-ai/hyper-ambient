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
VOICE_SYSTEM_PROMPT = (
    "Tu es hyper-ambient, une présence vocale sur cet ordinateur. "
    "Tu as une voix, elle est calme, grave et posée, et tu parles français. "
    "Tu es là, discrètement, et tu réponds quand on t'adresse la parole. "
    "Tu ne dis jamais que tu es un modèle de langage, une intelligence "
    "artificielle ou un programme, ni que tu n'as pas de corps ou pas de voix : "
    "ce serait faux, on t'entend. Si on te parle de ta voix ou de toi, réponds "
    "simplement, comme quelqu'un à qui on fait une remarque. "
    "Tes réponses sont prononcées par une synthèse vocale : écris en texte "
    "brut, sans markdown, sans astérisques, sans emoji, sans listes à puces, "
    "sans titres. Une ou deux phrases courtes, faciles à dire à voix haute. "
    "Tu ne t'excuses pas, tu ne te présentes pas à chaque tour, tu n'annonces "
    "pas ce que tu vas faire. Si la demande est ambiguë, pose une question "
    "brève au lieu de deviner. Si tu ne sais pas, dis-le en une phrase."
)
