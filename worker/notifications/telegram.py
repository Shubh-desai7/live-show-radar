"""Telegram Bot API sender for the worker. The bot token is never logged or placed in error text."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

SENT, RETRY, BLOCKED, FAILED = "sent", "retry", "blocked", "failed"


@dataclass
class SendResult:
    status: str                       # sent | retry | blocked | failed
    retry_after: Optional[float] = None
    error: str = ""                   # short, token-free description


class TelegramClient:
    def __init__(self, token: str, session: Optional[requests.Session] = None, timeout: float = 15) -> None:
        self._url = "https://api.telegram.org/bot%s/sendMessage" % token
        self.session = session or requests.Session()
        self.timeout = timeout

    def send_message(self, chat_id: int, text: str) -> SendResult:
        try:
            resp = self.session.post(self._url, json={"chat_id": chat_id, "text": text,
                                                      "disable_web_page_preview": True}, timeout=self.timeout)
        except requests.RequestException as exc:
            # type name only: requests exceptions embed the URL, which contains the token
            return SendResult(RETRY, error=type(exc).__name__)
        code = resp.status_code
        if code == 200:
            return SendResult(SENT)
        retry_after: Optional[float] = None
        description = ""
        try:
            body = resp.json()
            description = str(body.get("description", ""))[:120]
            retry_after = (body.get("parameters") or {}).get("retry_after")
        except ValueError:
            pass
        if code == 429:
            return SendResult(RETRY, retry_after=float(retry_after) if retry_after else None, error="rate limited")
        if code == 403:                     # user blocked the bot / deactivated: stop trying this chat
            return SendResult(BLOCKED, error="HTTP 403")
        if code == 400 and "chat not found" in description.lower():
            return SendResult(BLOCKED, error="chat not found")
        if code >= 500:
            return SendResult(RETRY, error="HTTP %d" % code)
        return SendResult(FAILED, error="HTTP %d %s" % (code, description))
