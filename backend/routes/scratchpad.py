"""
API routes for scratchpad functionality.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional

from tools.native.scratchpad import Scratchpad
from routes.uploads import get_user_email_from_token

router = APIRouter()

class ScratchpadEntry(BaseModel):
    content: str

@router.get("/api/scratchpad/{thread_id}", response_model=List[dict])
async def get_scratchpad_entries(thread_id: str, authorization: Optional[str] = Header(None)):
    """Get all scratchpad entries for a given thread."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = Scratchpad(thread_id)
        return scratchpad.get_entries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/scratchpad/{thread_id}")
async def add_scratchpad_entry(thread_id: str, entry: ScratchpadEntry, authorization: Optional[str] = Header(None)):
    """Add a new entry to the scratchpad for a given thread."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = Scratchpad(thread_id)
        scratchpad.add_entry(entry.content, author=user_email)
        return {"success": True, "message": "Entry added to scratchpad."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/scratchpad/{thread_id}/{entry_index}")
async def update_scratchpad_entry(thread_id: str, entry_index: int, entry: ScratchpadEntry, authorization: Optional[str] = Header(None)):
    """Update an existing scratchpad entry."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = Scratchpad(thread_id)
        scratchpad.update_entry(entry_index, entry.content)
        return {"success": True, "message": "Entry updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/scratchpad/{thread_id}/{entry_index}")
async def delete_scratchpad_entry(thread_id: str, entry_index: int, authorization: Optional[str] = Header(None)):
    """Delete a scratchpad entry."""
    user_email = get_user_email_from_token(authorization)
    try:
        scratchpad = Scratchpad(thread_id)
        scratchpad.delete_entry(entry_index)
        return {"success": True, "message": "Entry deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
