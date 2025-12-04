import os
import json
from typing import Any, Dict, List, Optional

import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import httpx


class NLQueryRequest(BaseModel):
    db_path: str
    question: str
    dialect: str = "sqlite"
    max_tokens: int = 512


class NLQueryResponse(BaseModel):
    sql: str
    rows: List[Dict[str, Any]]
    columns: List[str]
    raw_answer: Optional[str] = None
    summary: Optional[str] = None

GENAI_API_KEY_ENV = "GENAI_API_KEY"
GENAI_BASE_URL = "https://genailab.tcs.in"
GENAI_MODEL = "azure_ai/genailab-maas-DeepSeek-V3-0324"

GENAI_API_KEY = os.getenv(GENAI_API_KEY_ENV, "sk-PHXT5d_JGKnDksrzSEI0Xg")

http_client = httpx.Client(verify=False)

llm = ChatOpenAI(
    base_url=GENAI_BASE_URL,
    model=GENAI_MODEL,
    api_key=GENAI_API_KEY,
    http_client=http_client,
)


app = FastAPI(title="NL-to-SQL SQLite API", version="1.0.0")


def get_db_schema(db_path: str) -> str:
    if not os.path.exists(db_path):
        raise HTTPException(status_code=400, detail=f"Database file not found: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to connect to database: {exc}")

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]

        schema_descriptions = []
        for table in tables:
            cursor.execute(f"PRAGMA table_info('{table}')")
            cols = cursor.fetchall()
            col_desc = ", ".join(
                f"{c[1]} {c[2]}{' PRIMARY KEY' if c[5] == 1 else ''}"
                for c in cols
            )
            schema_descriptions.append(f"TABLE {table}: {col_desc}")

        return "\n".join(schema_descriptions)
    finally:
        conn.close()


def call_openai_for_sql(prompt: str, max_tokens: int) -> str:
    if not GENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail=(
                f"GENAI_API_KEY not set. Please set the {GENAI_API_KEY_ENV} environment variable "
                "with your hackathon API key."
            ),
        )

    try:
        # LangChain ChatOpenAI-style call, same as in llmTest.py
        result = llm.invoke(prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM API error: {exc}")

    # result is usually an AIMessage with `.content`
    content = getattr(result, "content", "")
    if isinstance(content, list):
        # concatenate text parts if content is structured
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )

    text = (content or "").strip()

    # 1) If there's a fenced code block, try to extract SQL from the FIRST fenced block
    if "```" in text:
        parts = text.split("```")
        # parts: [before, maybe 'sql\n...code...', after, ...]
        if len(parts) >= 2:
            first_block = parts[1]
            block_stripped = first_block.strip()
            if block_stripped.lower().startswith("sql"):
                # remove leading 'sql' label line
                block_stripped = block_stripped[3:].lstrip("\n")
            text = block_stripped.strip()

    # 2) Strip leading/trailing backticks/newlines again in case of residual fences
    if text.startswith("```"):
        text = text.strip("`\n ")
        if text.lower().startswith("sql"):
            text = text[3:].lstrip("\n")

    # 3) If there is still explanation text, try to slice from first SQL keyword
    lowered = text.lower()
    start_idx = -1
    for kw in ["select", "with", "insert", "update", "delete"]:
        idx = lowered.find(kw)
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx

    if start_idx != -1:
        text = text[start_idx:]
    else:
        # No apparent SQL keywords; better to fail fast than send explanation text to SQLite
        raise HTTPException(
            status_code=500,
            detail="Could not extract a valid SQL query from LLM response.",
        )

    # 4) Trim after the last semicolon if present
    semi_idx = text.rfind(";")
    if semi_idx != -1:
        text = text[: semi_idx + 1]

    return text.strip()


def execute_sql(db_path: str, sql: str) -> (List[Dict[str, Any]], List[str]):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to connect to database: {exc}")

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows_raw = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(row) for row in rows_raw]
        return rows, columns
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f"SQL execution error: {exc}; SQL={sql}")
    finally:
        conn.close()


@app.post("/nl-query", response_model=NLQueryResponse)
async def nl_query(payload: NLQueryRequest) -> NLQueryResponse:
    schema = get_db_schema(payload.db_path)

    prompt = (
        f"SQLite schema:\n{schema}\n\n"
        f"User question: {payload.question}\n\n"
        "Return a single SQLite query that correctly answers the question. "
        "Use proper JOINs when needed. Do not modify data. Read-only queries only. "
        "Treat all text comparisons as case-insensitive by default (for example using COLLATE NOCASE "
        "or LOWER() on both sides of the comparison). For instance, if the question says severity 'high' "
        "and the data stores 'High', still return those rows by using a case-insensitive comparison."
    )

    sql = call_openai_for_sql(prompt, payload.max_tokens)
    rows, columns = execute_sql(payload.db_path, sql)

    # Build a Markdown table summary from the result rows
    summary: Optional[str] = None
    if columns:
        # Limit number of rows shown in the table to keep it compact
        max_rows = 20
        display_rows = rows[:max_rows]

        header = "| " + " | ".join(str(c) for c in columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        body_lines = []
        for r in display_rows:
            body_lines.append("| " + " | ".join(str(r.get(c, "")) for c in columns) + " |")

        table_lines = [header, separator] + body_lines
        summary = "\n".join(table_lines)

    return NLQueryResponse(sql=sql, rows=rows, columns=columns, summary=summary)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok"}
