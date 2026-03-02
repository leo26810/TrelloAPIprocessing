from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "ai_apps.json"
DB_FILE = BASE_DIR / "data" / "ai_finder.db"

TOKEN_REGEX = re.compile(r"[a-zA-Z0-9äöüÄÖÜß+#.-]+")
STOPWORDS = {
    "the",
    "and",
    "für",
    "mit",
    "eine",
    "einen",
    "oder",
    "und",
    "der",
    "die",
    "das",
    "ich",
    "you",
    "to",
    "for",
    "in",
}

INTENT_KEYWORDS: dict[str, set[str]] = {
    "coding": {"code", "coding", "dev", "programm", "python", "javascript", "bug", "software"},
    "writing": {"text", "blog", "writing", "copy", "email", "artikel", "marketing"},
    "design": {"design", "bild", "image", "grafik", "logo", "ui", "ux", "video"},
    "research": {"research", "analyse", "analysis", "data", "report", "study", "insights"},
    "productivity": {"meeting", "notes", "produktivität", "productivity", "planung", "tasks", "workflow"},
}


class AnalyzeRequest(BaseModel):
    prompt: str = Field(..., min_length=4)
    top_k: int = Field(default=5, ge=1, le=20)


class AppResult(BaseModel):
    app_id: int
    name: str
    category: str
    description: str
    website: str
    pricing: str
    score: float
    strengths: list[str]
    reason: str


app = FastAPI(title="AI Finder", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> sqlite3.Connection:
    if not DB_FILE.exists():
        init_db()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS ai_apps;
            CREATE TABLE ai_apps (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                strengths TEXT NOT NULL,
                pricing TEXT NOT NULL,
                website TEXT NOT NULL,
                popularity REAL NOT NULL,
                keywords TEXT NOT NULL,
                locale TEXT NOT NULL
            );
            """
        )
        raw_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        data = []
        for item in raw_data:
            normalized = dict(item)
            normalized["strengths"] = json.dumps(item["strengths"], ensure_ascii=False)
            normalized["keywords"] = json.dumps(item["keywords"], ensure_ascii=False)
            data.append(normalized)

        conn.executemany(
            """
            INSERT INTO ai_apps(id, name, category, description, strengths, pricing, website, popularity, keywords, locale)
            VALUES(:id, :name, :category, :description, :strengths, :pricing, :website, :popularity, :keywords, :locale)
            """,
            data,
        )


def tokenize(text: str) -> list[str]:
    raw = [token.lower() for token in TOKEN_REGEX.findall(text)]
    return [token for token in raw if token not in STOPWORDS and len(token) > 2]


def infer_intents(prompt_tokens: set[str]) -> set[str]:
    intents = set()
    for intent, keys in INTENT_KEYWORDS.items():
        if prompt_tokens.intersection(keys):
            intents.add(intent)
    return intents


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    strengths = json.loads(row["strengths"])
    keywords = set(json.loads(row["keywords"]))
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "strengths": strengths,
        "pricing": row["pricing"],
        "website": row["website"],
        "popularity": row["popularity"],
        "keywords": keywords,
        "locale": row["locale"],
    }


def score_app(prompt: str, prompt_tokens: set[str], intents: set[str], app_data: dict[str, Any]) -> tuple[float, str]:
    app_tokens = tokenize(f"{app_data['name']} {app_data['description']} {' '.join(app_data['strengths'])} {' '.join(app_data['keywords'])}")
    app_token_set = set(app_tokens)

    overlap = len(prompt_tokens.intersection(app_token_set))
    overlap_score = overlap / max(1, math.sqrt(len(app_token_set)))

    intent_score = 0.0
    category_lower = app_data["category"].lower()
    for intent in intents:
        if intent in category_lower or any(intent in k for k in app_data["keywords"]):
            intent_score += 1.2

    prompt_length_factor = min(1.3, 0.7 + len(prompt) / 200)
    popularity_bonus = app_data["popularity"] * 0.8
    score = (overlap_score * 4 + intent_score + popularity_bonus) * prompt_length_factor

    reason_parts = []
    if overlap:
        reason_parts.append(f"{overlap} Keyword-Matches")
    if intent_score:
        reason_parts.append("passt zu deinem Use-Case")
    reason_parts.append(f"Popularity {app_data['popularity']:.1f}/5")

    return score, ", ".join(reason_parts)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=list[AppResult])
def analyze_prompt(payload: AnalyzeRequest) -> list[AppResult]:
    prompt_tokens = set(tokenize(payload.prompt))
    if not prompt_tokens:
        raise HTTPException(status_code=400, detail="Prompt enthält zu wenige verwertbare Begriffe.")

    intents = infer_intents(prompt_tokens)

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM ai_apps").fetchall()

    scored: list[AppResult] = []
    for row in rows:
        app_data = row_to_dict(row)
        score, reason = score_app(payload.prompt, prompt_tokens, intents, app_data)
        scored.append(
            AppResult(
                app_id=app_data["id"],
                name=app_data["name"],
                category=app_data["category"],
                description=app_data["description"],
                website=app_data["website"],
                pricing=app_data["pricing"],
                score=round(score, 3),
                strengths=app_data["strengths"],
                reason=reason,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: payload.top_k]


@app.get("/api/search")
def search_apps(
    query: str = Query(default=""),
    category: str = Query(default=""),
    pricing: str = Query(default=""),
    locale: str = Query(default=""),
    min_popularity: float = Query(default=0.0, ge=0.0, le=5.0),
) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM ai_apps").fetchall()

    query_tokens = set(tokenize(query))
    filtered = []
    for row in rows:
        item = row_to_dict(row)

        if category and category.lower() != item["category"].lower():
            continue
        if pricing and pricing.lower() not in item["pricing"].lower():
            continue
        if locale and locale.lower() not in item["locale"].lower():
            continue
        if item["popularity"] < min_popularity:
            continue

        if query_tokens:
            haystack = set(tokenize(item["name"] + " " + item["description"] + " " + " ".join(item["keywords"])))
            if not query_tokens.intersection(haystack):
                continue

        filtered.append(item)

    filtered.sort(key=lambda x: x["popularity"], reverse=True)
    return filtered


@app.get("/api/apps")
def list_apps() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM ai_apps ORDER BY popularity DESC").fetchall()
    return [row_to_dict(row) for row in rows]


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")
