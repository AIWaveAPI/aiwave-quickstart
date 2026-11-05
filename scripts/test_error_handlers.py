#!/usr/bin/env python3
"""Offline unit checks for examples/error_handling.py (no network, no key).

CI runs this on Python 3.8-3.12 so the copy-paste handlers are proven to
behave as documented, not merely to exist.
"""
import importlib.util
import io
import os
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "error_handling.py")

spec = importlib.util.spec_from_file_location("eh", EXAMPLE)
eh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eh)


class Headers(dict):
    def get(self, k, default=None):
        return super().get(k, default)


def check(cond, label):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    print(f"PASS: {label}")


def main():
    # Non-retryable codes must return False; retryable ones True.
    check(eh.handle(401, '{"error":{"message":"x"}}') is False, "401 not retryable")
    check(eh.handle(402, '{"error":{"message":"x"}}') is False, "402 not retryable")
    check(eh.handle(404, '{"error":{"message":"x"}}') is False, "404 not retryable")
    check(eh.handle(429, '{"error":{"message":"x"}}') is True, "429 retryable")
    check(eh.handle(503, '{"error":{"message":"x"}}', request_id="rid") is False,
          "5xx not automatically retryable")

    # Retry-After wins over local backoff.
    check(eh.retry_after_seconds(Headers({"Retry-After": "7"}), 0) == 7.0,
          "Retry-After header wins")
    check(eh.retry_after_seconds(Headers({"Retry-After": "120"}), 0) == 120.0,
          "Retry-After is not silently shortened")
    deadline = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=120), usegmt=True)
    check(90 < eh.retry_after_seconds(Headers({"Retry-After": deadline}), 0) <= 120,
          "HTTP-date Retry-After is honored")
    # Local backoff is bounded and jittered.
    for attempt in range(6):
        v = eh.retry_after_seconds(Headers(), attempt)
        check(0 < v <= 30, f"backoff attempt {attempt} capped at 30s")

    # Malformed / non-JSON bodies must not crash the handler.
    check(eh.handle(418, "plain text body") is False, "unhandled status safe")
    check(eh.handle(401, "") is False, "empty body safe")

    # A 5xx may follow an upstream completion. Verify the request is sent once.
    calls = []
    def fail_with_503(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 503, "upstream", Headers(),
                                     io.BytesIO(b'{"error":{"message":"upstream"}}'))
    with mock.patch.object(eh.urllib.request, "urlopen", side_effect=fail_with_503), \
         mock.patch.object(eh.time, "sleep") as sleeping:
        try:
            eh.chat_with_retries("test-model", [{"role": "user", "content": "hi"}],
                                 api_key="test-only", max_retries=3)
        except urllib.error.HTTPError as error:
            check(error.code == 503, "5xx is returned to the caller")
        else:
            check(False, "5xx is returned to the caller")
        check(len(calls) == 1 and sleeping.call_count == 0,
              "5xx does not send a second billable request")

    # A long server wait must be surfaced rather than retried after a shorter cap.
    calls.clear()
    def rate_limited(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 429, "limited",
                                     Headers({"Retry-After": "120"}), io.BytesIO(b'{}'))
    with mock.patch.object(eh.urllib.request, "urlopen", side_effect=rate_limited), \
         mock.patch.object(eh.time, "sleep") as sleeping:
        try:
            eh.chat_with_retries("test-model", [{"role": "user", "content": "hi"}],
                                 api_key="test-only", max_retries=3)
        except urllib.error.HTTPError as error:
            check(error.code == 429, "long Retry-After is returned to caller")
        else:
            check(False, "long Retry-After is returned to caller")
        check(len(calls) == 1 and sleeping.call_count == 0,
              "long Retry-After does not retry early")

    print("\nAll error-handler checks passed.")


if __name__ == "__main__":
    main()
