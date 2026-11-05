"""Bank / card statement upload (owner: track INGEST)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.agents import require_agents
from app.api.integrations import sync_out
from app.auth import DB, CurrentUser
from app.config import get_settings
from app.schemas.imports import ImportResultOut
from app.schemas.integrations import SyncResultOut
from app.services import mail_sync, statements

router = APIRouter(prefix="/imports", tags=["imports"])

STATEMENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
STATEMENT_EXTENSIONS = (".csv", ".txt", ".pdf", ".xlsx")


@router.post("/statement", response_model=ImportResultOut, status_code=201)
async def upload_statement(file: UploadFile, db: DB, user_id: CurrentUser) -> ImportResultOut:
    """CSV, Excel (.xlsx, first sheet) or PDF statement -> inbox items (status pending) for the user to review.
    413 above settings.max_upload_bytes, 415 for other file types, 422 for unreadable files
    (no header row, scanned PDF without text, password-protected PDF), 503 for a PDF while
    no LLM provider is configured."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    filename = file.filename or "statement"
    if content_type not in STATEMENT_TYPES and not filename.lower().endswith(STATEMENT_EXTENSIONS):
        raise HTTPException(status_code=415, detail="upload a CSV, Excel (.xlsx) or PDF statement")
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


@router.post("/email", response_model=SyncResultOut, status_code=201, dependencies=[Depends(require_agents)])
async def upload_email(file: UploadFile, user_id: CurrentUser) -> SyncResultOut:
    """One email saved as an .eml file (in Gmail: More > Download message) -> an inbox item to
    review, read by the same parser as synced mail. 413 above settings.mail_max_upload_bytes,
    415 for other files, 503 while no LLM provider is configured."""
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not filename.endswith(".eml") and content_type != "message/rfc822":
        raise HTTPException(status_code=415, detail="upload an email saved as an .eml file")
    limit = get_settings().mail_max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"file is larger than {limit // 1_000_000} MB")
    return sync_out(await mail_sync.import_file(user_id, data))
