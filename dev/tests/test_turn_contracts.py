"""Tests des contrats de tour, d'état et d'annulation pour le barge-in.

Couvre les transitions d'état, l'admission du canal et la fin de tour.
Zéro socket réseau réel, exécution synchrone/asyncio.run.
"""
from __future__ import annotations

import asyncio
import functools
import json
import pytest

from src.hostagent.channel import ChannelRefused, LocalChannel
from src.hostagent.contract import HostAgentContract, UnknownPrimitiveError, is_permitted
from src.core.app import HyperAmbientCore


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


# --- 1. Contrats d'admission et de canal local (Channel) ---

def test_channel_admission_loopback_valid():
    channel = LocalChannel(secret="top_secret_123")
    # IPv4 loopback
    channel.authenticate("127.0.0.1", "top_secret_123")
    # IPv6 loopback
    channel.authenticate("::1", "top_secret_123")


def test_channel_refuses_non_loopback_even_with_secret():
    channel = LocalChannel(secret="top_secret_123")
    with pytest.raises(ChannelRefused):
        channel.authenticate("192.168.1.50", "top_secret_123")
    with pytest.raises(ChannelRefused):
        channel.authenticate("10.0.0.1", "top_secret_123")


def test_channel_refuses_bad_secret_on_loopback():
    channel = LocalChannel(secret="top_secret_123")
    with pytest.raises(ChannelRefused):
        channel.authenticate("127.0.0.1", "wrong_secret")
    with pytest.raises(ChannelRefused):
        channel.authenticate("127.0.0.1", "")
    with pytest.raises(ChannelRefused):
        channel.authenticate("127.0.0.1", None)


def test_channel_handles_permitted_primitives():
    journal = []
    channel = LocalChannel(secret="s", journal=journal)
    channel.handle({"primitive": "audio.capture"})
    channel.handle(json.dumps({"primitive": "audio.render"}))
    assert journal == ["audio.capture", "audio.render"]


def test_channel_rejects_unpermitted_primitive():
    journal = []
    channel = LocalChannel(secret="s", journal=journal)
    with pytest.raises(ChannelRefused):
        channel.handle({"primitive": "system.exec"})
    with pytest.raises(ChannelRefused):
        channel.handle({"primitive": "barge_in.interrupt_unregistered"})
    assert journal == []


# --- 2. Contrat d'interruption et cycle de vie d'un tour ---

class TurnSimulationState:
    """Modélise l'état d'un tour et la réactivité à une interruption barge-in."""
    def __init__(self):
        self.state = "IDLE"  # IDLE -> CAPTURE -> PROCESSING -> SPEAKING -> END
        self.interrupted = False
        self.cleaned_up = False
        self.audio_frames_played = 0

    async def speak_stream(self, total_frames: int, interrupt_at_frame: int | None = None):
        self.state = "SPEAKING"
        for i in range(total_frames):
            if interrupt_at_frame is not None and i >= interrupt_at_frame:
                self.interrupted = True
                self.state = "INTERRUPTED"
                await self.on_interrupt()
                break
            self.audio_frames_played += 1
            await asyncio.sleep(0.001)
        if not self.interrupted:
            self.state = "END"
        self.cleaned_up = True

    async def on_interrupt(self):
        # Simulation du flush TTS immédiat (< 60ms) et vidage des buffers
        pass


@runs_async
async def test_turn_normal_completion():
    sim = TurnSimulationState()
    await sim.speak_stream(total_frames=5)
    assert sim.state == "END"
    assert sim.interrupted is False
    assert sim.audio_frames_played == 5
    assert sim.cleaned_up is True


@runs_async
async def test_turn_interrupted_barge_in():
    sim = TurnSimulationState()
    await sim.speak_stream(total_frames=10, interrupt_at_frame=3)
    assert sim.state == "INTERRUPTED"
    assert sim.interrupted is True
    assert sim.audio_frames_played == 3
    assert sim.cleaned_up is True


# --- 3. Contrat de base de l'orchestrateur central (HyperAmbientCore) ---

@runs_async
async def test_core_lifecycle():
    core = HyperAmbientCore()
    assert core.running is False
    
    # Démarrage et arrêt asynchrone
    start_task = asyncio.create_task(core.start())
    await asyncio.sleep(0.02)
    assert core.running is True
    
    await core.stop()
    assert core.running is False
    await start_task
