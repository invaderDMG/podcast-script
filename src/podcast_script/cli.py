"""CLI entrypoint for podcast-script (POD-006).

Owns the typer-based ``--lang`` validation surface and the ADR-0006
exception → ``typer.Exit(code)`` translation. Per ADR-0006, this module
is the *only* place that converts :class:`PodcastScriptError` subclasses
into exit codes; stages elsewhere raise the typed exceptions and never
call ``sys.exit`` directly.

The ``--lang`` curated set is locked at SRS §1.7 / Q11; unknown codes are
rejected with a "did you mean?" suggestion via Levenshtein distance ≤ 2
(AC-US-1.5). Missing ``--lang`` (and, once POD-016 lands, no config
fallback) is also a usage error (AC-US-4.3).

The pipeline orchestrator itself lands in POD-008 (SP-2). For now,
:func:`_run_pipeline` is a no-op so the CLI surface can be exercised
end-to-end without the heavy ML stages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .errors import PodcastScriptError, UsageError
from .logging_setup import Verbosity, configure

SUPPORTED_LANGS: tuple[str, ...] = ("es", "en", "pt", "fr", "de", "it", "ca", "eu")
"""The eight v1 ``--lang`` codes (SRS §1.7). Frozen for v1.0.0; expanding
this set is a SemVer-major event because it changes the CLI contract."""

_DID_YOU_MEAN_MAX_DISTANCE = 2
"""Per AC-US-1.5: suggest a code only when its Levenshtein distance to the
typo is ≤ 2. Larger distances would surface unrelated codes as 'suggestions'."""

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def validate_lang(code: str) -> None:
    """Validate ``code`` against the curated v1 ``--lang`` set.

    Raises :class:`UsageError` (exit 2) if ``code`` is not in
    :data:`SUPPORTED_LANGS`. The error message lists all supported codes
    and, when the typo is within Levenshtein distance 2 of a supported
    code, appends a ``did you mean `<closest>`?`` suggestion.
    """
    if code in SUPPORTED_LANGS:
        return

    supported = ", ".join(SUPPORTED_LANGS)
    suggestion = _closest_supported_lang(code)
    base = f"unknown --lang {code!r}; supported: {supported}"
    if suggestion is not None:
        raise UsageError(f"{base}; did you mean `{suggestion}`?")
    raise UsageError(base)


def _missing_lang_error() -> UsageError:
    supported = ", ".join(SUPPORTED_LANGS)
    return UsageError(f"--lang is required (e.g. --lang es). Supported: {supported}")


def _closest_supported_lang(code: str) -> str | None:
    """Return the closest supported code within ≤ 2 edits, or ``None``.

    Ties are broken by :data:`SUPPORTED_LANGS` order — i.e. ``es`` wins
    over ``en`` if both are equidistant — which makes the suggestion
    deterministic across runs.
    """
    best: tuple[int, str] | None = None
    for candidate in SUPPORTED_LANGS:
        distance = _levenshtein(code, candidate)
        if distance > _DID_YOU_MEAN_MAX_DISTANCE:
            continue
        if best is None or distance < best[0]:
            best = (distance, candidate)
    return best[1] if best is not None else None


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein edit distance.

    Implemented inline rather than via a third-party ``rapidfuzz``-style
    dep because ADR-0013 forbids new runtime deps for v1; the cost on
    2-to-~8-character strings is negligible.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            substitute = previous[j - 1] + (ca != cb)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


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
    backend: str | None,
    device: str,
    force: bool,
    debug: bool,
) -> None:
    """Pipeline placeholder. Wired in POD-008 (SP-2).

    Kept as a typed seam so the CLI parses, validates, and dispatches today
    without dragging the orchestrator's heavy imports (ADR-0011) into the
    CLI surface tests.
    """
    del input_path, output_path, lang, model, backend, device, force, debug


@app.command()
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
        str,
        typer.Option(
            "--model", help="Whisper model: tiny|base|small|medium|large-v3|large-v3-turbo."
        ),
    ] = "large-v3",
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help="Whisper backend: faster-whisper|mlx-whisper. Auto-selected by platform.",
        ),
    ] = None,
    device: Annotated[
        str, typer.Option("--device", help="Compute device: auto|cpu|cuda|mps.")
    ] = "auto",
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
        if lang is None:
            raise _missing_lang_error()
        validate_lang(lang)

        resolved_output = output if output is not None else input_path.with_suffix(".md")
        _run_pipeline(
            input_path=input_path,
            output_path=resolved_output,
            lang=lang,
            model=model,
            backend=backend,
            device=device,
            force=force,
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


def _cli_main() -> None:
    """Entry point for ``python -m podcast_script`` and the console-script shim."""
    app()
