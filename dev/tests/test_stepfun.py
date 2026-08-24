"""
Test StepFun LLM integration.
"""
import pytest
import os


@pytest.mark.asyncio
async def test_stepfun_init():
    """Test StepFun initialization."""
    from src.brain.stepfun import StepFunBrain

    # Test without API key (stub mode)
    brain = StepFunBrain(api_key="dummy-key")
    await brain.initialize()

    # Query in stub mode
    result = await brain.query("Hello")
    assert result is not None
    assert "response" in result

    await brain.close()


@pytest.mark.asyncio
async def test_stepfun_query_stub():
    """Test StepFun query (stub mode, no client initialized)."""
    from src.brain.stepfun import StepFunBrain

    # Create brain but don't initialize (keeps client None = stub mode)
    brain = StepFunBrain(api_key="dummy")
    # Skip initialize to stay in stub mode

    result = await brain.query("Dis-moi une blague en français")
    assert result is not None
    assert result["stop_reason"] == "stub"


@pytest.mark.asyncio
async def test_stepfun_streaming_stub():
    """Test StepFun streaming (stub mode)."""
    from src.brain.stepfun import StepFunBrain

    # Create brain but don't initialize (keeps client None = stub mode)
    brain = StepFunBrain(api_key="dummy")
    # Skip initialize to stay in stub mode

    chunks = []
    async for chunk in brain.query_streaming("Conte-moi une histoire"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert chunks[0]["stop_reason"] == "stub"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
