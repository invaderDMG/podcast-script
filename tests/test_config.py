"""Tests for ``config.py`` (POD-016 — US-4 / ADR-0013).

The four acceptance criteria split cleanly across the public API of
``config``:

* AC-US-4.1 — TOML defaults flow into ``Config`` when CLI omits the
  flag (covered by ``test_toml_defaults_provide_lang_when_cli_omits``).
* AC-US-4.2 — CLI wins on conflict (covered by
  ``test_cli_overrides_win_over_toml_defaults``).
* AC-US-4.3 — no config + no ``--lang`` → ``UsageError`` exit 2
  (covered by ``test_merge_raises_when_lang_is_unset_anywhere``).
* AC-US-4.4 — config-loaded lang revalidates the same as a CLI lang
  (covered by ``test_merge_rejects_unsupported_lang_from_toml``).

Tests target the merge-level public surface (``load_toml_defaults`` and
``merge``) so the tests survive the dataclass shape evolving — only
behavior the SRS commits to is asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from podcast_script import config
from podcast_script.errors import UsageError


def test_load_toml_defaults_returns_empty_dict_for_missing_path(tmp_path: Path) -> None:
    """A missing config file is the *normal* case — running with no
    config and a complete CLI must not error. ADR-0013 sketch returns
    an empty dict; we lock that contract here so callers can blindly
    spread the result into ``merge``.
    """
    missing = tmp_path / "config.toml"
    assert not missing.exists()

    assert config.load_toml_defaults(missing) == {}


def test_load_toml_defaults_parses_supported_keys(tmp_path: Path) -> None:
    """Smoke that ``tomllib`` is wired at all and that the keys we
    expect to see (``lang`` + ``model``) come back as plain ``str``.
    """
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('lang = "es"\nmodel = "large-v3"\n', encoding="utf-8")

    assert config.load_toml_defaults(cfg_path) == {"lang": "es", "model": "large-v3"}


def test_toml_defaults_provide_lang_when_cli_omits(tmp_path: Path) -> None:
    """AC-US-4.1 — running with no ``--lang`` falls back to the TOML
    ``lang``; the run proceeds without error.
    """
    toml_defaults = {"lang": "es", "model": "large-v3"}
    cli_overrides = {"input": tmp_path / "ep.mp3", "lang": None, "model": None}

    cfg = config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

    assert cfg.lang == "es"
    assert cfg.model == "large-v3"


def test_cli_overrides_win_over_toml_defaults(tmp_path: Path) -> None:
    """AC-US-4.2 — CLI ``--lang en --model tiny`` beats the same fields
    in TOML.
    """
    toml_defaults = {"lang": "es", "model": "large-v3"}
    cli_overrides = {"input": tmp_path / "ep.mp3", "lang": "en", "model": "tiny"}

    cfg = config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

    assert cfg.lang == "en"
    assert cfg.model == "tiny"


def test_merge_raises_when_lang_is_unset_anywhere(tmp_path: Path) -> None:
    """AC-US-4.3 — no config and no ``--lang`` exits 2; the message
    must list the eight supported codes so the user can self-correct.
    """
    cli_overrides = {"input": tmp_path / "ep.mp3", "lang": None}

    with pytest.raises(UsageError) as excinfo:
        config.merge(toml_defaults={}, cli_overrides=cli_overrides)

    assert excinfo.value.exit_code == 2
    msg = str(excinfo.value)
    # The eight v1 codes from SRS §1.7 — every one must appear.
    for code in ("es", "en", "pt", "fr", "de", "it", "ca", "eu"):
        assert code in msg


def test_merge_expands_tilde_in_toml_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0013 §Decision step 5 — ``Path(str).expanduser().resolve()``.

    A TOML ``output = "~/episodes/ep.md"`` must reach the pipeline as
    ``<HOME>/episodes/ep.md`` already absolute, otherwise downstream
    code (``_check_output_path``, atomic-write) sees a literal ``~``
    in the path and the run fails for the wrong reason.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "episodes").mkdir()

    toml_defaults = {"lang": "es", "output": "~/episodes/ep.md"}
    cli_overrides = {"input": "~/in.mp3", "lang": None}

    cfg = config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

    assert cfg.input == (tmp_path / "in.mp3").resolve()
    assert cfg.output == (tmp_path / "episodes" / "ep.md").resolve()


def test_merge_rejects_unsupported_lang_from_toml(tmp_path: Path) -> None:
    """AC-US-4.4 — config-loaded ``lang = "ja"`` triggers the same
    AC-US-1.5 validation as a CLI ``--lang ja`` would (exit 2).
    """
    toml_defaults = {"lang": "ja"}
    cli_overrides = {"input": tmp_path / "ep.mp3", "lang": None}

    with pytest.raises(UsageError) as excinfo:
        config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

    assert excinfo.value.exit_code == 2
    assert "ja" in str(excinfo.value)
