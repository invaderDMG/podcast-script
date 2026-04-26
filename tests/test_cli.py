"""Tests for the ``podcast_script.cli`` module (POD-006).

Covers the CLI surface that POD-006 owns: ``--lang`` curated-set validation
(AC-US-1.5), required-``--lang`` rejection (AC-US-4.3), the typer entrypoint,
and ADR-0006 exception → ``typer.Exit`` translation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from podcast_script.cli import SUPPORTED_LANGS, app, validate_lang
from podcast_script.errors import UsageError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _touch(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"")
    return p


class TestValidateLang:
    """Pure-function tests for the ``--lang`` validator (AC-US-1.5)."""

    @pytest.mark.parametrize("code", ["es", "en", "pt", "fr", "de", "it", "ca", "eu"])
    def test_accepts_each_supported_code(self, code: str) -> None:
        validate_lang(code)  # no exception

    def test_supported_set_is_locked_to_eight_codes(self) -> None:
        # SRS §1.7 / Q11 — the curated set is part of the v1 contract.
        assert SUPPORTED_LANGS == ("es", "en", "pt", "fr", "de", "it", "ca", "eu")

    def test_unknown_code_raises_usage_error(self) -> None:
        with pytest.raises(UsageError) as exc_info:
            validate_lang("zzzzz")
        # ADR-0006: UsageError carries exit_code=2 + event="usage_error".
        assert exc_info.value.exit_code == 2
        assert exc_info.value.event == "usage_error"

    def test_unknown_code_message_lists_all_eight_supported(self) -> None:
        with pytest.raises(UsageError) as exc_info:
            validate_lang("zzzzz")
        message = str(exc_info.value)
        for code in SUPPORTED_LANGS:
            assert code in message, f"missing supported code {code!r} from message: {message!r}"

    def test_unknown_code_with_no_close_match_omits_suggestion(self) -> None:
        with pytest.raises(UsageError) as exc_info:
            validate_lang("zzzzz")
        # Levenshtein from "zzzzz" to any 2-char code is ≥ 3, so no suggestion.
        assert "did you mean" not in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        ("typo", "expected_suggestion"),
        [
            ("ess", "es"),  # distance 1 (insertion); unambiguous
            ("eng", "en"),  # distance 1; unambiguous
            ("frr", "fr"),  # distance 1; unambiguous
            ("dee", "de"),  # distance 1; unambiguous
            ("itt", "it"),  # distance 1; unambiguous
        ],
    )
    def test_close_typo_suggests_intended_code(self, typo: str, expected_suggestion: str) -> None:
        with pytest.raises(UsageError) as exc_info:
            validate_lang(typo)
        message = str(exc_info.value)
        assert f"did you mean `{expected_suggestion}`" in message

    def test_equidistant_ties_break_by_supported_set_order(self) -> None:
        # "eus" is distance 1 from both "es" (delete 'u') and "eu"
        # (delete 's'). Without a semantic tie-breaker, we pick the first
        # of SUPPORTED_LANGS so the message is deterministic.
        with pytest.raises(UsageError) as exc_info:
            validate_lang("eus")
        assert "did you mean `es`" in str(exc_info.value)

    def test_uppercased_code_is_rejected_as_unknown(self) -> None:
        # SRS §1.7 lists lowercase codes; case-folding is not part of v1
        # (Q11 deliberately scoped to a tested set, not a lookup table).
        with pytest.raises(UsageError):
            validate_lang("ES")


class TestCliMissingLang:
    """AC-US-4.3 — no ``--lang`` flag and (in POD-006) no config layer yet."""

    def test_missing_lang_exits_with_code_2(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file)])
        assert result.exit_code == 2

    def test_missing_lang_message_states_required_and_lists_codes(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file)])
        stderr = result.stderr
        assert "--lang" in stderr
        assert "required" in stderr.lower()
        for code in SUPPORTED_LANGS:
            assert code in stderr, f"missing supported code {code!r} from stderr: {stderr!r}"


class TestCliLangValidationSurface:
    """AC-US-1.5 wired through the typer surface (not just the pure validator)."""

    def test_unknown_lang_exits_with_code_2(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "ja"])
        assert result.exit_code == 2

    def test_unknown_lang_message_has_did_you_mean_when_close(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "ess"])
        assert result.exit_code == 2
        assert "did you mean `es`" in result.stderr

    def test_unknown_lang_emits_logfmt_event_usage_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # ADR-0006 + ADR-0008: the CLI catch-and-translate logs the
        # exception's ``event`` token so operators can grep one fixed key.
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "zzzzz"])
        assert "event=usage_error" in result.stderr
        assert "level=error" in result.stderr


class TestCliGrammarSurface:
    """SRS §9.1 grammar — POD-006 locks the *parser* surface; pipeline-level
    effects of these flags are wired in subsequent SP-1..SP-5 tasks. The
    point here is that the grammar is rejected/accepted as defined, not that
    each flag does its job yet.
    """

    def test_locked_short_flags_are_accepted(self, runner: CliRunner, tmp_path: Path) -> None:
        # SRS §9.1 / Q17 — ``-o``, ``-f``, ``-v``, ``-q`` are the only short
        # aliases. We just need the parser to accept them; downstream tasks
        # exercise the actual behaviour.
        input_file = _touch(tmp_path, "episode.mp3")
        output_file = input_file.with_suffix(".md")
        result = runner.invoke(
            app,
            [str(input_file), "--lang", "es", "-o", str(output_file), "-f", "-v"],
        )
        assert result.exit_code == 0, f"expected 0 got {result.exit_code}; stderr={result.stderr!r}"

    def test_unknown_short_flag_for_lang_is_rejected(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # SRS §9.1 / Q17 — ``-l`` is *not* an alias for ``--lang``; only
        # the four high-traffic options have shorts.
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "-l", "es"])
        assert result.exit_code != 0

    def test_help_lists_locked_grammar_surface(self, runner: CliRunner) -> None:
        # SRS §9.1 + Q17 lock the public CLI grammar for v1.0.0. This test
        # is the regression net: a typer upgrade that quietly drops or
        # renames a flag, or removes a short alias, should fail here.
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for long_flag in (
            "--lang",
            "--output",
            "--force",
            "--model",
            "--backend",
            "--device",
            "--verbose",
            "--quiet",
            "--debug",
        ):
            assert long_flag in result.stdout, f"missing {long_flag} from --help"
        for short_alias in ("-o", "-f", "-v", "-q"):
            assert short_alias in result.stdout, f"missing short alias {short_alias} from --help"
        for code in SUPPORTED_LANGS:
            assert code in result.stdout, f"missing supported lang code {code!r} from --help"

    def test_help_includes_nfr9_exit_code_table(self, runner: CliRunner) -> None:
        # SRS §9.1 (line 430) requires --help to list "every flag, the eight
        # supported --lang codes, AND the documented exit-code table (NFR-9)".
        # The flags + lang codes already render via typer; this asserts the
        # exit-code table is also present so v1.0.0 ships §9.1-compliant.
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Exit codes" in result.stdout
        for code in ("0", "1", "2", "3", "4", "5", "6"):
            assert code in result.stdout, f"missing exit code {code} from --help"
        # Spot-check the categories from NFR-9 are present so the table is
        # human-readable, not just a column of digits.
        assert "usage" in result.stdout.lower()
        assert "decode" in result.stdout.lower()

    def test_long_only_flags_are_accepted(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--lang",
                "es",
                "--model",
                "tiny",
                "--backend",
                "faster-whisper",
                "--device",
                "cpu",
                "--debug",
            ],
        )
        assert result.exit_code == 0, f"stderr={result.stderr!r}"
