.PHONY: build up down shell logs test smoke models models-voice models-brain llama whisper demo clean

# --- container lifecycle ---------------------------------------------------
build:            ## rebuild image (layers below torch are cache-hits)
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

shell:
	docker exec -it mother-core-dev bash

logs:
	docker compose logs -f

# --- verification ----------------------------------------------------------
smoke:            ## run every capability once, print real measurements
	docker exec -it mother-core-dev python3 dev/scripts/smoke_test.py

test:
	docker exec -it mother-core-dev python3 -m pytest dev/tests -v

gpu:
	docker exec -it mother-core-dev nvidia-smi

# --- models ----------------------------------------------------------------
models:           ## VAD + Piper + whisper turbo & large-v3 + Magpie Sofia (~6 GB)
	docker exec -it mother-core-dev bash dev/scripts/fetch_models.sh core

models-voice:     ## Magpie Sofia only (NeMo-Speech.cpp + GGUF)
	docker exec -it mother-core-dev bash dev/scripts/fetch_models.sh voice

models-brain:     ## Granite 4.2 3B GGUF for llama-server (~2.2 GB)
	docker exec -it mother-core-dev bash dev/scripts/fetch_models.sh brain

# --- local services --------------------------------------------------------
llama:            ## BRAIN local — llama-server on :8090 (host)
	docker exec -it mother-core-dev bash dev/scripts/serve_llama.sh

whisper:          ## EARS local — whisper-server on :8091 (host)
	docker exec -it mother-core-dev bash dev/scripts/serve_whisper.sh

# --- pipeline --------------------------------------------------------------
demo:             ## end-to-end BRAIN -> MOUTH with latency breakdown
	docker exec -it mother-core-dev python3 dev/scripts/pipeline_demo.py \
		--text "Explique-moi en deux phrases ce qu'est un facteur temps réel."

demo-local:       ## same, forced onto local llama.cpp
	docker exec -it -e BRAIN_SERVICE=llamacpp mother-core-dev \
		python3 dev/scripts/pipeline_demo.py \
		--text "Explique-moi en deux phrases ce qu'est un facteur temps réel."

clean:
	docker compose down -v
