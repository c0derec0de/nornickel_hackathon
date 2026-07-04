"""Тест backoff-логики openai-провайдера (мок httpx + sleep, без сети).

Запуск из каталога backend:
    PYTHONPATH=. python tests/test_llm_backoff.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm  # noqa: E402

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {extra}")


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def run():
    llm.time.sleep = lambda *a, **k: None          # не спим
    llm.settings.openai_api_key = "test"
    llm.settings.openai_base_url = "http://x"

    print("== 429 затем 200 ==")
    calls = {"n": 0}

    def post_429_then_ok(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResp(429, {"error": {"metadata": {"retry_after_seconds": 0.01}}})
        return FakeResp(200, {"choices": [{"message": {"content": '{"ok":true}'}}]})

    llm.httpx.post = post_429_then_ok
    check("контент после ретраев", llm._openai_chat("s", "u") == '{"ok":true}')
    check("3 попытки", calls["n"] == 3, f"n={calls['n']}")

    print("== стабильный 429 → RuntimeError ==")
    calls2 = {"n": 0}

    def post_always_429(url, json=None, headers=None, timeout=None):
        calls2["n"] += 1
        return FakeResp(429, {"error": {"metadata": {"retry_after_seconds": 0.01}}})

    llm.httpx.post = post_always_429
    try:
        llm._openai_chat("s", "u", max_retries=4)
        check("должен был бросить", False)
    except RuntimeError:
        check("бросил RuntimeError", True)
        check("ровно 4 попытки", calls2["n"] == 4, f"n={calls2['n']}")

    print("== 400 на response_format → повтор без него ==")
    seen = []

    def post_400_then_ok(url, json=None, headers=None, timeout=None):
        seen.append("response_format" in json)
        if len(seen) == 1:
            return FakeResp(400, {"error": {"message": "response_format not supported"}})
        return FakeResp(200, {"choices": [{"message": {"content": "ok"}}]})

    llm.httpx.post = post_400_then_ok
    out = llm._openai_chat("s", "u", json_mode=True)
    check("вернул ответ после деградации", out == "ok")
    check("1-й запрос с response_format, 2-й без", seen == [True, False], f"seen={seen}")

    print("== extract: JSON и битый ответ ==")
    llm.httpx.post = lambda *a, **k: FakeResp(200, {"choices": [{"message": {"content":
        '{"entities":[{"name":"никель","type":"Material"}],"relations":[]}'}}]})
    er = llm._openai_extract("текст")
    check("извлёк сущность", len(er.entities) == 1 and er.entities[0].name == "никель")

    llm.httpx.post = lambda *a, **k: FakeResp(200, {"choices": [{"message":
        {"content": "извините, не могу"}}]})
    er2 = llm._openai_extract("текст")
    check("битый JSON → пустой результат без исключения", er2.entities == [])

    print(f"\n==== ИТОГ: {PASS} passed, {FAIL} failed ====")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
