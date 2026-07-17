from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_active_domain(config_path: Path | str = REPO_ROOT / "config.yaml") -> str:
    with open(config_path) as f:
        return yaml.safe_load(f)["active_domain"]


def get_domain_config(domain: str | None = None) -> dict:
    domain = domain or get_active_domain()
    path = REPO_ROOT / "domains" / domain / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
