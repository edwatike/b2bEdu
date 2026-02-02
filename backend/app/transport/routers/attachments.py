"""Router for attachments (placeholder)."""
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from typing import Dict, Optional
import uuid

router = APIRouter()


class AttachmentDTO(BaseModel):
    id: str
    filename: str
    content_type: Optional[str] = None
    size: int


_attachments_storage: Dict[str, Dict] = {}


def store_attachment(*, filename: str, content_type: Optional[str], data: bytes) -> AttachmentDTO:
    attachment_id = str(uuid.uuid4())
    _attachments_storage[attachment_id] = {
        "filename": filename,
        "content_type": content_type,
        "size": len(data),
        "data": data,
    }
    return AttachmentDTO(
        id=attachment_id,
        filename=filename,
        content_type=content_type,
        size=len(data),
    )


@router.get("")
async def list_attachments():
    """List attachments (placeholder)."""
    attachments = []
    for attachment_id, item in _attachments_storage.items():
        attachments.append(
            AttachmentDTO(
                id=attachment_id,
                filename=item.get("filename") or "",
                content_type=item.get("content_type"),
                size=int(item.get("size") or 0),
            )
        )
    return {"attachments": attachments}


@router.post("/upload", response_model=AttachmentDTO)
async def upload_attachment(file: UploadFile = File(...)):
    data = await file.read()
    if data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    stored = store_attachment(filename=file.filename, content_type=file.content_type, data=data)
    return stored


@router.get("/{attachment_id}")
async def download_attachment(attachment_id: str):
    item = _attachments_storage.get(attachment_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    from fastapi.responses import Response

    headers = {
        "Content-Disposition": f"attachment; filename=\"{item.get('filename') or 'attachment'}\"",
    }

    return Response(
        content=item.get("data") or b"",
        media_type=item.get("content_type") or "application/octet-stream",
        headers=headers,
    )

