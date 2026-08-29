#!/bin/bash
set -e
python -c "import qwen_tts; print('qwen_tts deja la')" 2>/dev/null && exit 0
pip install -q qwen-tts
python -c "import qwen_tts; print('qwen_tts OK', qwen_tts.__file__)"
