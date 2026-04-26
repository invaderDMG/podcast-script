"""Tests for the logging setup (POD-003 initial cut, ADR-0008 + NFR-10).

The on-stderr bytes are an implicit contract once v1.0.0 ships (Risk #9):
operators grep for ``event=…`` tokens and parse logfmt key=value pairs.
These tests pin the formatter shape so accidental drift (a stray space, a
re-ordered key, a missing quote) surfaces in CI.

Event-catalogue enforcement (the 22 frozen tokens) is out of scope for
POD-003 — that lands in POD-015. Here we only pin the *mechanics* of the
formatter and the wiring of ``RichHandler`` through ``Progress.console``.
"""

import logging
from collections.abc import Generator

import pytest
from rich.logging import RichHandler
from rich.progress import Progress

from podcast_script.logging_setup import LogfmtFormatter, Verbosity, configure


def _record(level: int, msg: str = "", **extra: object) -> logging.LogRecord:
    """Build a LogRecord with ``extra`` attributes attached, mirroring what
    ``logger.info(msg, extra={...})`` produces."""
    record = logging.LogRecord(
        name="podcast_script",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=None,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestLogfmtFormatter:
    def test_emits_level_first_then_event(self) -> None:
        line = LogfmtFormatter().format(_record(logging.INFO, event="startup"))

        assert line == "level=info event=startup"

    def test_appends_extras_after_event_in_insertion_order(self) -> None:
        line = LogfmtFormatter().format(
            _record(logging.INFO, event="model_load_done", model="tiny", duration_wall_s=1.5),
        )

        assert line == "level=info event=model_load_done model=tiny duration_wall_s=1.5"

    @pytest.mark.parametrize(
        ("value", "rendered"),
        [
            ("ffmpeg returned 1", '"ffmpeg returned 1"'),
            ("a=b", '"a=b"'),
            ('he said "hi"', '"he said \\"hi\\""'),
            ("", '""'),
        ],
        ids=["whitespace", "equals", "embedded-quote", "empty-string"],
    )
    def test_quotes_values_with_whitespace_equals_or_quote(self, value: str, rendered: str) -> None:
        line = LogfmtFormatter().format(_record(logging.ERROR, event="decode_error", cause=value))

        assert line == f"level=error event=decode_error cause={rendered}"


@pytest.fixture
def reset_logger() -> Generator[logging.Logger]:
    """Hand back the ``podcast_script`` logger with no handlers attached.

    ``configure`` mutates a process-global ``logging.Logger``; without this
    fixture, handlers leak across tests and assertions become order-dependent.
    """
    logger = logging.getLogger("podcast_script")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    yield logger
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


class TestConfigure:
    @pytest.mark.parametrize(
        ("verbosity", "expected_level"),
        [
            ("quiet", logging.ERROR),
            ("normal", logging.INFO),
            ("verbose", logging.DEBUG),
            ("debug", logging.DEBUG),
        ],
    )
    def test_sets_logger_level_per_verbosity(
        self,
        reset_logger: logging.Logger,
        verbosity: Verbosity,
        expected_level: int,
    ) -> None:
        logger = configure(verbosity, progress=None)

        assert logger.name == "podcast_script"
        assert logger.level == expected_level

    def test_uses_stderr_console_when_no_progress(
        self,
        reset_logger: logging.Logger,
    ) -> None:
        logger = configure("normal", progress=None)

        (handler,) = (h for h in logger.handlers if isinstance(h, RichHandler))
        assert handler.console.stderr is True

    def test_reuses_progress_console_when_progress_passed(
        self,
        reset_logger: logging.Logger,
    ) -> None:
        progress = Progress()

        logger = configure("normal", progress=progress)

        (handler,) = (h for h in logger.handlers if isinstance(h, RichHandler))
        assert handler.console is progress.console
