"""Shared voice I/O helpers (STT + TTS) used by both the web HTTP endpoints
(`routes/voice.py`) and the Telegram bot path (`telegram_bot/handlers.py`).

Keeping the OpenAI calls in one place means the web UI and Telegram voice notes
behave identically (same models, same voice/accent, same number-reading
instruction).

- STT: gpt-4o-mini-transcribe
- TTS: gpt-4o-mini-tts (voice "echo", Indian-English accent)
"""

from __future__ import annotations

import io
import logging
import os

import openai

logger = logging.getLogger(__name__)

# 25 MB OpenAI transcription cap.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
# OpenAI TTS input cap per call.
MAX_TTS_CHARS = 4096

DEFAULT_VOICE = "echo"
DEFAULT_SPEED = 1.25
_TTS_INSTRUCTIONS = (
    "Clear, professional tone. Indian English accent. "
    "Read financial numbers and stock tickers clearly."
)


def _client() -> openai.OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")
    return openai.OpenAI(api_key=api_key)


def transcribe_bytes(data: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio bytes to text via gpt-4o-mini-transcribe.

    `filename` only needs a correct extension hint for the API; Telegram voice
    notes are OGG/Opus (`.oga`/`.ogg`), which the API accepts natively.
    """
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Audio file too large. Maximum size is 25 MB.")

    audio_file = io.BytesIO(data)
    audio_file.name = filename or "audio.ogg"

    logger.info("[Voice STT] transcribing %s (%d bytes)", audio_file.name, len(data))
    text = _client().audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=audio_file,
        response_format="text",
    )
    # response_format="text" returns a bare string.
    return (text or "").strip()


def synthesize_bytes(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
    response_format: str = "mp3",
) -> bytes:
    """Synthesize a single chunk of text to speech, returning raw audio bytes.

    `text` must be <= MAX_TTS_CHARS; callers that need more should chunk first
    (the web endpoint does offset-based chunking; Telegram caps to one clip).
    `response_format`: "mp3" (web) or "opus" (Telegram voice notes — OGG/Opus).
    """
    if not text or not text.strip():
        raise ValueError("Text content is required")
    if len(text) > MAX_TTS_CHARS:
        raise ValueError(f"Text exceeds {MAX_TTS_CHARS} chars; chunk before synthesis")

    logger.info(
        "[Voice TTS] synthesizing %d chars (voice=%s speed=%s fmt=%s)",
        len(text),
        voice,
        speed,
        response_format,
    )
    response = _client().audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions=_TTS_INSTRUCTIONS,
        speed=speed,
        response_format=response_format,
    )
    return response.content
