import requests

from worker.notifications.telegram import BLOCKED, FAILED, RETRY, SENT, TelegramClient

TOKEN = "123456:SECRET-TOKEN"


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class Session:
    def __init__(self, outcome):
        self.outcome, self.sent = outcome, []

    def post(self, url, json=None, timeout=None):
        self.sent.append((url, json))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def client(outcome):
    s = Session(outcome)
    return TelegramClient(TOKEN, s), s


def test_success_posts_plain_text_to_the_chat():
    c, s = client(Resp(200, {"ok": True}))
    assert c.send_message(42, "hi").status == SENT
    assert s.sent[0][1] == {"chat_id": 42, "text": "hi", "disable_web_page_preview": True}


def test_rate_limit_is_retryable_with_server_hint():
    r = client(Resp(429, {"description": "Too Many Requests", "parameters": {"retry_after": 7}}))[0].send_message(1, "x")
    assert (r.status, r.retry_after) == (RETRY, 7.0)


def test_blocked_users_and_missing_chats_are_not_retried():
    assert client(Resp(403, {"description": "Forbidden: bot was blocked by the user"}))[0].send_message(1, "x").status == BLOCKED
    assert client(Resp(400, {"description": "Bad Request: chat not found"}))[0].send_message(1, "x").status == BLOCKED


def test_server_errors_retry_but_other_client_errors_fail():
    assert client(Resp(502))[0].send_message(1, "x").status == RETRY
    assert client(Resp(400, {"description": "Bad Request: message is too long"}))[0].send_message(1, "x").status == FAILED


def test_network_errors_retry_and_never_leak_the_token():
    r = client(requests.ConnectionError("failed for url https://api.telegram.org/bot%s/sendMessage" % TOKEN))[0].send_message(1, "x")
    assert r.status == RETRY and TOKEN not in r.error and "SECRET" not in r.error
