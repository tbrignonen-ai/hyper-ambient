"""
MOUTH: voice character shaping — the MU/TH/UR treatment.

A neutral TTS voice does not read as a ship's computer. Two levers:

  1. Delivery, at synthesis time. Slower rate, flattened pitch variation and
     regularised phoneme durations make the reading unhurried and impersonal.
     These are Piper `SynthesisConfig` fields, not DSP.

  2. Space and grain, after synthesis. hyper-ambient speaks through a hull: band
     limiting, a short metallic room, a faint doubling.

Everything here is **stateful and streaming-safe**. Filters keep their `zi`
and the reverb keeps its buffers across calls, because MOUTH emits one chunk
per clause — a stateless implementation would click at every seam.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import signal


@dataclass
class VoiceProfile:
    """Delivery + treatment for one character."""

    # --- synthesis (Piper SynthesisConfig) ---
    length_scale: float = 1.0      # >1 speaks slower
    noise_scale: float = 0.667     # pitch/timbre variability; lower = flatter
    noise_w_scale: float = 0.8     # duration variability; lower = metronomic

    # --- delivery, backend-agnostic ---
    # `length_scale` ci-dessus n'existe que dans Piper. pocket-tts n'expose
    # aucun reglage de vitesse : `generate_audio_stream` ne prend que
    # `max_tokens` et `frames_after_eos`. Ralentir la voix sur ce backend passe
    # donc par un etirement temporel apres synthese, a hauteur conservee.
    time_stretch: float = 1.0      # >1 ralentit sans deplacer la hauteur

    # --- treatment ---
    highpass_hz: float = 0.0       # 0 disables
    lowpass_hz: float = 0.0
    reverb_mix: float = 0.0        # 0..1
    reverb_decay: float = 0.0      # 0..1, feedback amount
    double_ms: float = 0.0         # faint delayed copy, 0 disables
    double_mix: float = 0.0
    drive: float = 1.0             # pre-limiter gain
    presence_hz: float = 0.0       # peaking EQ, 0 disables
    presence_db: float = 0.0
    deess_hz: float = 0.0          # dipping EQ around sibilance, 0 disables
    deess_db: float = 0.0


# Neutral: whatever the voice does natively.
FLAT = VoiceProfile()

# MU/TH/UR 6000 — unhurried, level, speaking inside a metal room.
# Band limits are deliberately wide: a telephone band (300–3400) reads as
# "phone call", not "ship". Keeping lows to 90 Hz preserves the chest weight
# that makes it feel like it comes from the walls.
MOTHER = VoiceProfile(
    length_scale=1.16,
    # Pas d'etirement : essaye a 1.10 sur pocket-tts, la retouche s'entend
    # (vocodeur de phase applique par chunk). Le mecanisme reste disponible
    # dans VoiceTreatment, mais le profil ne s'en sert pas.
    time_stretch=1.0,
    noise_scale=0.45,
    noise_w_scale=0.55,
    highpass_hz=90.0,
    lowpass_hz=7200.0,
    reverb_mix=0.22,
    reverb_decay=0.62,
    double_ms=17.0,
    double_mix=0.16,
    drive=1.15,
)

# Colder and further away — for alerts rather than conversation.
MOTHER_ALERT = VoiceProfile(
    length_scale=1.08,
    noise_scale=0.35,
    noise_w_scale=0.45,
    highpass_hz=180.0,
    lowpass_hz=5200.0,
    reverb_mix=0.34,
    reverb_decay=0.72,
    double_ms=23.0,
    double_mix=0.22,
    drive=1.3,
)

# Aurora Ray — close-mic, soft, present. The opposite of the hull:
# no doubling, almost no reverb, keep air above 8 kHz, a little presence
# so a dark neural voice doesn't sit behind the listener.
AURORA = VoiceProfile(
    highpass_hz=70.0,
    lowpass_hz=12000.0,
    reverb_mix=0.05,
    reverb_decay=0.28,
    double_ms=0.0,
    double_mix=0.0,
    drive=1.0,
    presence_hz=3400.0,
    presence_db=2.5,
    deess_hz=7500.0,
    deess_db=-3.0,
)

PROFILES = {"flat": FLAT, "mother": MOTHER, "alert": MOTHER_ALERT, "aurora": AURORA}


def _peaking_sos(freq: float, q: float, gain_db: float, sample_rate: int) -> np.ndarray:
    """One biquad peaking section, SOS layout for sosfilt."""
    a_gain = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq / sample_rate
    alpha = np.sin(w0) / (2.0 * q)
    cosw = np.cos(w0)
    b0 = 1.0 + alpha * a_gain
    b1 = -2.0 * cosw
    b2 = 1.0 - alpha * a_gain
    a0 = 1.0 + alpha / a_gain
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha / a_gain
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)


class _Schroeder:
    """
    Small metallic room: 4 feedback combs in parallel, then 2 allpasses.

    Implemented as IIR sections rather than per-sample loops, because MOUTH's
    whole first-audio budget is ~100 ms and a Python sample loop would spend
    more than that on one clause. A feedback comb is exactly 1/(1 - g·z^-N)
    and an allpass (-g + z^-N)/(1 - g·z^-N), so `lfilter` does both in one
    vectorised call and `zi` carries the tail across chunks.
    """

    # Mutually non-commensurate delays, so the tail has no ringing pitch.
    # Two sets: running one per side gives a genuinely decorrelated tail.
    # Feeding the same tail to both channels would only widen the level, not
    # the image — it would still collapse to a point between the speakers.
    COMBS_MS = (29.7, 37.1, 41.1, 43.7)
    COMBS_MS_ALT = (31.3, 35.9, 39.7, 46.1)
    ALLPASS_MS = (5.0, 1.7)
    ALLPASS_MS_ALT = (6.3, 2.3)
    ALLPASS_G = 0.5

    def __init__(self, sample_rate: int, decay: float, variant: int = 0):
        g = float(np.clip(decay, 0.0, 0.95))
        combs_ms = self.COMBS_MS_ALT if variant else self.COMBS_MS
        allpass_ms = self.ALLPASS_MS_ALT if variant else self.ALLPASS_MS

        self._combs = []
        for ms in combs_ms:
            n = max(1, int(sample_rate * ms / 1000))
            b = np.zeros(1, dtype=np.float64)
            b[0] = 1.0
            a = np.zeros(n + 1, dtype=np.float64)
            a[0], a[n] = 1.0, -g
            self._combs.append([b, a, np.zeros(n, dtype=np.float64)])

        self._allpass = []
        for ms in allpass_ms:
            n = max(1, int(sample_rate * ms / 1000))
            ag = self.ALLPASS_G
            b = np.zeros(n + 1, dtype=np.float64)
            b[0], b[n] = -ag, 1.0
            a = np.zeros(n + 1, dtype=np.float64)
            a[0], a[n] = 1.0, -ag
            self._allpass.append([b, a, np.zeros(n, dtype=np.float64)])

    def process(self, x: np.ndarray) -> np.ndarray:
        acc = np.zeros_like(x, dtype=np.float64)
        for sec in self._combs:
            b, a, zi = sec
            y, sec[2] = signal.lfilter(b, a, x, zi=zi)
            acc += y
        acc /= len(self._combs)

        for sec in self._allpass:
            b, a, zi = sec
            acc, sec[2] = signal.lfilter(b, a, acc, zi=zi)

        return acc.astype(np.float32)


class VoiceTreatment:
    """Streaming post-processor. One instance per utterance stream."""

    def __init__(self, profile: VoiceProfile, sample_rate: int):
        self.p = profile
        self.sr = sample_rate

        self._sos = []
        nyq = sample_rate / 2.0
        if profile.highpass_hz > 0:
            self._sos.append(signal.butter(2, profile.highpass_hz / nyq, "highpass", output="sos"))
        if 0 < profile.lowpass_hz < nyq:
            self._sos.append(signal.butter(4, profile.lowpass_hz / nyq, "lowpass", output="sos"))
        if 0 < profile.presence_hz < nyq and profile.presence_db != 0.0:
            self._sos.append(_peaking_sos(profile.presence_hz, 1.4, profile.presence_db, sample_rate))
        if 0 < profile.deess_hz < nyq and profile.deess_db != 0.0:
            self._sos.append(_peaking_sos(profile.deess_hz, 2.2, profile.deess_db, sample_rate))
        self._zi = [signal.sosfilt_zi(s) * 0.0 for s in self._sos]

        self._reverb = (
            _Schroeder(sample_rate, profile.reverb_decay) if profile.reverb_mix > 0 else None
        )

        n_dbl = int(sample_rate * profile.double_ms / 1000) if profile.double_ms > 0 else 0
        self._dbl_tail = np.zeros(n_dbl, dtype=np.float32) if n_dbl else None

    def _etirer(self, x: np.ndarray) -> np.ndarray:
        """Allonge le signal sans deplacer la hauteur (vocodeur de phase).

        Contrairement a `transposer` plus bas, qui relit l'onde plus lentement
        et descend donc la hauteur avec la duree, on veut ici ralentir la
        diction *seule*. C'est exactement ce que fait un vocodeur de phase.

        Seul maillon non strictement continu de cette chaine : l'analyse
        travaille par fenetre, donc les bornes de chunk ne sont pas reconstruites
        a l'identique. Aux facteurs modestes vises (~1.1) le raccord reste sous
        le seuil audible ; a fort etirement il faudrait un recouvrement porte
        d'un chunk a l'autre.
        """
        import librosa

        # Une fenetre plus large que le chunk ne porte aucune information ;
        # librosa la comblerait de zeros et le raccord s'entendrait.
        n_fft = 1 << max(6, min(11, int(np.log2(x.size)) - 1))
        etire = librosa.effects.time_stretch(
            x.astype(np.float32), rate=1.0 / self.p.time_stretch, n_fft=n_fft
        )
        return etire.astype(np.float32)

    def process(self, pcm16: np.ndarray) -> np.ndarray:
        """Take int16 PCM, return int16 PCM.

        La longueur est conservee, sauf si le profil demande un `time_stretch`
        different de 1.0 — auquel cas la sortie est allongee d'autant.
        """
        if pcm16.size == 0:
            return pcm16
        x = pcm16.astype(np.float32) / 32768.0

        # Avant les filtres et la reverberation : l'etirement appartient a la
        # diction, la reverberation a la piece. Etirer apres reverberation
        # allongerait la queue du reflet, ce qui agrandit la salle au lieu de
        # ralentir la voix.
        if self.p.time_stretch != 1.0 and x.size >= 64:
            x = self._etirer(x)

        for i, sos in enumerate(self._sos):
            x, self._zi[i] = signal.sosfilt(sos, x, zi=self._zi[i])

        if self._dbl_tail is not None:
            n = len(self._dbl_tail)
            delayed = np.concatenate([self._dbl_tail, x[:-n]]) if n <= x.size else np.zeros_like(x)
            self._dbl_tail = x[-n:].copy() if n <= x.size else self._dbl_tail
            x = x + self.p.double_mix * delayed

        if self._reverb is not None:
            x = (1.0 - self.p.reverb_mix) * x + self.p.reverb_mix * self._reverb.process(x)

        x = np.tanh(x * self.p.drive) / np.tanh(self.p.drive)
        return np.clip(x * 32767.0, -32768, 32767).astype(np.int16)


# --- Transposition -----------------------------------------------------------
#
# Les seules voix Piper francaises exploitables sont claires : siwis et
# upmc-jessica mesurent 235 Hz de fondamentale, la ou hyper-ambient demande une
# voix grave et posee. Le corpus MLS proposait bien 56 locutrices dans la fenetre
# grave, mais son synthetiseur multi-locuteur s'est revele inexploitable — de 50 a
# 300 % d'erreur de transcription selon la locutrice. Descendre une voix native
# reste donc la seule route qui conserve un francais natif.
#
# On descend par reechantillonnage, pas par vocodeur de phase. C'est le procede le
# plus simple et il n'introduit aucun artefact : on relit l'onde plus lentement. Il
# deplace aussi les formants vers le grave, ce qui donne le corps sombre recherche,
# et il ralentit la diction — un defaut pour la plupart des usages, mais exactement
# ce que ce cahier des charges demande. L'allongement se compense en amont, en
# accelerant la synthese Piper d'autant.

def facteur_transposition(demi_tons: float) -> float:
    """Rapport de frequences correspondant a un intervalle en demi-tons."""
    return float(2.0 ** (demi_tons / 12.0))


def transposer(pcm16: np.ndarray, demi_tons: float) -> np.ndarray:
    """Transpose un bloc PCM 16 bits, sans changer sa frequence d'echantillonnage.

    Un intervalle negatif descend la voix et allonge le bloc dans le meme rapport.
    """
    if demi_tons == 0.0 or pcm16.size == 0:
        return pcm16

    facteur = facteur_transposition(demi_tons)
    cible = max(1, int(round(pcm16.size / facteur)))
    lu = np.interp(
        np.linspace(0.0, pcm16.size - 1, cible),
        np.arange(pcm16.size),
        pcm16.astype(np.float32),
    )
    return np.clip(lu, -32768, 32767).astype(np.int16)
