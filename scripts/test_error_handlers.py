#!/usr/bin/env python3
"""Offline unit checks for examples/error_handling.py (no network, no key).

CI runs this on Python 3.8-3.12 so the copy-paste handlers are proven to
behave as documented, not merely to exist.
"""
import importlib.util
import os
import sys

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
    check(eh.handle(503, '{"error":{"message":"x"}}', request_id="rid") is True,
          "5xx retryable")

    # Retry-After wins over local backoff.
    check(eh.retry_after_seconds(Headers({"Retry-After": "7"}), 0) == 7.0,
          "Retry-After header wins")
    # Local backoff is bounded and jittered.
    for attempt in range(6):
        v = eh.retry_after_seconds(Headers(), attempt)
        check(0 < v <= 30, f"backoff attempt {attempt} capped at 30s")

    # Malformed / non-JSON bodies must not crash the handler.
    check(eh.handle(418, "plain text body") is False, "unhandled status safe")
    check(eh.handle(401, "") is False, "empty body safe")

    print("\nAll error-handler checks passed.")


if __name__ == "__main__":
    main()
