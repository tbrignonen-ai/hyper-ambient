FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# numpy 2.5, scipy 1.18 and librosa 1.0 require Python >= 3.12.
# Jammy stops at 3.11, and the deadsnakes archive is not reachable from every
# network, so this pins a CPython standalone build.
ARG PYTHON_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only.tar.gz
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    ca-certificates \
    build-essential \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    sox \
    && curl -fsSL "$PYTHON_URL" -o /tmp/python.tar.gz \
    && tar -xzf /tmp/python.tar.gz -C /usr/local \
    && rm /tmp/python.tar.gz \
    && /usr/local/python/bin/python3 -m pip install --upgrade pip setuptools wheel \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/usr/local/python/bin:${PATH}

WORKDIR /workspace

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# ---------------------------------------------------------------------------
# Everything below is appended AFTER the heavy layers above, so rebuilds reuse
# the CUDA base image and the torch install from cache (no re-download).
# ---------------------------------------------------------------------------

# Build toolchain for llama.cpp / whisper.cpp
RUN apt-get update && apt-get install -y \
    cmake \
    ccache \
    pkg-config \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# --- llama.cpp (CUDA, sm_89 = Ada Lovelace / RTX 4070) ---------------------
# Provides llama-server: OpenAI-compatible /v1/chat/completions with SSE.
# BRAIN talks the same protocol locally and remotely.
ARG CUDA_ARCH=89
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp /opt/llama.cpp && \
    cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \
        -DGGML_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCH} \
        -DLLAMA_CURL=ON \
        -DLLAMA_BUILD_TESTS=OFF \
        -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /opt/llama.cpp/build --config Release -j"$(nproc)" && \
    cmake --install /opt/llama.cpp/build --prefix /usr/local && \
    rm -rf /opt/llama.cpp/build/CMakeFiles

# --- whisper.cpp (CUDA) ----------------------------------------------------
# GGUF ASR path: whisper-cli / whisper-server, same ggml runtime as llama.cpp.
RUN git clone --depth 1 https://github.com/ggml-org/whisper.cpp /opt/whisper.cpp && \
    cmake -S /opt/whisper.cpp -B /opt/whisper.cpp/build \
        -DGGML_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCH} \
        -DWHISPER_BUILD_TESTS=OFF \
        -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /opt/whisper.cpp/build --config Release -j"$(nproc)" && \
    cmake --install /opt/whisper.cpp/build --prefix /usr/local && \
    rm -rf /opt/whisper.cpp/build/CMakeFiles

ENV LD_LIBRARY_PATH=/usr/local/lib:${LD_LIBRARY_PATH}

# --- Python extras (ASR / VAD / TTS / acoustics) ---------------------------
COPY requirements-extra.txt .
RUN pip install -r requirements-extra.txt

ENV HF_HOME=/workspace/models/hf-cache \
    LLAMA_CACHE=/workspace/models/gguf

EXPOSE 8000 8001 8080 8081

CMD ["/bin/bash"]
