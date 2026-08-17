"""Tests for the crew-memory embedder fail-open policy (_embed_with_fail_open).

Crew memory is an enhancement, not part of producing the metric view — a
transient embedding failure (SSL/EOF, connection reset, 429/5xx) must never
propagate and fail a flow whose generation already succeeded. Regression for a
production `SSLEOFError` on the embedding endpoint that flipped a completed UCMV
run to FAILED.

Imports only the module-level helper (not EmbedderConfigBuilder), so it avoids
the heavy engine import chain.
"""
import os

os.environ.setdefault("DATABASE_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB_PATH", ":memory:")

import requests  # noqa: E402
from src.engines.crewai.config.embedder_config_builder import _embed_with_fail_open  # noqa: E402


def _no_sleep(_seconds):
    return None


class TestEmbedFailOpen:
    def test_retries_transient_then_succeeds(self):
        calls = {"n": 0}

        def flaky(docs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise requests.exceptions.SSLError("EOF occurred in violation of protocol")
            return [[1.0, 2.0]]

        out = _embed_with_fail_open(flaky, ["x"], dimension=2, max_attempts=3, sleep_fn=_no_sleep)
        assert out == [[1.0, 2.0]]
        assert calls["n"] == 2  # retried once, then succeeded

    def test_fails_open_to_zero_vectors_on_persistent_transport_error(self):
        def always(docs):
            raise requests.exceptions.ConnectionError("connection reset")

        out = _embed_with_fail_open(always, ["a", "b"], dimension=4, max_attempts=3, sleep_fn=_no_sleep)
        assert out == [[0.0] * 4, [0.0] * 4]  # one zero-vector per doc; never raises

    def test_non_retryable_stops_immediately_and_fails_open(self):
        calls = {"n": 0}

        def authfail(docs):
            calls["n"] += 1
            raise Exception("No authentication method available")  # no .retryable flag

        out = _embed_with_fail_open(authfail, ["a"], dimension=3, max_attempts=3, sleep_fn=_no_sleep)
        assert calls["n"] == 1  # not retried (non-transient)
        assert out == [[0.0, 0.0, 0.0]]

    def test_retryable_5xx_is_retried_then_fails_open(self):
        calls = {"n": 0}

        def server_err(docs):
            calls["n"] += 1
            e = Exception("Embedding API error 503: unavailable")
            e.retryable = True  # transient server error
            raise e

        out = _embed_with_fail_open(server_err, ["a"], dimension=2, max_attempts=3, sleep_fn=_no_sleep)
        assert calls["n"] == 3  # retried up to max
        assert out == [[0.0, 0.0]]
