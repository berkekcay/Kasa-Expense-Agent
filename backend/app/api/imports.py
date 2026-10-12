"""Bank / card statement upload (owner: track INGEST)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from app.auth import DB, CurrentUser
from app.config import get_settings
from app.schemas.imports import ImportResultOut
from app.services import statements

router = APIRouter(prefix="/imports", tags=["imports"])

STATEMENT_TYPES = {"text/csv", "application/vnd.ms-excel", "application/pdf", "text/plain"}
STATEMENT_EXTENSIONS = (".csv", ".txt", ".pdf")


@router.post("/statement", response_model=ImportResultOut, status_code=201)
async def upload_statement(file: UploadFile, db: DB, user_id: CurrentUser) -> ImportResultOut:
    """CSV or PDF statement -> inbox items (status pending) for the user to review.
    413 above settings.max_upload_bytes, 415 for other file types, 422 for unreadable files
    (no header row, scanned PDF without text, password-protected PDF), 503 for a PDF while
    no LLM provider is configured."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    filename = file.filename or "statement"
    if content_type not in STATEMENT_TYPES and not filename.lower().endswith(STATEMENT_EXTENSIONS):
        raise HTTPException(status_code=415, detail="upload a CSV or PDF statement")
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"file is larger than {limit // (1024 * 1024)} MB")
    result = await statements.import_statement(
        db, user_id, filename=filename, content_type=content_type, data=data
    )
    return ImportResultOut(
        lines=result.lines,
        created=result.created,
        duplicates=result.duplicates,
        skipped=result.skipped,
        errors=result.errors,
    )
