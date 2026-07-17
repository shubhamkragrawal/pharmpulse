from __future__ import annotations

from typing import Any
from unittest.mock import patch

from core.extractor_base import BaseExtractor, PageResult

# Mocked non-pharma API: a library catalog, two pages, cursor-paginated.
LIBRARY_PAGES = {
    None: (
        [
            {"book_id": "LC-001", "title": "Domain-Driven Design", "author": "Eric Evans"},
            {"book_id": "LC-002", "title": "Refactoring", "author": "Martin Fowler"},
        ],
        "page-2-token",
    ),
    "page-2-token": (
        [{"book_id": "LC-003", "title": "The Pragmatic Programmer", "author": "Hunt & Thomas"}],
        None,
    ),
}


class LibraryCatalogExtractor(BaseExtractor):
    source_name = "library_catalog"
    target_table = "raw.library_books"
    record_id_field = "book_id"

    def fetch_page(self, page_index: int, cursor: str | None) -> PageResult:
        records, next_cursor = LIBRARY_PAGES[cursor]
        return PageResult(records=records, has_more=next_cursor is not None, next_cursor=next_cursor)

    def record_id(self, record: dict[str, Any]) -> str:
        return record["book_id"]


def _sql_text(query) -> str:
    return query.as_string(None) if hasattr(query, "as_string") else str(query)


class FakeCursor:
    def __init__(self, store: "FakeStore"):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=()):
        text = _sql_text(query)
        if "extraction_checkpoints" in text and text.strip().startswith("SELECT"):
            row = self.store.checkpoints.get(params[0])
            self._fetchone_result = row
        elif "INSERT INTO" in text and "extraction_checkpoints" in text:
            source, start_page, started_at = params
            if source in self.store.checkpoints:
                self.store.checkpoints[source]["status"] = "running"
            else:
                self.store.checkpoints[source] = {
                    "last_page_completed": start_page,
                    "resume_cursor": None,
                    "status": "running",
                }
        elif "UPDATE" in text and "status = 'completed'" in text:
            self.store.checkpoints[params[1]]["status"] = "completed"
        elif "UPDATE" in text and "extraction_checkpoints" in text:
            page_index, cursor, source = params
            self.store.checkpoints[source]["last_page_completed"] = page_index
            self.store.checkpoints[source]["resume_cursor"] = cursor
        elif "INSERT INTO" in text:
            record_id, payload, fetched_at = params
            self.store.records[record_id] = getattr(payload, "obj", payload)

    def fetchone(self):
        return getattr(self, "_fetchone_result", None)


class FakeStore:
    def __init__(self):
        self.checkpoints: dict[str, dict] = {}
        self.records: dict[str, dict] = {}


class FakeConn:
    def __init__(self, store: FakeStore):
        self.store = store

    def cursor(self, **kwargs):
        return FakeCursor(self.store)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_base_extractor_handles_non_pharma_source_end_to_end():
    store = FakeStore()
    extractor = LibraryCatalogExtractor(db_dsn="postgresql://fake", page_size=2)

    with patch("core.extractor_base.psycopg.connect", return_value=FakeConn(store)):
        total = extractor.run(resume=False)

    assert total == 3
    assert set(store.records.keys()) == {"LC-001", "LC-002", "LC-003"}
    assert store.records["LC-002"]["title"] == "Refactoring"
    assert store.checkpoints["library_catalog"]["status"] == "completed"
    assert store.checkpoints["library_catalog"]["last_page_completed"] == 1


def test_base_extractor_resumes_from_checkpoint_not_page_zero():
    store = FakeStore()
    store.checkpoints["library_catalog"] = {
        "last_page_completed": 0,
        "resume_cursor": "page-2-token",
        "status": "running",
    }
    extractor = LibraryCatalogExtractor(db_dsn="postgresql://fake", page_size=2)

    with patch("core.extractor_base.psycopg.connect", return_value=FakeConn(store)):
        total = extractor.run(resume=True)

    assert total == 1
    assert set(store.records.keys()) == {"LC-003"}
    assert "LC-001" not in store.records
