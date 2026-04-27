"""Tests for the first-run model-download notice helper (POD-021).

Tier 1 unit tests per ADR-0017 covering ``emit_first_run_notice_if_missing``
in :mod:`podcast_script.backends.base` — the shared seam each
``WhisperBackend`` impl calls from its ``load()`` to satisfy AC-US-5.1
(notice on cache miss within NFR-6's 1-s budget) and AC-US-5.2
(silence on cache hit). The locked event shape is owned by ADR-0012:
``level=info event=model_download model=<name> size_gb=<n>``.
"""

from __future__ import annotations

import logging

import pytest

from podcast_script.backends.base import (
    MODEL_SIZES_GB,
    emit_first_run_notice_if_missing,
)


def _capture_records(logger_name: str) -> tuple[logging.Logger, list[logging.LogRecord]]:
    """Attach a list-recording handler to ``logger_name`` and return both.

    Direct handler attach (rather than ``caplog``) so the test does not
    depend on ``propagate`` flags set by :func:`podcast_script.logging_setup.configure`
    — the helper-level tests exercise the bare logger surface.
    """
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(logger_name)
    handler = _Capture()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, records


def test_emits_locked_shape_on_cache_miss() -> None:
    """AC-US-5.1 + ADR-0012: on a cache miss the helper MUST emit exactly
    one ``level=info event=model_download model=<name> size_gb=<n>``
    record. Shape locked — adding/removing keys is a SemVer-major event
    per SRS §16.1, so this test is the contract test for the helper.
    """
    logger, records = _capture_records("podcast_script.test_first_run.miss")

    emit_first_run_notice_if_missing(
        "large-v3",
        is_cached=lambda _model: False,
        logger=logger,
    )

    assert len(records) == 1
    rec = records[0]
    assert rec.levelno == logging.INFO
    assert getattr(rec, "event", None) == "model_download"
    assert getattr(rec, "model", None) == "large-v3"
    assert getattr(rec, "size_gb", None) == "3"


def test_silent_on_cache_hit_AC_US_5_2() -> None:
    """AC-US-5.2: when the model is already cached, the helper MUST NOT
    emit anything. Subsequent runs after the first download stay silent
    so wrappers piping the tool don't see a spurious ``model_download``
    event on every re-run.
    """
    logger, records = _capture_records("podcast_script.test_first_run.hit")

    emit_first_run_notice_if_missing(
        "large-v3",
        is_cached=lambda _model: True,
        logger=logger,
    )

    assert records == []


def test_unknown_model_falls_back_to_one_gb() -> None:
    """When the user passes a model name we don't recognize (e.g. a
    custom HF repo) we still want the user warned that a download may be
    coming. The helper falls back to a conservative 1 GB estimate — they
    will see ``huggingface_hub``'s real progress bar shortly after.
    """
    logger, records = _capture_records("podcast_script.test_first_run.unknown")

    emit_first_run_notice_if_missing(
        "totally-custom-model",
        is_cached=lambda _model: False,
        logger=logger,
    )

    assert len(records) == 1
    assert getattr(records[0], "size_gb", None) == "1"


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("tiny", "0.075"),
        ("base", "0.14"),
        ("small", "0.46"),
        ("medium", "1.5"),
        ("large-v3", "3"),
        ("large-v3-turbo", "1.6"),
    ],
)
def test_size_formatting_matches_table(model: str, expected: str) -> None:
    """The on-the-wire ``size_gb`` token MUST come from
    :data:`MODEL_SIZES_GB` formatted with ``:g`` — round numbers render
    bare (``3``), fractional ones keep their decimals (``0.075``,
    ``1.5``). Keeps the line short and human-readable while staying
    deterministic across versions.
    """
    logger, records = _capture_records(f"podcast_script.test_first_run.size.{model}")

    emit_first_run_notice_if_missing(
        model,
        is_cached=lambda _model: False,
        logger=logger,
    )

    assert getattr(records[0], "size_gb", None) == expected


def test_known_model_table_covers_v1_supported_set() -> None:
    """The v1 model set the README documents (tiny / base / small /
    medium / large-v3 / large-v3-turbo) MUST all be in
    :data:`MODEL_SIZES_GB` so users running any of them see an accurate
    size in the AC-US-5.1 notice. Adding a model post-v1 is a minor
    update; removing one is breaking.
    """
    required = {"tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"}

    assert required <= MODEL_SIZES_GB.keys()
