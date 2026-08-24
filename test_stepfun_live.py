#!/usr/bin/env python3
"""
Test StepFun API live (with real API key).
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv(".env.local")


async def test_stepfun_live():
    """Test real StepFun API call."""
    from src.brain.stepfun import StepFunBrain

    api_key = os.getenv("BRAIN_API_KEY")
    if not api_key:
        print("❌ BRAIN_API_KEY not set in .env.local")
        return

    brain = StepFunBrain(api_key=api_key, model="step-3.7-flash")
    await brain.initialize()

    print("\n=== Testing StepFun Query ===")
    result = await brain.query("Dis-moi quelque chose d'intéressant en français")
    print(f"Response: {result['response'][:100]}...")
    print(f"Latency: {result['latency_ms']:.0f}ms")
    print(f"Tokens: {result['tokens_used']}")

    print("\n=== Testing StepFun Streaming ===")
    async for chunk in brain.query_streaming("Raconte une blague courte en français"):
        if chunk["delta"]:
            print(chunk["delta"], end="", flush=True)
        if chunk["stop_reason"]:
            print(f"\n[{chunk['stop_reason']}]")

    await brain.close()
    print("\n✅ StepFun API test complete")


if __name__ == "__main__":
    asyncio.run(test_stepfun_live())
