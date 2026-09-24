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


_UNITE = (
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
)
_DIZAINE = (
    "", "", "vingt", "trente", "quarante", "cinquante", "soixante",
    "soixante", "quatre-vingt", "quatre-vingt",
)
# Un chiffre en fin de fragment peut encore s'allonger (« 2 » → « 24 »).
_SUITE = r"(?=[\s,;:!?»”')\]]|\.(?:\s|$))"
_HEURE_MIN = re.compile(r"(?<!\d)(\d{1,2})h(\d{2})(?!\d)", re.IGNORECASE)
_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_ONES_EN = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS_EN = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
)
_POURCENT = re.compile(r"(?<!\d)(\d+)(?:([.,])(\d+))?[ \t]*%")
_DECIMAL = re.compile(r"(?<!\d)(\d+)([.,])(\d+)(?!\d)" + _SUITE)
_ENTIER = re.compile(r"(?<!\d)(\d+)(?!\d)" + _SUITE)


def _cardinal(n: int, feminin: bool = False) -> str:
    """Entier français, tirets de la réforme de 1990, jusqu'au million exclu."""
    n = int(n)
    if n < 0:
        return "moins " + _cardinal(-n, feminin)
    if n < 20:
        if n == 1 and feminin:
            return "une"
        return _UNITE[n]
    if n < 100:
        diz, unit = divmod(n, 10)
        if diz == 8 and unit == 0:
            return "quatre-vingts"
        if diz in (7, 9):
            base = "soixante" if diz == 7 else "quatre-vingt"
            reste = 10 + unit
            if reste == 11:
                return f"{base}-et-onze"
            return f"{base}-{_cardinal(reste, feminin)}"
        base = _DIZAINE[diz]
        if unit == 0:
            return base
        if unit == 1:
            return f"{base}-et-{_cardinal(1, feminin)}"
        return f"{base}-{_cardinal(unit, feminin)}"
    if n < 1000:
        cent, reste = divmod(n, 100)
        tete = "cent" if cent == 1 else f"{_cardinal(cent)} cent"
        if reste == 0:
            return tete + ("s" if cent > 1 else "")
        return f"{tete} {_cardinal(reste, feminin)}"
    if n < 1_000_000:
        mille, reste = divmod(n, 1000)
        tete = "mille" if mille == 1 else f"{_cardinal(mille)} mille"
        if reste == 0:
            return tete
        return f"{tete} {_cardinal(reste, feminin)}"
    return str(n)


def _heure_en_lettres(heures: str, minutes: str) -> str:
    h, m = int(heures), int(minutes)
    nom = _cardinal(h, feminin=True)
    unite = "heure" if h == 1 else "heures"
    if m == 0:
        return f"{nom} {unite}"
    return f"{nom} {unite} {_cardinal(m)}"


def _decimal_en_lettres(entier: str, frac: str) -> str:
    return f"{_cardinal(int(entier))} virgule {_cardinal(int(frac))}"


def _cardinal_en(n: int) -> str:
    n = int(n)
    if n < 0:
        return "minus " + _cardinal_en(-n)
    if n < 20:
        return _ONES_EN[n]
    if n < 100:
        diz, unit = divmod(n, 10)
        if unit == 0:
            return _TENS_EN[diz]
        return f"{_TENS_EN[diz]}-{_ONES_EN[unit]}"
    if n < 1000:
        cent, reste = divmod(n, 100)
        tete = f"{_ONES_EN[cent]} hundred"
        if reste == 0:
            return tete
        return f"{tete} {_cardinal_en(reste)}"
    if n < 1_000_000:
        mille, reste = divmod(n, 1000)
        tete = f"{_cardinal_en(mille)} thousand"
        if reste == 0:
            return tete
        return f"{tete} {_cardinal_en(reste)}"
    return str(n)


def _horloge_en(heures: str, minutes: str) -> str:
    h, m = int(heures), int(minutes)
    if m == 0:
        return f"{_cardinal_en(h)} o'clock"
    return f"{_cardinal_en(h)} {_cardinal_en(m)}"


def _nombres_en_anglais(text: str) -> str:
    def _rempl_heure(m: re.Match) -> str:
        return _horloge_en(m.group(1), m.group(2))

    def _rempl_pct(m: re.Match) -> str:
        if m.group(3) is not None:
            corps = f"{_cardinal_en(int(m.group(1)))} point {_cardinal_en(int(m.group(3)))}"
        else:
            corps = _cardinal_en(int(m.group(1)))
        return f"{corps} percent"

    def _rempl_dec(m: re.Match) -> str:
        return f"{_cardinal_en(int(m.group(1)))} point {_cardinal_en(int(m.group(3)))}"

    def _rempl_ent(m: re.Match) -> str:
        return _cardinal_en(int(m.group(0)))

    text = _HEURE_MIN.sub(_rempl_heure, text)
    text = _CLOCK.sub(_rempl_heure, text)
    text = _POURCENT.sub(_rempl_pct, text)
    text = _DECIMAL.sub(_rempl_dec, text)
    text = _ENTIER.sub(_rempl_ent, text)
    return text


def nombres_en_lettres(text: str) -> str:
    """Verbalise les nombres d'un fragment, sans dépendre de la fin de chaîne.

    FR par défaut. ``HA_LANG=en`` : heures 15h30 / 3:30, pourcents, décimaux.
    Un entier ou un décimal collé en fin de fragment reste en chiffres.
    """
    if not text:
        return text

    from src.i18n import langue

    if langue() == "en":
        return _nombres_en_anglais(text)

    def _rempl_heure(m: re.Match) -> str:
        return _heure_en_lettres(m.group(1), m.group(2))

    def _rempl_pct(m: re.Match) -> str:
        if m.group(3) is not None:
            corps = _decimal_en_lettres(m.group(1), m.group(3))
        else:
            corps = _cardinal(int(m.group(1)))
        return f"{corps} pour cent"

    def _rempl_dec(m: re.Match) -> str:
        return _decimal_en_lettres(m.group(1), m.group(3))

    def _rempl_ent(m: re.Match) -> str:
        return _cardinal(int(m.group(0)))

    text = _HEURE_MIN.sub(_rempl_heure, text)
    text = _POURCENT.sub(_rempl_pct, text)
    text = _DECIMAL.sub(_rempl_dec, text)
    text = _ENTIER.sub(_rempl_ent, text)
    return text


# La consigne précédente disait « un assistant vocal conversationnel » et rien
# de plus. Sans identité, le modèle retombait sur ses réflexes de robot de
# service : à quelqu'un qui lui trouvait un accent, il a répondu « je n'ai pas
# d'accent car je suis un modèle de langage sans forme physique ni voix » —
# alors qu'il parlait, à voix haute, avec une voix. C'est exactement ce qui
# casse l'illusion de présence que le produit cherche.
# Depuis le 24/09, le distant lit le même fichier de conversation que le local.
from src.brain.local_prompt import LOCAL_SYSTEM_PROMPT as VOICE_SYSTEM_PROMPT  # noqa: E402
