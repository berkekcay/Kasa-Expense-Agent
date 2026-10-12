"""Bank / card statement upload (owner: track INGEST)."""

from fastapi import APIRouter, UploadFile

from app.auth import DB, CurrentUser
from app.schemas.imports import ImportResultOut

router = APIRouter(prefix="/imports", tags=["imports"])

STATEMENT_TYPES = {"text/csv", "application/vnd.ms-excel", "application/pdf", "text/plain"}


@router.post("/statement", response_model=ImportResultOut, status_code=201)
async def upload_statement(file: UploadFile, db: DB, user_id: CurrentUser) -> ImportResultOut:
    """CSV or PDF statement -> inbox items (status pending) for the user to review.
    Limit the read to settings.max_upload_bytes (413 above it), 415 for other types."""
    raise NotImplementedError("POST /imports/statement: track INGEST")
