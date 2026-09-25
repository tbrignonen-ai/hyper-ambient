"""Serveur MLX-LM épinglé, budget exact après template et avant inférence.

Le dépassement est rejeté, jamais tronqué : conserver les consignes système,
les outils et leurs résultats. Aucun import Metal avant main().
"""
from __future__ import annotations

from functools import wraps
from importlib.metadata import version

MLX_LM_VERSION = "0.31.3"
CONTEXT_TOKENS = 2048
OUTPUT_TOKENS = 512


def bounded_tokenize(original):
    @wraps(original)
    def tokenize(self, tokenizer, request, args):
        if type(args.max_tokens) is not int or args.max_tokens <= 0:
            raise ValueError("max_tokens doit être un entier strictement positif")
        args.max_tokens = min(args.max_tokens, OUTPUT_TOKENS)
        result = original(self, tokenizer, request, args)
        if not isinstance(result, tuple) or len(result) != 4:
            raise RuntimeError("Contrat de tokenisation MLX-LM incompatible")
        prompt = result[0]
        if len(prompt) + args.max_tokens > CONTEXT_TOKENS:
            raise ValueError(
                f"Contexte Mac dépassé : {len(prompt)} tokens d'entrée + "
                f"{args.max_tokens} de sortie > {CONTEXT_TOKENS}. "
                "Réduire l'historique, les outils ou le message."
            )
        return result

    return tokenize


def main():
    from native.macos.profile import require_platform

    require_platform()
    if version("mlx-lm") != MLX_LM_VERSION:
        raise RuntimeError(f"Le serveur Mac exige mlx-lm=={MLX_LM_VERSION}")
    from mlx_lm import server

    # Les chemins batch et single passent ici avant cache/prefill/génération.
    server.ResponseGenerator._tokenize = bounded_tokenize(server.ResponseGenerator._tokenize)
    server.main()


if __name__ == "__main__":
    main()
