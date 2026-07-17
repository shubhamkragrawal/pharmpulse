from __future__ import annotations

import importlib
import os

from core.config import get_active_domain, get_domain_config


def build_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def run_extraction(domain: str | None = None, sources: list[str] | None = None) -> dict[str, int]:
    domain = domain or get_active_domain()
    domain_config = get_domain_config(domain)
    extractors_module = importlib.import_module(f"domains.{domain}.extractors")
    dsn = build_dsn()

    results: dict[str, int] = {}
    for source_name, source_cfg in domain_config["extraction"].items():
        if sources is not None and source_name not in sources:
            continue
        extractor_cls = getattr(extractors_module, source_cfg["extractor_class"])
        extractor = extractor_cls(db_dsn=dsn, page_size=source_cfg.get("page_size", 100))
        print(f"[{domain}/{source_name}] starting extraction...")
        total = extractor.run()
        print(f"[{domain}/{source_name}] upserted {total} records")
        results[source_name] = total
    return results
