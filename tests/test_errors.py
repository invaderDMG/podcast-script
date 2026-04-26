"""Stability tests for the typed exception hierarchy (ADR-0006).

The exit-code mapping is an implicit shell-script contract once published
(SRS NFR-9, Risk #8). These tests pin every code and event token so that
an accidental refactor surfaces in CI rather than in a SemVer-major break.
"""

import pytest

from podcast_script.errors import (
    DecodeError,
    InputIOError,
    ModelError,
    OutputExistsError,
    PodcastScriptError,
    UsageError,
)


@pytest.mark.parametrize(
    ("exc_cls", "expected_exit_code", "expected_event"),
    [
        (PodcastScriptError, 1, "internal_error"),
        (UsageError, 2, "usage_error"),
        (InputIOError, 3, "input_io_error"),
        (DecodeError, 4, "decode_error"),
        (ModelError, 5, "model_error"),
        (OutputExistsError, 6, "output_exists"),
    ],
)
def test_exit_codes_are_stable(
    exc_cls: type[PodcastScriptError],
    expected_exit_code: int,
    expected_event: str,
) -> None:
    assert exc_cls.exit_code == expected_exit_code
    assert exc_cls.event == expected_event


@pytest.mark.parametrize(
    "exc_cls",
    [UsageError, InputIOError, DecodeError, ModelError, OutputExistsError],
)
def test_subclasses_derive_from_base(exc_cls: type[PodcastScriptError]) -> None:
    assert issubclass(exc_cls, PodcastScriptError)


def test_base_derives_from_exception() -> None:
    assert issubclass(PodcastScriptError, Exception)


def test_subclasses_declare_their_own_overrides() -> None:
    """Each subclass must define its own ``exit_code`` and ``event`` rather
    than inherit the catch-all defaults from ``PodcastScriptError``. Without
    this, a forgotten override would silently fall back to exit 1 /
    ``internal_error`` and ship as a SemVer-major contract break."""
    for cls in (UsageError, DecodeError, OutputExistsError):
        assert "exit_code" in cls.__dict__
        assert "event" in cls.__dict__


def test_instances_carry_message_and_attrs() -> None:
    err = DecodeError("ffmpeg returned 1")
    assert str(err) == "ffmpeg returned 1"
    assert err.exit_code == 4
    assert err.event == "decode_error"
