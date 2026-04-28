"""CLI entrypoint for podcast-script (POD-006 + POD-016).

Owns the typer surface and the ADR-0006 exception → ``typer.Exit(code)``
translation. Per ADR-0006, this module is the *only* place that converts
:class:`PodcastScriptError` subclasses into exit codes; stages elsewhere
raise the typed exceptions and never call ``sys.exit`` directly.

The ``--lang`` curated set is locked at SRS §1.7 / Q11; the validator —
including the Levenshtein-≤-2 did-you-mean (AC-US-1.5) — lives in
:mod:`.config` and is re-exported here for backward compatibility with
callers that imported the cli helpers directly.

POD-016 inverts the previous "CLI wins implicitly" model: the CLI
collects each flag as ``None`` when the user didn't pass it, hands the
dict (plus the parsed TOML defaults from
:data:`~podcast_script.config.DEFAULT_CONFIG_PATH`) to
:func:`~podcast_script.config.merge`, and runs the pipeline against the
merged :class:`~podcast_script.config.Config`. Defaults (``model =
large-v3``, ``device = auto``, …) live in :mod:`.config`, not here, so
TOML can show through any flag the user didn't type (AC-US-4.1).

POD-008 wired :class:`~podcast_script.pipeline.Pipeline` behind
:func:`_run_pipeline`; the cli is the composition root that hands real
stages to the orchestrator (ADR-0002). Until POD-010 / POD-011 /
POD-018-020 land, the stub stages defined in this module produce a
placeholder Markdown body so the smoke path works end-to-end without
the heavy ML deps.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from . import config as _config
from .config import SUPPORTED_LANGS, validate_lang
from .errors import InputIOError, OutputExistsError, PodcastScriptError
from .logging_setup import configure

if TYPE_CHECKING:
    from .logging_setup import Verbosity

# Re-exported so existing imports (``from podcast_script.cli import
# SUPPORTED_LANGS, validate_lang``) keep working post-POD-016.
__all__ = ["SUPPORTED_LANGS", "app", "validate_lang"]

# Exit-code table required in --help by SRS §9.1 (line 430): "lists every
# flag, the eight supported --lang codes, AND the documented exit-code
# table (NFR-9)". Codes themselves are owned by the exception classes in
# errors.py per ADR-0006; this is the human-readable surface.
#
# The leading ``\b`` is Click's "do not reflow this paragraph" marker —
# required because Click otherwise rewraps the epilog into one run-on
# line. Typer renders this through Click when ``rich_markup_mode=None``.
_EXIT_CODE_EPILOG = (
    "\b\n"
    "Exit codes (NFR-9):\n"
    "  0  success\n"
    "  1  generic / unexpected internal error\n"
    "  2  usage error (bad flags, missing/unsupported --lang, ffmpeg not on PATH)\n"
    "  3  input I/O error (input not found, output parent missing)\n"
    "  4  decode error (ffmpeg failed)\n"
    "  5  model / network error\n"
    "  6  output exists without --force"
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode=None,
)


def _check_output_path(resolved_output: Path, *, force: bool) -> None:
    """Pre-flight gate for the resolved output path (POD-022, US-6).

    Two ACs are enforced before the pipeline starts so a misconfigured
    invocation costs nothing more than an exit code:

    * AC-US-6.4 — parent directory must already exist (the cli MUST NOT
      create it); raises :class:`InputIOError` (exit 3). Holds with or
      without ``--force``.
    * AC-US-6.1 — if the path already exists and ``--force``/``-f`` was
      not passed, raise :class:`OutputExistsError` (exit 6); the prior
      file is therefore left untouched.

    Order matters: a missing parent makes the existence check
    meaningless, so it is reported first and only then is overwrite
    refused.
    """
    parent = resolved_output.parent
    if not parent.is_dir():
        raise InputIOError(
            f"output parent directory does not exist: {parent}; "
            "create it before re-running, or pass -o/--output with an existing parent"
        )
    if resolved_output.exists() and not force:
        raise OutputExistsError(
            f"refusing to overwrite existing file {resolved_output}; pass --force / -f to opt in"
        )


def _resolve_verbosity(verbose: bool, quiet: bool, debug: bool) -> Verbosity:
    """Map the three flag booleans to a :data:`Verbosity` label.

    Mutual-exclusion enforcement and a richer matrix land in POD-014
    (SP-5); for POD-006 we just pick the strongest signal so log output
    behaves consistently when more than one is passed by accident.
    """
    if debug:
        return "debug"
    if verbose:
        return "verbose"
    if quiet:
        return "quiet"
    return "normal"


def _run_pipeline(
    *,
    input_path: Path,
    output_path: Path,
    lang: str,
    model: str,
    backend: str,
    device: str,
    force: bool,
    debug: bool,
) -> None:
    """Compose the pipeline and run it.

    The cli is the composition root (ADR-0002 §Decision step 4) — it
    instantiates the concrete stages and hands them to :class:`Pipeline`.
    POD-017 plugs the real :class:`WhisperBackend` (faster-whisper or
    mlx-whisper) in via :func:`~podcast_script.backends.base.select_backend`,
    replacing the stub used during SP-1/SP-2. ``--force`` / ``--debug``
    wiring is plumbed but their pipeline-level effects (atomic-rename
    invariant; debug-artifact dir) live in POD-009 / POD-024 — the cli
    just hands them through.
    """
    del force, debug

    from .backends.base import select_backend
    from .decode import decode as decode_audio
    from .pipeline import Pipeline
    from .render import render
    from .segment import InaSpeechSegmenter

    pipeline = Pipeline(
        decode=decode_audio,
        segmenter=InaSpeechSegmenter(),
        backend=select_backend(backend=backend, device=device),
        render=render,
        model=model,
        device=device,
        lang=lang,
    )
    pipeline.run(input_path=input_path, output_path=output_path)


@app.command(epilog=_EXIT_CODE_EPILOG)
def main(
    input_path: Annotated[
        Path,
        typer.Argument(
            metavar="INPUT",
            help="Audio file to transcribe (any format ffmpeg can decode).",
        ),
    ],
    lang: Annotated[
        str | None,
        typer.Option("--lang", help=f"Language code. One of: {', '.join(SUPPORTED_LANGS)}."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output Markdown path. Defaults to <input-stem>.md next to the input.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "-f", "--force", help="Overwrite an existing output file. Default refuses (exit 6)."
        ),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help=(
                "Whisper model: tiny|base|small|medium|large-v3|large-v3-turbo. Default: large-v3."
            ),
        ),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help="Whisper backend: faster-whisper|mlx-whisper. Auto-selected by platform.",
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option("--device", help="Compute device: auto|cpu|cuda|mps. Default: auto."),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Enable debug-level logs.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("-q", "--quiet", help="Suppress informational logs.")
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", help="Retain intermediate artifacts in <input-stem>.debug/ (US-7)."
        ),
    ] = False,
) -> None:
    """Transcribe a podcast audio file to Markdown with music-segment markers."""
    verbosity = _resolve_verbosity(verbose, quiet, debug)
    log = configure(verbosity, progress=None)

    try:
        # POD-016 — load TOML defaults from the locked path (None = absent)
        # then merge with whatever the user typed on argv. ``cli_overrides``
        # carries every flag value as-is; entries with ``None`` mean
        # "user didn't pass this flag" and let TOML / built-in defaults
        # show through (AC-US-4.1). CLI values that *are* set win
        # (AC-US-4.2). Missing lang anywhere → AC-US-4.3.
        toml_defaults = _config.load_toml_defaults(_config.DEFAULT_CONFIG_PATH)
        cli_overrides: dict[str, object] = {
            "input": input_path,
            "output": output,
            "lang": lang,
            "model": model,
            "backend": backend,
            "device": device,
            "force": force,
            "verbosity": verbosity,
        }
        cfg = _config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

        resolved_output = cfg.output if cfg.output is not None else cfg.input.with_suffix(".md")
        _check_output_path(resolved_output, force=cfg.force)
        _run_pipeline(
            input_path=cfg.input,
            output_path=resolved_output,
            lang=cfg.lang,
            model=cfg.model,
            backend=cfg.backend,
            device=cfg.device,
            force=cfg.force,
            debug=debug,
        )
    except PodcastScriptError as exc:
        log.error("", extra={"event": exc.event, "code": exc.exit_code, "cause": str(exc)})
        raise typer.Exit(exc.exit_code) from exc
    except Exception as exc:
        log.error("", extra={"event": "internal_error", "code": 1, "cause": str(exc)})
        if verbosity == "debug":
            raise
        raise typer.Exit(1) from exc
