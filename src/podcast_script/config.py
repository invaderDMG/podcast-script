"""C-Config: TOML defaults + CLI merge → ``Config`` dataclass (POD-016).

Implements ADR-0013: stdlib :mod:`tomllib` reads
``~/.config/podcast-script/config.toml`` (or any path the CLI hands
us); :func:`merge` overlays CLI flags on top of those defaults with
**CLI-wins** precedence (AC-US-4.2); :func:`validate` re-runs the same
``--lang`` validation against the merged value regardless of source so a
config-loaded ``lang = "ja"`` is rejected just as harshly as
``--lang ja`` would be (AC-US-4.4 / AC-US-1.5).

Defaults live here, not in :mod:`.cli`, because the CLI must be able to
pass ``None`` for "user didn't set this flag" so the TOML value can show
through. Hardcoding ``model="large-v3"`` in the CLI signature would make
that field win over TOML even when the user typed nothing.

Per ADR-0013 the surface is small (~120 LOC); we keep validation manual
rather than declarative because the field set is tiny and low-churn.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

from .errors import UsageError
from .logging_setup import Verbosity

SUPPORTED_LANGS: tuple[str, ...] = ("es", "en", "pt", "fr", "de", "it", "ca", "eu")
"""The eight v1 language codes locked in SRS §1.7. Mirrors
:data:`podcast_script.cli.SUPPORTED_LANGS`; the cli module re-exports
this so callers that haven't moved to ``Config`` yet keep working."""

SUPPORTED_MODELS: tuple[str, ...] = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
)
"""Whisper model names recognised in v1.0.0. Matches the size table in
``backends/base.MODEL_SIZES_GB`` so first-run notice and validation
agree on which models exist."""

SUPPORTED_BACKENDS: tuple[str, ...] = ("auto", "faster-whisper", "mlx-whisper")
"""``auto`` defers to :func:`select_backend` (POD-017, lands next).
The two concrete names are the published CLI surface."""

SUPPORTED_DEVICES: tuple[str, ...] = ("auto", "cpu", "cuda", "mps")
"""``auto`` lets the backend pick; the other three match the hardware
classes the project supports (CPU on any host, CUDA on Linux+NVIDIA,
MPS on Apple Silicon via mlx-whisper)."""

_DID_YOU_MEAN_MAX_DISTANCE = 2
"""Per AC-US-1.5: only suggest a code within ≤ 2 edits of the typo.
Larger distances surface unrelated codes and confuse more than they
help."""

DEFAULT_CONFIG_PATH: Path = Path.home() / ".config" / "podcast-script" / "config.toml"
"""XDG-style location used when the CLI doesn't pass an explicit path.
Per SRS §1.3, env-var overrides are out of scope for v1 — keeping the
location hardcoded is deliberate."""


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable run-configuration for one CLI invocation (ADR-0013).

    Constructed by :func:`merge` from ``(toml_defaults, cli_overrides)``;
    consumers downstream (cli composition root, pipeline) read the
    fields directly. ``frozen=True`` blocks accidental in-flight mutation
    across stages; ``slots=True`` keeps the in-memory footprint flat.
    """

    input: Path
    output: Path | None
    lang: str
    model: str
    backend: str
    device: str
    force: bool
    verbosity: Verbosity


# Built-in defaults — applied when neither TOML nor CLI sets the field.
# Kept as a private dict (not class defaults on :class:`Config`) so that
# ``Config(**merged)`` is honest about which fields the merge supplied
# vs. which it left to the dataclass to fill in.
_BUILTIN_DEFAULTS: dict[str, Any] = {
    "output": None,
    "model": "large-v3",
    "backend": "auto",
    "device": "auto",
    "force": False,
    "verbosity": "normal",
}


def load_toml_defaults(path: Path) -> dict[str, Any]:
    """Read ``path`` and return its top-level table as a plain ``dict``.

    Returns an empty dict when ``path`` does not exist — this is the
    *normal* case for users who haven't created a config file. Callers
    therefore never need to special-case "no config" and can blindly
    spread the result into :func:`merge`.

    Raises :class:`UsageError` (exit 2) on malformed TOML so a typo in
    the user's config produces a clean message rather than a stack
    trace bubbling out of :mod:`tomllib`.
    """
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(f"invalid TOML in {path}: {exc}") from exc


def merge(
    *,
    toml_defaults: dict[str, Any],
    cli_overrides: dict[str, Any],
) -> Config:
    """Merge ``toml_defaults`` and ``cli_overrides`` into a validated ``Config``.

    Precedence (lowest-wins-first → highest-wins-last):
    1. :data:`_BUILTIN_DEFAULTS` for fields neither side sets.
    2. ``toml_defaults`` (parsed config file).
    3. ``cli_overrides``, but only entries whose value is not ``None`` —
       a ``None`` CLI value means "the user didn't pass this flag", so
       the TOML/default underneath shows through (AC-US-4.1).

    Raises :class:`UsageError` (exit 2) when:
    * ``input`` is missing — there is nothing to transcribe.
    * ``lang`` is missing from both config and CLI (AC-US-4.3).
    * any whitelisted field carries a value outside its allowed set
      (AC-US-4.4 + the AC-US-1.5 did-you-mean for ``lang``).
    """
    cli_set = {k: v for k, v in cli_overrides.items() if v is not None}
    merged: dict[str, Any] = {**_BUILTIN_DEFAULTS, **toml_defaults, **cli_set}

    if "input" not in merged:
        raise UsageError("INPUT path is required")
    if "lang" not in merged:
        raise _missing_lang_error()

    merged["input"] = Path(merged["input"])
    if merged["output"] is not None:
        merged["output"] = Path(merged["output"])

    try:
        cfg = Config(**merged)
    except TypeError as exc:
        # Unknown TOML key: dataclass rejects it — translate to UsageError
        # so the user sees an actionable message, not a TypeError trace.
        raise UsageError(f"unrecognized config field: {exc}") from exc

    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    """Validate every whitelisted field on ``cfg``; raise on any miss.

    ``lang`` uses the same did-you-mean machinery as :mod:`.cli` so a
    config-loaded typo (AC-US-4.4) gets the same hint as a CLI typo
    (AC-US-1.5). The other three whitelists raise plain messages —
    they're rare enough that did-you-mean noise isn't worth the LoC.
    """
    if cfg.lang not in SUPPORTED_LANGS:
        supported = ", ".join(SUPPORTED_LANGS)
        suggestion = _closest_supported_lang(cfg.lang)
        base = f"unknown lang {cfg.lang!r}; supported: {supported}"
        if suggestion is not None:
            raise UsageError(f"{base}; did you mean `{suggestion}`?")
        raise UsageError(base)

    if cfg.model not in SUPPORTED_MODELS:
        raise UsageError(f"unknown model {cfg.model!r}; supported: {', '.join(SUPPORTED_MODELS)}")

    if cfg.backend not in SUPPORTED_BACKENDS:
        raise UsageError(
            f"unknown backend {cfg.backend!r}; supported: {', '.join(SUPPORTED_BACKENDS)}"
        )

    if cfg.device not in SUPPORTED_DEVICES:
        raise UsageError(
            f"unknown device {cfg.device!r}; supported: {', '.join(SUPPORTED_DEVICES)}"
        )

    if cfg.verbosity not in get_args(Verbosity):
        raise UsageError(
            f"unknown verbosity {cfg.verbosity!r}; supported: {', '.join(get_args(Verbosity))}"
        )


def _missing_lang_error() -> UsageError:
    supported = ", ".join(SUPPORTED_LANGS)
    return UsageError(f"--lang is required (e.g. --lang es). Supported: {supported}")


def _closest_supported_lang(code: str) -> str | None:
    """Return the closest supported code within ≤ 2 edits, or ``None``.

    Ties break by :data:`SUPPORTED_LANGS` order so the suggestion is
    deterministic across runs (e.g. ``es`` wins over ``en`` if both are
    equidistant). Mirrors the cli helper of the same name; the
    duplication is small enough not to warrant a shared helper module
    until a third caller appears.
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
    """Standard edit distance; ADR-0013 forbids new runtime deps so we
    inline rather than pulling in ``rapidfuzz``. Cost is negligible on
    2-to-~8-character codes."""
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


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "SUPPORTED_BACKENDS",
    "SUPPORTED_DEVICES",
    "SUPPORTED_LANGS",
    "SUPPORTED_MODELS",
    "Config",
    "load_toml_defaults",
    "merge",
    "validate",
]
