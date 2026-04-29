"""C-Progress: rich progress bar for the three pipeline phases (POD-013).

The pipeline (ADR-0002) ticks one task per phase:

* ``decode`` — atomic; advanced once when ``ffmpeg`` returns the PCM.
* ``segment`` — atomic; advanced once when the segmenter pass finishes.
* ``transcribe`` — per ADR-0010, total = ``len(speech_segments)``;
  advanced once per outer-loop iteration over speech segments. This
  keeps the UX identical on Linux/CUDA, Linux/CPU, and Apple Silicon
  (NFR-7) — neither backend's internal yield cadence is observable.

ADR-0008 — the Console used here is shared with the log handler
(:func:`podcast_script.logging_setup.configure`) so progress + log
lines render on the same TTY without tearing.

AC-US-3.2 — non-TTY stderr must not paint ANSI. Rich's ``Progress``
already does the right thing when its target stream's ``.isatty()``
returns ``False`` (``disable=True``), so the cli composition root just
hands the real stderr in. Tests substitute a hermetic ``StringIO`` /
fake-TTY to exercise both branches without depending on the runner's
actual stderr state.
"""

from __future__ import annotations

import sys
from typing import IO

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Public task-id constants. Locked at 0/1/2 to match the registration
# order in :func:`make_progress`. Callers should reach for these
# instead of integer literals so a future refactor that re-orders the
# tasks fails compilation rather than silently no-op'ing ticks.
DECODE_TASK: TaskID = TaskID(0)
SEGMENT_TASK: TaskID = TaskID(1)
TRANSCRIBE_TASK: TaskID = TaskID(2)


def make_progress(*, file: IO[str] | None = None) -> Progress:
    """Build the three-phase progress bar.

    ``file`` is the destination stream (``sys.stderr`` by default — the
    cli passes it explicitly so tests can substitute a non-TTY stream
    to exercise the AC-US-3.2 fallback). Rich's ``Console`` infers
    ``no_color`` / ANSI behaviour from the stream's ``.isatty()``, and
    we mirror that into ``Progress.disable`` so a piped stderr writes
    nothing.

    The returned ``Progress`` already has the three named tasks
    registered; the pipeline calls
    :meth:`~rich.progress.Progress.advance` against the locked task
    IDs (:data:`DECODE_TASK` / :data:`SEGMENT_TASK` /
    :data:`TRANSCRIBE_TASK`).
    """
    stream = file if file is not None else sys.stderr
    is_tty = bool(getattr(stream, "isatty", lambda: False)())

    console = Console(file=stream, force_terminal=is_tty)
    bar = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        # ``disable`` short-circuits all rendering — the AC-US-3.2 path.
        disable=not is_tty,
        # ``transient=False`` keeps the final state visible after the
        # run completes, so ``--debug`` captures or screencasts retain
        # the "decode 100% / segment 100% / transcribe 100%" record.
        transient=False,
    )

    # Decode + segment are atomic; transcribe's total is set by the
    # pipeline once the segmenter pass returns ``len(speech_segments)``.
    bar.add_task("decode", total=1)
    bar.add_task("segment", total=1)
    bar.add_task("transcribe", total=None)

    return bar


__all__ = [
    "DECODE_TASK",
    "SEGMENT_TASK",
    "TRANSCRIBE_TASK",
    "Progress",
    "TaskID",
    "make_progress",
]
