import os
from pathlib import Path

import psycopg2
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from components.chat_prompt import CHAT_SYSTEM_PROMPT
from components.chunking_process import load_and_split_pages, load_and_split_pdf
from components.env import load_project_env
from components.gemini_embedding import GeminiEmbeddings
from components.mock_pdf_data import MOCK_PDF_NAME, MOCK_PDF_PAGES
from components.openrouter_rerank import OpenRouterRerank

load_project_env()

_gemini_embeddings = None
_reranker = None


def _embeddings():
    global _gemini_embeddings
    if _gemini_embeddings is None:
        _gemini_embeddings = GeminiEmbeddings()
    return _gemini_embeddings


def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = OpenRouterRerank()
    return _reranker


def get_connection():
    return psycopg2.connect(
        database=os.getenv("POSTGRES_DB", "vectordb3"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "newpassword"),
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


def _to_vector(values) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def _store_split_documents(docs_list, parent_docs_list, child_docs_list, child_texts) -> dict:
    if not docs_list:
        raise ValueError("No pages found in the PDF.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        embedded_contents = _embeddings().embed_documents(child_texts)
        doc = docs_list[0]
        pdf_id = doc.metadata["document_id"]
        pdf_name = doc.metadata["pdf_name"]

        cursor.execute(
            """
            INSERT INTO documents (file_hash, pdf_name)
            VALUES (%s, %s)
            ON CONFLICT (file_hash) DO NOTHING
            """,
            (pdf_id, pdf_name),
        )
        conn.commit()

        for parent_doc in parent_docs_list:
            parent_docs_id = parent_doc.metadata["parent_id"]
            hash_id = parent_doc.metadata["document_id"]
            parent_pages = parent_doc.metadata.get("page", 0)
            parent_texts = parent_doc.page_content
            cursor.execute(
                """
                INSERT INTO parent_chunks (parent_id, file_hash, page, parent_texts)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (parent_id) DO NOTHING
                """,
                (str(parent_docs_id), hash_id, parent_pages, parent_texts),
            )
        conn.commit()

        for child_doc, embedded_content in zip(child_docs_list, embedded_contents):
            child_id = child_doc.metadata["child_id"]
            child_parent_id = child_doc.metadata["parent_id"]
            child_text = child_doc.page_content
            cursor.execute(
                """
                INSERT INTO child_chunks (child_id, parent_id, child_text, embeddings)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (child_id) DO NOTHING
                """,
                (
                    str(child_id),
                    str(child_parent_id),
                    child_text,
                    _to_vector(embedded_content),
                ),
            )
        conn.commit()

        return {
            "filename": pdf_name,
            "document_id": pdf_id,
            "parent_chunks": len(parent_docs_list),
            "child_chunks": len(child_docs_list),
        }
    finally:
        conn.close()


def insert_into_database(pdf_path: str | Path) -> dict:
    pdf_path = Path(pdf_path)
    docs_list, parent_docs_list, child_docs_list, child_texts = load_and_split_pdf(
        pdf_path
    )
    return _store_split_documents(
        docs_list, parent_docs_list, child_docs_list, child_texts
    )


def seed_mock_pdf_data() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM child_chunks")
        cursor.execute("DELETE FROM parent_chunks")
        cursor.execute("DELETE FROM documents")
        conn.commit()
    finally:
        conn.close()

    docs_list, parent_docs_list, child_docs_list, child_texts = load_and_split_pages(
        MOCK_PDF_PAGES, MOCK_PDF_NAME
    )
    return _store_split_documents(
        docs_list, parent_docs_list, child_docs_list, child_texts
    )


def list_documents() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.pdf_name, d.file_hash, COUNT(p.parent_id) AS pages
            FROM documents d
            LEFT JOIN parent_chunks p ON p.file_hash = d.file_hash
            GROUP BY d.pdf_name, d.file_hash
            ORDER BY d.pdf_name
            """
        )
        return [
            {"name": row[0], "id": row[1], "chunks": row[2]}
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def get_document(document_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pdf_name, file_hash FROM documents WHERE file_hash = %s",
            (document_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            """
            SELECT page, parent_texts
            FROM parent_chunks
            WHERE file_hash = %s
            ORDER BY page ASC, parent_id ASC
            """,
            (document_id,),
        )
        pages = [
            {"page": item[0], "text": item[1]}
            for item in cursor.fetchall()
        ]
        return {"name": row[0], "id": row[1], "pages": pages}
    finally:
        conn.close()


def query_database(query: str, history: list | None = None) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        embed_query = _to_vector(_embeddings().embed_query(query))

        sql_query = """
        WITH ranked_child_chunks AS (
            SELECT parent_id, (embeddings <=> %s::vector) AS distance
            FROM child_chunks
            ORDER BY embeddings <=> %s::vector ASC
            LIMIT 20
        ),
        deduplicated_parent_ids AS (
            SELECT parent_id, MIN(distance) AS best_distance
            FROM ranked_child_chunks
            GROUP BY parent_id
        )
        SELECT p.parent_id, p.parent_texts, p.page, d.pdf_name, d.file_hash
        FROM parent_chunks p
        JOIN deduplicated_parent_ids r ON p.parent_id = r.parent_id
        LEFT JOIN documents d ON p.file_hash = d.file_hash
        WHERE length(p.parent_texts) > 100
        ORDER BY r.best_distance ASC
        LIMIT 5
        """
        cursor.execute(sql_query, (embed_query, embed_query))
        sql_result = cursor.fetchall()
    finally:
        conn.close()

    if not sql_result:
        return {
            "answer": "ไม่พบเนื้อหาที่เกี่ยวข้องในเอกสารที่อัปโหลดไว้",
            "sources": [],
        }

    documents_payload = [{"text": result[1]} for result in sql_result]
    ranked = _get_reranker().rerank(
        query=query, documents=documents_payload, top_n=min(3, len(documents_payload))
    ) or []
    context = [item.get("source") for item in ranked if item.get("source")]
    if not context:
        context = [row[1] for row in sql_result[:3]]

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    user_content = f"""Context จากเอกสาร:
{context}

คำถามของผู้ใช้:
{query}"""

    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]
    if history:
        for item in history[-8:]:
            role = item.get("role")
            content = item.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_content))

    response = llm.invoke(messages)
    sources = [
        {
            "page": row[2],
            "text": row[1],
            "filename": row[3],
            "document_id": row[4],
        }
        for row in sql_result
    ]
    return {"answer": response.content, "sources": sources}
