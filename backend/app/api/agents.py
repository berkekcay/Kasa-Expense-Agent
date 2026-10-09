"""Agent-backed endpoints: receipt upload and chat. They return 503 without GOOGLE_API_KEY."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from google.genai import types

from app.agents import runtime
from app.auth import DB, CurrentUser
from app.schemas import ChartSpec, ChatIn, ChatOut, ExpenseOut, ReceiptOut
from app.services import expenses as expense_service

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def require_agents() -> None:
    try:
        runtime.ensure_available()
    except runtime.AgentsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


router = APIRouter(tags=["agents"], dependencies=[Depends(require_agents)])


@router.post("/receipts", response_model=ReceiptOut, status_code=201)
async def upload_receipt(file: UploadFile, db: DB, user_id: CurrentUser) -> ReceiptOut:
    """Receipt photo -> receipt agent (image as inline Part) -> save_expense tool -> expense."""
    if file.content_type not in RECEIPT_TYPES:
        raise HTTPException(status_code=415, detail=f"unsupported image type {file.content_type}")
    data = await file.read(MAX_RECEIPT_BYTES + 1)
    if not data or len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=413, detail="image must be between 1 byte and 10 MB")

    run = await runtime.run_agent(
        "receipt",
        user_id,
        [
            types.Part(text="Here is a receipt photo. Read it and save it as an expense."),
            types.Part.from_bytes(data=data, mime_type=file.content_type),
        ],
    )
    saved = run.last_tool_result("save_expense")
    if not saved or saved.get("status") != "saved":
        reason = (saved or {}).get("error") or run.text or "the receipt could not be read"
        raise HTTPException(status_code=422, detail=reason)
    expense = expense_service.get_expense(db, user_id, int(saved["expense_id"]))
    return ReceiptOut(
        expense=ExpenseOut.from_model(expense), agent_message=run.text, warnings=saved.get("warnings", [])
    )


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, user_id: CurrentUser) -> ChatOut:
    """One message -> coordinator -> specialist agent. Returns text and, if the report agent
    produced one, a chart spec for the frontend."""
    run = await runtime.run_agent("chat", user_id, [types.Part(text=body.message)], body.session_id)
    report = run.last_tool_result("run_report")
    chart = ChartSpec(**report["chart"]) if report and report.get("chart") else None
    return ChatOut(session_id=run.session_id, text=run.text or "(no answer)", chart=chart)
