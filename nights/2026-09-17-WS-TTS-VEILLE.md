# 2026-09-17 — WS TTS VEILLE (FR femme lente / Aura-like)

**Brief:** nouveaux TTS FR (femme lente, calme, Aura-like) · local ≤VRAM MOTHER (~12 Go GPU, Luciole live) ou distant léger.  
**Auteur:** WS · **Date:** 2026-09-17 · **Pas d'impl.**

## Top 5 candidats

| # | Candidat | Liens | Taille / VRAM | Pourquoi |
|---|---|---|---|---|
| 1 | **NeuTTS Nano French** | HF: https://huggingface.co/neuphonic/neutts-nano-french · Q4 GGUF: https://huggingface.co/neuphonic/neutts-nano-french-q4-gguf · Q8: https://huggingface.co/neuphonic/neutts-nano-french-q8-gguf · GitHub: https://github.com/neuphonic/neutts | ~0.2B (~117M actifs) · Q4 CPU/edge · ~0 VRAM GPU | FR-only + **clone 3–15 s**. Chemin Aura: ref WAV femme lente/calme. Coexiste avec Luciole/Occamy. |
| 2 | **Qwen3-TTS VoiceDesign 1.7B** | HF: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign · ModelScope: `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` · docs: https://github.com/QwenLM/Qwen3-TTS | ~1.7B · ~4–6 Go FP16 (+tokenizer) | Instruct NL → *« voix femme FR, lente, douce, posée »* = plus proche **Aura-by-prompt**. FR natif (10 langues). Si VRAM serrée: Base 0.6B + clone ref. |
| 3 | **Orpheus-3B French FT — Amélie** | GGUF: https://huggingface.co/lex-au/Orpheus-3b-French-FT-Q8_0.gguf · FastAPI: https://github.com/Lex-au/Orpheus-FastAPI · base: CanopyLabs FR FT | 3B Q8 ~3–4 Go (Q4/Q2 plus légers) | Voix **`amelie`** (élégante FR) + tags émotion. `marie` = moins fiable. Qualité « conversation » vs Kokoro. |
| 4 | **Chatterbox TTS French** (Thomcles) | https://huggingface.co/Thomcles/Chatterbox-TTS-French · GGUF multi: https://huggingface.co/cstr/chatterbox-GGUF | ~0.5B stack · T3+S3 Q8 ~0.9 Go | Fine-tune ~1400 h FR (Emilia). Clone ref → caler tempo lent. Upstream multilangue aussi `-l fr`. |
| 5 | **Fun-CosyVoice3 0.5B** | https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 · famille CosyVoice3 / CosyVoice-300M | ~0.5B · ~1–2 Go | FR + **zero-shot clone**. Léger vs 1.7B. Option distant légère si on évite GPU local. |

## Hors top (déjà souvent testés / moins « nouveau »)

- Kokoro `ff_siwis` / Piper `fr_FR-siwis-*` — même lignée SIWIS, très léger, peu de « coup de foudre » probable.
- Qwen3 CustomVoice presets: **aucune voix FR native** (Serena/Vivian = ZH).

## Ordre de test recommandé (VRAM 12 Go + Luciole)

1. NeuTTS Nano FR + ref Aura-like  
2. Orpheus Amélie Q4/Q8  
3. Qwen3 VoiceDesign si ~5 Go libres  

## Sources (post X / pages)

- NeuTTS: https://huggingface.co/neuphonic/neutts-nano-french  
- Qwen3-TTS: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign · https://github.com/QwenLM/Qwen3-TTS  
- Orpheus FR: https://huggingface.co/lex-au/Orpheus-3b-French-FT-Q8_0.gguf  
- Chatterbox FR: https://huggingface.co/Thomcles/Chatterbox-TTS-French  
- CosyVoice3: https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512  