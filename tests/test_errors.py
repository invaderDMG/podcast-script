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
        (PodcastScriptError, 1, "error"),
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


def test_attrs_are_class_level_not_instance_only() -> None:
    """exit_code / event must resolve on the class, not just on instances —
    callers (CLI translator) inspect them on caught objects, but tests +
    docs read them off the class. ADR-0006 names them as class attrs."""
    for cls in (UsageError, DecodeError, OutputExistsError):
        assert "exit_code" in cls.__dict__ or any("exit_code" in c.__dict__ for c in cls.__mro__)


def test_instances_carry_message_and_attrs() -> None:
    err = DecodeError("ffmpeg returned 1")
    assert str(err) == "ffmpeg returned 1"
    assert err.exit_code == 4
    assert err.event == "decode_error"
