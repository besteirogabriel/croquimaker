from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROCESSING_STATES = ("queued", "reading", "building", "finishing")
INITIAL_AUDIT_HASH = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ProjectStorePaths:
    database: Path

    @classmethod
    def from_environment(cls) -> "ProjectStorePaths":
        data_dir = Path(os.getenv("CROQUIMAKER_DATA_DIR", "generated"))
        return cls(
            database=Path(
                os.getenv(
                    "CROQUIMAKER_PROJECT_DB",
                    str(data_dir / "operations.db"),
                )
            )
        )


class ProjectStore:
    def __init__(self, database: Path):
        self.database = Path(database)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def initialize(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_jobs (
                    id TEXT PRIMARY KEY,
                    project_slug TEXT NOT NULL
                        CHECK (project_slug IN ('caxias', 'vacaria')),
                    created_by_id INTEGER,
                    created_by TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    input_filename TEXT NOT NULL,
                    output_pdf_filename TEXT NOT NULL UNIQUE,
                    output_xls_filename TEXT,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    has_excel INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    input_sha256 TEXT,
                    output_sha256 TEXT,
                    engine TEXT,
                    cached INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_summary TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_project_jobs_scope_created
                    ON project_jobs(project_slug, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_project_jobs_state
                    ON project_jobs(state);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    actor_user_id INTEGER,
                    actor_username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    project_slug TEXT
                        CHECK (project_slug IN ('caxias', 'vacaria') OR project_slug IS NULL),
                    job_id TEXT,
                    source_address TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );

                CREATE INDEX IF NOT EXISTS idx_audit_scope_occurred
                    ON audit_events(project_slug, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_job
                    ON audit_events(job_id, occurred_at);
                """
            )

    @staticmethod
    def _serialize_result(result: dict | None) -> str:
        return json.dumps(result or {}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> dict:
        job = dict(row)
        job["has_excel"] = bool(job["has_excel"])
        job["cached"] = bool(job["cached"])
        try:
            job["result"] = json.loads(job.pop("result_json") or "{}")
        except json.JSONDecodeError:
            job["result"] = {}
        return job

    def save_job(self, job: dict) -> None:
        now = utc_now()
        created_at = job.get("created_at") or now
        updated_at = job.get("updated_at") or now
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_jobs (
                    id, project_slug, created_by_id, created_by,
                    original_filename, input_filename, output_pdf_filename,
                    output_xls_filename, state, message, has_excel, result_json,
                    input_sha256, output_sha256, engine, cached, created_at,
                    updated_at, started_at, completed_at, error_summary
                ) VALUES (
                    :id, :project_slug, :created_by_id, :created_by,
                    :original_filename, :input_filename, :output_pdf_filename,
                    :output_xls_filename, :state, :message, :has_excel, :result_json,
                    :input_sha256, :output_sha256, :engine, :cached, :created_at,
                    :updated_at, :started_at, :completed_at, :error_summary
                )
                ON CONFLICT(id) DO UPDATE SET
                    project_slug = excluded.project_slug,
                    created_by_id = excluded.created_by_id,
                    created_by = excluded.created_by,
                    original_filename = excluded.original_filename,
                    input_filename = excluded.input_filename,
                    output_pdf_filename = excluded.output_pdf_filename,
                    output_xls_filename = excluded.output_xls_filename,
                    state = excluded.state,
                    message = excluded.message,
                    has_excel = excluded.has_excel,
                    result_json = excluded.result_json,
                    input_sha256 = excluded.input_sha256,
                    output_sha256 = excluded.output_sha256,
                    engine = excluded.engine,
                    cached = excluded.cached,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    error_summary = excluded.error_summary
                """,
                {
                    "id": job["id"],
                    "project_slug": job["project_slug"],
                    "created_by_id": job.get("created_by_id"),
                    "created_by": job.get("created_by", "legacy"),
                    "original_filename": job.get("original_filename", "projeto.pdf"),
                    "input_filename": job.get("input_filename", "projeto.pdf"),
                    "output_pdf_filename": job.get(
                        "output_pdf_filename",
                        f"CROQUI-{job['project_slug'].upper()}-{job['id'][:8].upper()}.pdf",
                    ),
                    "output_xls_filename": job.get("output_xls_filename"),
                    "state": job["state"],
                    "message": job["message"],
                    "has_excel": int(bool(job.get("has_excel"))),
                    "result_json": self._serialize_result(job.get("result")),
                    "input_sha256": job.get("input_sha256"),
                    "output_sha256": job.get("output_sha256"),
                    "engine": job.get("engine"),
                    "cached": int(bool(job.get("cached"))),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "started_at": job.get("started_at"),
                    "completed_at": job.get("completed_at"),
                    "error_summary": job.get("error_summary"),
                },
            )

    def get_job(self, job_id: str, project_slug: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM project_jobs
                WHERE id = ? AND project_slug = ?
                """,
                (job_id, project_slug),
            ).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, project_slugs: Iterable[str], limit: int = 50) -> list[dict]:
        slugs = tuple(project_slugs)
        if not slugs:
            return []
        placeholders = ",".join("?" for _ in slugs)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM project_jobs
                WHERE project_slug IN ({placeholders})
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*slugs, max(1, min(limit, 500))),
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def pending_jobs(self) -> list[dict]:
        placeholders = ",".join("?" for _ in PROCESSING_STATES)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM project_jobs
                WHERE state IN ({placeholders})
                ORDER BY created_at
                """,
                PROCESSING_STATES,
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def dashboard_stats(self, project_slugs: Iterable[str]) -> dict:
        slugs = tuple(project_slugs)
        if not slugs:
            return {"total": 0, "done": 0, "processing": 0, "error": 0}
        placeholders = ",".join("?" for _ in slugs)
        processing_placeholders = ",".join("?" for _ in PROCESSING_STATES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN state = 'done' THEN 1 ELSE 0 END) AS done,
                    SUM(CASE WHEN state IN ({processing_placeholders}) THEN 1 ELSE 0 END)
                        AS processing,
                    SUM(CASE WHEN state = 'error' THEN 1 ELSE 0 END) AS error
                FROM project_jobs
                WHERE project_slug IN ({placeholders})
                """,
                (*PROCESSING_STATES, *slugs),
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "done": int(row["done"] or 0),
            "processing": int(row["processing"] or 0),
            "error": int(row["error"] or 0),
        }

    def record_event(
        self,
        *,
        actor_username: str,
        action: str,
        outcome: str = "success",
        actor_user_id: int | None = None,
        project_slug: str | None = None,
        job_id: str | None = None,
        source_address: str | None = None,
        details: dict | None = None,
        occurred_at: str | None = None,
    ) -> str:
        occurred_at = occurred_at or utc_now()
        details_json = json.dumps(
            details or {},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous_row = connection.execute(
                "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous_row["event_hash"] if previous_row else INITIAL_AUDIT_HASH
            payload = json.dumps(
                {
                    "occurred_at": occurred_at,
                    "actor_user_id": actor_user_id,
                    "actor_username": actor_username,
                    "action": action,
                    "outcome": outcome,
                    "project_slug": project_slug,
                    "job_id": job_id,
                    "source_address": source_address,
                    "details_json": details_json,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            event_hash = hashlib.sha256(
                f"{previous_hash}:{payload}".encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO audit_events (
                    occurred_at, actor_user_id, actor_username, action, outcome,
                    project_slug, job_id, source_address, details_json,
                    previous_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    occurred_at,
                    actor_user_id,
                    actor_username,
                    action,
                    outcome,
                    project_slug,
                    job_id,
                    source_address,
                    details_json,
                    previous_hash,
                    event_hash,
                ),
            )
        return event_hash

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict:
        event = dict(row)
        try:
            event["details"] = json.loads(event.pop("details_json") or "{}")
        except json.JSONDecodeError:
            event["details"] = {}
        return event

    def list_events(
        self,
        project_slugs: Iterable[str],
        *,
        limit: int = 100,
        include_system: bool = False,
    ) -> list[dict]:
        slugs = tuple(project_slugs)
        if not slugs and not include_system:
            return []
        params: list[object] = list(slugs)
        if slugs:
            placeholders = ",".join("?" for _ in slugs)
            scope = f"project_slug IN ({placeholders})"
            if include_system:
                scope = f"({scope} OR project_slug IS NULL)"
        else:
            scope = "project_slug IS NULL"
        params.append(max(1, min(limit, 1000)))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM audit_events
                WHERE {scope}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def verify_audit_chain(self) -> bool:
        previous_hash = INITIAL_AUDIT_HASH
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY id"
            ).fetchall()
        for row in rows:
            if row["previous_hash"] != previous_hash:
                return False
            payload = json.dumps(
                {
                    "occurred_at": row["occurred_at"],
                    "actor_user_id": row["actor_user_id"],
                    "actor_username": row["actor_username"],
                    "action": row["action"],
                    "outcome": row["outcome"],
                    "project_slug": row["project_slug"],
                    "job_id": row["job_id"],
                    "source_address": row["source_address"],
                    "details_json": row["details_json"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            expected_hash = hashlib.sha256(
                f"{previous_hash}:{payload}".encode("utf-8")
            ).hexdigest()
            if row["event_hash"] != expected_hash:
                return False
            previous_hash = row["event_hash"]
        return True
