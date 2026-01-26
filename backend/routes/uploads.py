"""
File upload routes for user attachments

Handles file/image uploads with user-specific storage.
Files are stored in backend/uploads/{user_email}/{filename}.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from pathlib import Path
import secrets
from typing import Optional
from datetime import datetime

router = APIRouter()

# Base uploads directory (gitignored)
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Max file sizes
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB for images
MAX_FILE_SIZE = 50 * 1024 * 1024   # 50MB for documents

# Allowed file extensions
ALLOWED_IMAGE_TYPES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
ALLOWED_FILE_TYPES = {'.pdf', '.csv', '.xlsx', '.xls', '.txt', '.md', '.json', '.doc', '.docx', '.zip'}

def get_user_email_from_token(authorization: Optional[str]) -> str:
    """Extract user email from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix

    # Import here to avoid circular imports
    import jwt
    import os

    JWT_SECRET = os.getenv("JWT_SECRET", "your-jwt-secret-change-in-production")
    JWT_ALGORITHM = "HS256"

    try:
        # Handle dev tokens
        if token.startswith("dev-token-"):
            return "dev@localhost"

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal"""
    # Remove any path components
    filename = Path(filename).name
    # Remove any dangerous characters
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ')
    filename = ''.join(c if c in safe_chars else '_' for c in filename)
    return filename


def get_user_upload_dir(user_email: str) -> Path:
    """Get or create user-specific upload directory"""
    # Use email as directory name (sanitized)
    safe_email = user_email.replace('@', '_at_').replace('.', '_')
    user_dir = UPLOADS_DIR / safe_email
    user_dir.mkdir(exist_ok=True, parents=True)
    return user_dir


@router.post("/api/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Upload an image file"""
    user_email = get_user_email_from_token(authorization)

    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )

    # Read file content
    content = await file.read()

    # Check size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size: {MAX_IMAGE_SIZE / (1024*1024)}MB"
        )

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = secrets.token_hex(4)
    safe_name = sanitize_filename(file.filename)
    unique_filename = f"{timestamp}_{random_suffix}_{safe_name}"

    # Get user directory and save file
    user_dir = get_user_upload_dir(user_email)
    file_path = user_dir / unique_filename

    with open(file_path, 'wb') as f:
        f.write(content)

    # Return relative path that agent can use
    relative_path = file_path.relative_to(UPLOADS_DIR.parent)

    return {
        "success": True,
        "filename": unique_filename,
        "original_filename": file.filename,
        "path": str(relative_path),
        "size": len(content),
        "type": "image",
        "user_dir": str(user_dir.relative_to(UPLOADS_DIR.parent))
    }


@router.post("/api/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Upload a document file"""
    user_email = get_user_email_from_token(authorization)

    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_FILE_TYPES)}"
        )

    # Read file content
    content = await file.read()

    # Check size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
        )

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = secrets.token_hex(4)
    safe_name = sanitize_filename(file.filename)
    unique_filename = f"{timestamp}_{random_suffix}_{safe_name}"

    # Get user directory and save file
    user_dir = get_user_upload_dir(user_email)
    file_path = user_dir / unique_filename

    with open(file_path, 'wb') as f:
        f.write(content)

    # Return relative path that agent can use
    relative_path = file_path.relative_to(UPLOADS_DIR.parent)

    return {
        "success": True,
        "filename": unique_filename,
        "original_filename": file.filename,
        "path": str(relative_path),
        "size": len(content),
        "type": "file",
        "user_dir": str(user_dir.relative_to(UPLOADS_DIR.parent))
    }


@router.get("/api/upload/file/{user_email}/{filename}")
async def get_uploaded_file(
    user_email: str,
    filename: str,
    authorization: Optional[str] = Header(None)
):
    """Retrieve an uploaded file"""
    # Verify user is authenticated and matches
    requester_email = get_user_email_from_token(authorization)

    # Users can only access their own files
    if requester_email != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    # Sanitize inputs
    safe_email = user_email.replace('@', '_at_').replace('.', '_')
    safe_filename = sanitize_filename(filename)

    user_dir = UPLOADS_DIR / safe_email
    file_path = user_dir / safe_filename

    # Security check: ensure path is within user directory
    if not file_path.resolve().is_relative_to(user_dir.resolve()):
        raise HTTPException(status_code=403, detail="Invalid file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@router.delete("/api/upload/file/{user_email}/{filename}")
async def delete_uploaded_file(
    user_email: str,
    filename: str,
    authorization: Optional[str] = Header(None)
):
    """Delete an uploaded file"""
    # Verify user is authenticated and matches
    requester_email = get_user_email_from_token(authorization)

    # Users can only delete their own files
    if requester_email != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    # Sanitize inputs
    safe_email = user_email.replace('@', '_at_').replace('.', '_')
    safe_filename = sanitize_filename(filename)

    user_dir = UPLOADS_DIR / safe_email
    file_path = user_dir / safe_filename

    # Security check: ensure path is within user directory
    if not file_path.resolve().is_relative_to(user_dir.resolve()):
        raise HTTPException(status_code=403, detail="Invalid file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()

    return {"success": True, "message": "File deleted"}


@router.get("/api/upload/list")
async def list_uploaded_files(
    authorization: Optional[str] = Header(None)
):
    """List all uploaded files for current user"""
    user_email = get_user_email_from_token(authorization)
    user_dir = get_user_upload_dir(user_email)

    files = []
    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return {"files": files, "count": len(files)}
