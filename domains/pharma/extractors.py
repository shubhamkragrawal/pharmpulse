from __future__ import annotations

from typing import Any

import requests

from core.extractor_base import BaseExtractor, PageResult


class CTGovExtractor(BaseExtractor):
    source_name = "ctgov"
    target_table = "raw.ct_studies"
    record_id_field = "nct_id"

    base_url = "https://clinicaltrials.gov/api/v2/studies"

    def fetch_page(self, page_index: int, cursor: str | None) -> PageResult:
        params = {"pageSize": self.page_size}
        if cursor:
            params["pageToken"] = cursor
        resp = requests.get(self.base_url, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        studies = body.get("studies", [])
        next_token = body.get("nextPageToken")
        return PageResult(records=studies, has_more=bool(next_token), next_cursor=next_token)

    def record_id(self, record: dict[str, Any]) -> str:
        return record["protocolSection"]["identificationModule"]["nctId"]


class OpenFDAExtractor(BaseExtractor):
    source_name = "openfda"
    target_table = "raw.fda_applications"
    record_id_field = "application_number"

    base_url = "https://api.fda.gov/drug/drugsfda.json"

    def fetch_page(self, page_index: int, cursor: str | None) -> PageResult:
        skip = page_index * self.page_size
        params = {"limit": self.page_size, "skip": skip}
        resp = requests.get(self.base_url, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        results = body.get("results", [])
        total = body.get("meta", {}).get("results", {}).get("total", 0)
        has_more = skip + len(results) < total
        return PageResult(records=results, has_more=has_more)

    def record_id(self, record: dict[str, Any]) -> str:
        return record["application_number"]
