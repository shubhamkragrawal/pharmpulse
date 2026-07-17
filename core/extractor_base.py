from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    records: list[dict[str, Any]]
    has_more: bool
    next_cursor: str | None = None


class BaseExtractor(ABC):
    """Paginated extractor: fetch -> retry/backoff -> checkpoint -> upsert. No knowledge of what a record represents."""

    source_name: str
    target_table: str
    record_id_field: str
    payload_field: str = "payload"

    max_retries: int = 5
    backoff_base_seconds: float = 1.0

    def __init__(self, db_dsn: str, page_size: int = 100):
        self.db_dsn = db_dsn
        self.page_size = page_size

    @abstractmethod
    def fetch_page(self, page_index: int, cursor: str | None) -> PageResult:
        raise NotImplementedError

    @abstractmethod
    def record_id(self, record: dict[str, Any]) -> str:
        raise NotImplementedError

    def run(self, resume: bool = True) -> int:
        with psycopg.connect(self.db_dsn, row_factory=dict_row) as conn:
            page_index, cursor = self._get_resume_point(conn) if resume else (0, None)
            self._mark_running(conn, page_index)
            total = 0
            while True:
                result = self._fetch_page_with_backoff(page_index, cursor)
                if result.records:
                    total += self._upsert(conn, result.records)
                self._checkpoint(conn, page_index, result.next_cursor)
                if not result.has_more:
                    break
                cursor = result.next_cursor
                page_index += 1
            self._mark_completed(conn)
            return total

    def _fetch_page_with_backoff(self, page_index: int, cursor: str | None) -> PageResult:
        attempt = 0
        while True:
            try:
                return self.fetch_page(page_index, cursor)
            except Exception:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                sleep_for = self.backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "%s: page %d fetch failed (attempt %d/%d), retrying in %.1fs",
                    self.source_name, page_index, attempt, self.max_retries, sleep_for,
                )
                time.sleep(sleep_for)

    def _upsert(self, conn: psycopg.Connection, records: list[dict[str, Any]]) -> int:
        table_parts = self.target_table.split(".")
        table_ident = sql.Identifier(*table_parts)
        query = sql.SQL(
            "INSERT INTO {table} ({id_col}, {payload_col}, fetched_at) VALUES (%s, %s, %s) "
            "ON CONFLICT ({id_col}) DO UPDATE SET {payload_col} = EXCLUDED.{payload_col}, fetched_at = EXCLUDED.fetched_at"
        ).format(
            table=table_ident,
            id_col=sql.Identifier(self.record_id_field),
            payload_col=sql.Identifier(self.payload_field),
        )
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            for record in records:
                cur.execute(query, (self.record_id(record), psycopg.types.json.Json(record), now))
        conn.commit()
        return len(records)

    def _get_resume_point(self, conn: psycopg.Connection) -> tuple[int, str | None]:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_page_completed, resume_cursor, status FROM raw.extraction_checkpoints WHERE source = %s",
                (self.source_name,),
            )
            row = cur.fetchone()
        if row is None or row["status"] == "completed":
            return 0, None
        return row["last_page_completed"] + 1, row["resume_cursor"]

    def _mark_running(self, conn: psycopg.Connection, start_page: int) -> None:
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.extraction_checkpoints
                    (source, last_page_completed, last_run_started_at, status)
                VALUES (%s, %s, %s, 'running')
                ON CONFLICT (source) DO UPDATE SET
                    last_run_started_at = EXCLUDED.last_run_started_at,
                    status = 'running'
                """,
                (self.source_name, max(start_page - 1, 0), now),
            )
        conn.commit()

    def _checkpoint(self, conn: psycopg.Connection, page_index: int, cursor: str | None) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE raw.extraction_checkpoints
                SET last_page_completed = %s, resume_cursor = %s, status = 'running'
                WHERE source = %s
                """,
                (page_index, cursor, self.source_name),
            )
        conn.commit()

    def _mark_completed(self, conn: psycopg.Connection) -> None:
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE raw.extraction_checkpoints SET status = 'completed', last_run_completed_at = %s WHERE source = %s",
                (now, self.source_name),
            )
        conn.commit()
