"""
Voice I/O endpoints for Nifty Strategist
- Speech-to-text (STT) transcription using gpt-4o-mini-transcribe
- Text-to-speech (TTS) synthesis using gpt-4o-mini-tts
"""

import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import openai
import io

from services import voice as voice_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    """Request model for text-to-speech synthesis"""
    text: str
    voice: Optional[str] = "echo"  # Options: alloy, echo, fable, onyx, nova, shimmer
    speed: Optional[float] = 1.25  # 0.25 to 4.0
    chunk_size: Optional[int] = None  # Optional override for per-request chunking (max 4096)
    offset: Optional[int] = 0  # Character offset to start synthesis from


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio to text using OpenAI Whisper (gpt-4o-mini-transcribe).

    Accepts audio file in various formats (mp3, mp4, mpeg, mpga, m4a, wav, webm).
    Returns transcribed text.
    """
    try:
        audio_data = await audio.read()
        transcription = voice_service.transcribe_bytes(
            audio_data, filename=audio.filename or "audio.webm"
        )

        logger.info(f"[Voice STT] Transcription successful: {transcription[:100]}...")

        return {
            "status": "success",
            "text": transcription,
            "filename": audio.filename
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except openai.APIError as e:
        logger.error(f"[Voice STT] OpenAI API error: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        logger.error(f"[Voice STT] Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    Convert text to speech using OpenAI TTS (gpt-4o-mini-tts).

    Returns audio stream in MP3 format.
    """
    try:
        # Validate input
        if not request.text or len(request.text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Text content is required"
            )

        total_length = len(request.text)

        # Determine chunk configuration
        chunk_size = request.chunk_size or 4096
        if chunk_size <= 0:
            raise HTTPException(
                status_code=400,
                detail="Chunk size must be a positive integer."
            )

        # Cap chunk size to API constraints
        chunk_size = min(chunk_size, 4096)

        offset = request.offset or 0
        if offset < 0:
            raise HTTPException(
                status_code=400,
                detail="Offset must be zero or a positive integer."
            )
        if offset >= total_length:
            raise HTTPException(
                status_code=400,
                detail="Offset exceeds text length."
            )

        chunk_end = min(offset + chunk_size, total_length)
        chunk_text = request.text[offset:chunk_end]

        if not chunk_text:
            raise HTTPException(
                status_code=400,
                detail="No text available for synthesis with the provided offset and chunk size."
            )

        logger.info(
            "[Voice TTS] Synthesizing speech chunk: start=%d end=%d total=%d (voice=%s, speed=%s)",
            offset,
            chunk_end,
            total_length,
            request.voice,
            request.speed,
        )

        # Call OpenAI TTS via the shared service (mp3 for the web player).
        audio_content = voice_service.synthesize_bytes(
            chunk_text,
            voice=request.voice or voice_service.DEFAULT_VOICE,
            speed=request.speed or voice_service.DEFAULT_SPEED,
            response_format="mp3",
        )

        # Stream the audio response
        logger.info(f"[Voice TTS] Speech synthesis successful")

        # Convert response to bytes for streaming
        audio_bytes = io.BytesIO(audio_content)

        chunk_headers = {
            "Content-Disposition": "attachment; filename=speech.mp3",
            "Cache-Control": "no-cache",
            "X-Voice-Chunk-Start": str(offset),
            "X-Voice-Chunk-End": str(chunk_end),
            "X-Voice-Chunk-Size": str(chunk_size),
            "X-Voice-Total-Length": str(total_length),
            "X-Voice-Has-More": str(chunk_end < total_length).lower(),
        }

        if chunk_end < total_length:
            chunk_headers["X-Voice-Next-Offset"] = str(chunk_end)
        if chunk_size:
            chunk_index = offset // chunk_size if chunk_size else 0
            chunk_headers["X-Voice-Chunk-Index"] = str(chunk_index)

        return StreamingResponse(
            audio_bytes,
            media_type="audio/mpeg",
            headers=chunk_headers
        )

    except openai.APIError as e:
        logger.error(f"[Voice TTS] OpenAI API error: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")
    except HTTPException as e:
        # Re-raise HTTP exceptions to preserve their status codes/details
        raise e
    except Exception as e:
        logger.error(f"[Voice TTS] Synthesis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")
