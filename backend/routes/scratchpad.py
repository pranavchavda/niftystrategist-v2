"""
API routes for scratchpad functionality.
Uses DB-backed ScratchpadDB (replaces file-based Scratchpad).
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional

from services.scratchpad_db import ScratchpadDB
from routes.uploads import get_user_email_from_token

router = APIRouter()


class ScratchpadEntry(BaseModel):
    content: str


@router.get("/api/scratchpad/{thread_id}", response_model=List[dict])
async def get_scratchpad_entries(thread_id: str, authorization: Optional[str] = Header(None)):
    """Get all scratchpad entries for a given thread."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = ScratchpadDB(thread_id)
        return await scratchpad.get_entries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/scratchpad/{thread_id}")
async def add_scratchpad_entry(thread_id: str, entry: ScratchpadEntry, authorization: Optional[str] = Header(None)):
    """Add a new entry to the scratchpad for a given thread. Returns the created entry."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = ScratchpadDB(thread_id)
        new_entry = await scratchpad.add_entry(entry.content, author=user_email)
        return new_entry
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/scratchpad/{thread_id}/{entry_id}")
async def update_scratchpad_entry(thread_id: str, entry_id: int, entry: ScratchpadEntry, authorization: Optional[str] = Header(None)):
    """Update an existing scratchpad entry by id."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = ScratchpadDB(thread_id)
        updated = await scratchpad.update_entry(entry_id, entry.content)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/scratchpad/{thread_id}/{entry_id}")
async def delete_scratchpad_entry(thread_id: str, entry_id: int, authorization: Optional[str] = Header(None)):
    """Delete a scratchpad entry by id."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = ScratchpadDB(thread_id)
        await scratchpad.delete_entry(entry_id)
        return {"success": True, "message": "Entry deleted."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
