"""Tests for ``progress.py`` (POD-013 — US-3 / ADR-0010).

The module owns the construction of the :class:`rich.progress.Progress`
instance the pipeline ticks during a run. Pipeline-level wiring +
per-segment ticking lands in cycle B.
"""

from __future__ import annotations

import io
from typing import IO, cast

import pytest

from podcast_script import progress as progress_module
from podcast_script.progress import (
    DECODE_TASK,
    SEGMENT_TASK,
    TRANSCRIBE_TASK,
    make_progress,
)


def test_make_progress_registers_three_named_tasks_in_canonical_order() -> None:
    """AC-US-3.1 — three named phases (decode, segment, transcribe).

    Order matters because the bar renders top-to-bottom; the user
    reads the run's lifecycle straight off the screen. Names are
    locked because shell wrappers may grep them out of ``--debug``
    captures.
    """
    bar = make_progress()

    descriptions = [bar.tasks[i].description for i in range(len(bar.tasks))]

    assert descriptions == ["decode", "segment", "transcribe"]
    # Public constants for callers — keeps task lookup typed and
    # protects against typos (a missed key = silently no-op tick).
    assert bar.tasks[0].id == DECODE_TASK
    assert bar.tasks[1].id == SEGMENT_TASK
    assert bar.tasks[2].id == TRANSCRIBE_TASK


def test_decode_and_segment_tasks_are_single_step_phases() -> None:
    """Decode + segment are atomic — they either run or don't. Total =
    1 so the bar shows 0% while running and 100% when advanced once.
    Transcribe (per ADR-0010) gets its total set later when the
    segmenter pass finishes; here it starts at 0 with no fixed total.
    """
    bar = make_progress()

    assert bar.tasks[DECODE_TASK].total == 1
    assert bar.tasks[SEGMENT_TASK].total == 1
    # Transcribe total is set by the pipeline once it knows
    # ``len(speech_segments)`` (ADR-0010); ``None`` means "not yet
    # known" in rich's API.
    assert bar.tasks[TRANSCRIBE_TASK].total is None


def test_make_progress_disabled_when_stderr_is_not_a_tty() -> None:
    """AC-US-3.2 — non-TTY stderr (piped to a file) must not paint
    ANSI control sequences. Rich's Progress respects ``disable=True``
    by suppressing all rendering. We pass an explicit non-TTY stream
    so the test is hermetic from the runner's actual stderr state.
    """
    pipe_stream: io.StringIO = io.StringIO()  # not a TTY by definition
    bar = make_progress(file=pipe_stream)

    assert bar.disable is True
    # Sanity — starting and advancing on a disabled bar is a no-op
    # but must not raise. Shell wrappers piping stderr to a file
    # should observe nothing from rich on stderr.
    bar.start()
    bar.advance(DECODE_TASK, 1)
    bar.stop()

    assert pipe_stream.getvalue() == ""


def test_make_progress_enabled_when_stderr_is_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inverse of the previous: a fake TTY-shaped stream gets a live
    bar. We don't render the bar here (transient, hard to assert),
    just verify it isn't disabled."""

    class _FakeTtyStream:
        def isatty(self) -> bool:
            return True

        def write(self, _s: str) -> int:
            return 0

        def flush(self) -> None:
            pass

    # ``IO[str]`` is structural at runtime; the cast keeps mypy happy
    # without forcing the fake to inherit from io.IOBase (which would
    # bring in a half-dozen abstract methods we don't need).
    bar = make_progress(file=cast("IO[str]", _FakeTtyStream()))

    assert bar.disable is False


def test_make_progress_factory_is_idempotent() -> None:
    """Two calls return two distinct ``Progress`` instances. POD-014
    + the cli composition root should be free to construct one per
    run without spooky shared state.
    """
    a = make_progress()
    b = make_progress()
    assert a is not b
    assert a.tasks[DECODE_TASK].id == b.tasks[DECODE_TASK].id  # canonical id


def test_progress_module_re_exports_the_rich_progress_type() -> None:
    """Callers should be able to type-annotate against the module's
    re-export rather than reaching into ``rich.progress`` directly —
    keeps the dep surface visible from one import in pipeline.py.
    """
    from rich.progress import Progress

    assert progress_module.Progress is Progress
