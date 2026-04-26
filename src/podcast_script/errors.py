"""Typed exception hierarchy for podcast-script (ADR-0006).

The exit-code mapping in ``NFR-9`` is part of the published shell-script
contract once v1.0.0 ships (Risk #8), so each exception carries its
exit code and its logfmt ``event`` token as class attributes. Stages
raise these; only ``cli`` translates them into ``typer.Exit(code)``.
"""


class PodcastScriptError(Exception):
    """Base class for all expected, user-actionable errors.

    Subclasses override ``exit_code`` and ``event``. The default values
    here apply to bare ``PodcastScriptError`` instances (catch-all for
    "something the tool itself flagged but doesn't fit a sub-category").
    """

    exit_code: int = 1
    event: str = "error"


class UsageError(PodcastScriptError):
    """Bad CLI invocation: unknown flag, invalid ``--lang``, etc."""

    exit_code = 2
    event = "usage_error"


class InputIOError(PodcastScriptError):
    """Input file unreadable, missing, or its parent directory absent."""

    exit_code = 3
    event = "input_io_error"


class DecodeError(PodcastScriptError):
    """``ffmpeg`` failed to decode the input audio."""

    exit_code = 4
    event = "decode_error"


class ModelError(PodcastScriptError):
    """Whisper model load or download failure (network, disk, API drift)."""

    exit_code = 5
    event = "model_error"


class OutputExistsError(PodcastScriptError):
    """Output path (file or ``--debug`` directory) already exists without ``--force``."""

    exit_code = 6
    event = "output_exists"
