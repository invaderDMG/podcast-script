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

from podcast_script.logging_setup import LogfmtFormatter


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
