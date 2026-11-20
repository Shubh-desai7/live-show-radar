"""Thin PostgREST client over `requests` (no extra dependency). Uses the service-role key: bypasses RLS."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests


class DatabaseError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__("Supabase request failed (%d): %s" % (status, body[:300]))
        self.status = status
        self.body = body


class SupabaseRest:
    def __init__(self, url: str, service_key: str, session: Optional[requests.Session] = None) -> None:
        self.base = url.rstrip("/") + "/rest/v1/"
        self.session = session or requests.Session()
        self.session.headers.update({
            "apikey": service_key,
            "Authorization": "Bearer " + service_key,
            "Content-Type": "application/json",
        })

    def _check(self, resp: requests.Response) -> requests.Response:
        if resp.status_code >= 400:
            raise DatabaseError(resp.status_code, resp.text)
        return resp

    def select(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        return self._check(self.session.get(self.base + table, params=params, timeout=30)).json()

    def insert(self, table: str, row: Dict[str, Any], *, ignore_duplicates: bool = False,
               merge_duplicates: bool = False, on_conflict: Optional[str] = None) -> Optional[Dict[str, Any]]:
        prefer = "return=representation"
        params: Dict[str, str] = {}
        if ignore_duplicates or merge_duplicates:
            prefer += ",resolution=" + ("merge-duplicates" if merge_duplicates else "ignore-duplicates")
            if on_conflict:
                params["on_conflict"] = on_conflict
        resp = self._check(self.session.post(self.base + table, json=row, params=params,
                                             headers={"Prefer": prefer}, timeout=30))
        rows = resp.json()
        return rows[0] if rows else None

    def update(self, table: str, match: Dict[str, str], values: Dict[str, Any]) -> None:
        self._check(self.session.patch(self.base + table, params=match, json=values, timeout=30))

    def update_returning(self, table: str, match: Dict[str, str], values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """PATCH and return the rows that matched (empty list = nothing matched, e.g. lost a race)."""
        resp = self._check(self.session.patch(self.base + table, params=match, json=values,
                                              headers={"Prefer": "return=representation"}, timeout=30))
        return resp.json()
