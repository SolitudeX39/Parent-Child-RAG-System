import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.env import load_project_env

load_project_env()

from components.chat_prompt import SUGGESTED_PROMPTS
from components.database import (
    get_document,
    insert_into_database,
    list_documents,
    query_database,
    seed_mock_pdf_data,
)

app = FastAPI(title="Parent-Child RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = []


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/documents")
def documents():
    try:
        return {"documents": list_documents()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/prompts")
def prompts():
    return {"prompts": SUGGESTED_PROMPTS}


@app.get("/documents/{document_id}")
def document_detail(document_id: str):
    try:
        detail = get_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not detail:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return detail


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    upload_dir = ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_dir:
        saved_path = Path(tmp_dir) / filename
        saved_path.write_bytes(await file.read())
        try:
            result = insert_into_database(saved_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "indexed", **result}


@app.post("/seed-mock")
def seed_mock():
    try:
        return {"status": "indexed", **seed_mock_pdf_data()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat")
def chat(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    history = [item.model_dump() for item in body.history]
    try:
        return query_database(message, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
