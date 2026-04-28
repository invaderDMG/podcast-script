"""Tests for the ``podcast_script.cli`` module (POD-006).

Covers the CLI surface that POD-006 owns: ``--lang`` curated-set validation
(AC-US-1.5), required-``--lang`` rejection (AC-US-4.3), the typer entrypoint,
and ADR-0006 exception → ``typer.Exit`` translation. POD-016 adds the
config-merge surface (AC-US-4.1, AC-US-4.2, AC-US-4.4) at the CLI level.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from podcast_script import config as config_module
from podcast_script.cli import SUPPORTED_LANGS, app, validate_lang
from podcast_script.errors import UsageError


@pytest.fixture(autouse=True)
def _isolated_default_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin :data:`config.DEFAULT_CONFIG_PATH` to a non-existent path.

    Without this fixture every CLI test would pick up whatever
    ``~/.config/podcast-script/config.toml`` happens to exist on the
    machine running the suite — so a developer with a personal config
    setting ``lang = "es"`` would silently mask AC-US-4.3 failures
    (the "no config + no --lang" path). Tests that *want* a config can
    override this fixture by monkeypatching the same attribute again.
    """
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", tmp_path / "no-such-config.toml")


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

    The two flag-acceptance tests stub :func:`podcast_script.cli._run_pipeline`
    to a no-op so they remain pure parser tests after POD-008 wired the real
    Pipeline behind it (which would otherwise fail on the empty fixture file
    with a decode error).
    """

    def test_locked_short_flags_are_accepted(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # SRS §9.1 / Q17 — ``-o``, ``-f``, ``-v``, ``-q`` are the only short
        # aliases. We just need the parser to accept them; downstream tasks
        # exercise the actual behaviour.
        from podcast_script import cli as cli_module

        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **_: None)

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

    def test_long_only_flags_are_accepted(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from podcast_script import cli as cli_module

        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **_: None)

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


class TestOutputExistsCheck:
    """AC-US-6.1 — refuse to overwrite an existing output without ``--force``.

    POD-022: the cli rejects a run before the pipeline starts when the
    resolved output path already exists and ``--force``/``-f`` was not
    passed. The pipeline never runs in this branch, so no monkeypatch is
    needed — exit 6 must surface from the pre-flight gate.
    """

    def test_existing_output_without_force_exits_6(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("hand-edited transcript\n", encoding="utf-8")
        result = runner.invoke(app, [str(input_file), "--lang", "es"])
        assert result.exit_code == 6, f"stderr={result.stderr!r}"

    def test_existing_output_message_names_file_and_suggests_force(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("hand-edited transcript\n", encoding="utf-8")
        result = runner.invoke(app, [str(input_file), "--lang", "es"])
        # AC-US-6.1: stderr names the existing file and instructs --force/-f.
        assert "episode.md" in result.stderr, f"stderr={result.stderr!r}"
        assert "--force" in result.stderr, f"stderr={result.stderr!r}"

    def test_existing_output_unchanged_after_refused_run(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        prior = "hand-edited transcript\n"
        output_file.write_text(prior, encoding="utf-8")
        runner.invoke(app, [str(input_file), "--lang", "es"])
        # AC-US-6.1: "episode.md is left unchanged."
        assert output_file.read_text(encoding="utf-8") == prior

    def test_existing_output_emits_logfmt_event_output_exists(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # ADR-0006 + ADR-0008: every typed-error exit logs the locked
        # ``event`` token (here ``output_exists``, NFR-9 exit 6) so users
        # can grep one fixed key on stderr.
        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("hand-edited\n", encoding="utf-8")
        result = runner.invoke(app, [str(input_file), "--lang", "es"])
        assert "event=output_exists" in result.stderr
        assert "code=6" in result.stderr

    def test_explicit_output_via_dash_o_also_checked(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # The check applies to the *resolved* output path, not just the
        # default ``<input-stem>.md`` — ``-o``/``--output`` flows through
        # the same gate.
        input_file = _touch(tmp_path, "episode.mp3")
        custom = tmp_path / "custom.md"
        custom.write_text("hand-edited\n", encoding="utf-8")
        result = runner.invoke(app, [str(input_file), "--lang", "es", "-o", str(custom)])
        assert result.exit_code == 6, f"stderr={result.stderr!r}"

    def test_force_bypasses_gate(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # POD-022 just opens the gate; POD-023 will lock down the
        # "actually overwrites" + atomic-preservation paths end-to-end
        # (AC-US-6.2 / AC-US-6.3). Here we only assert that ``--force``
        # avoids the exit-6 refusal — pipeline is stubbed.
        from podcast_script import cli as cli_module

        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **_: None)

        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("hand-edited\n", encoding="utf-8")
        result = runner.invoke(app, [str(input_file), "--lang", "es", "--force"])
        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        # Short alias ``-f`` is checked by ``test_locked_short_flags_are_accepted``.

    def test_no_pre_existing_output_runs_pipeline(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Sanity: when the output doesn't exist the gate is a no-op.
        from podcast_script import cli as cli_module

        called: list[Path] = []
        monkeypatch.setattr(
            cli_module,
            "_run_pipeline",
            lambda **kw: called.append(kw["output_path"]),
        )

        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "es"])
        assert result.exit_code == 0
        assert called == [tmp_path / "episode.md"]


class TestMissingParentDir:
    """AC-US-6.4 — resolved output's parent directory does not exist → exit 3.

    Holds with or without ``--force`` (the SRS spelling). The cli MUST NOT
    create the missing parent silently.
    """

    def test_missing_parent_exits_3(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_path = tmp_path / "does-not-exist" / "episode.md"
        result = runner.invoke(app, [str(input_file), "--lang", "es", "-o", str(output_path)])
        assert result.exit_code == 3, f"stderr={result.stderr!r}"

    def test_missing_parent_message_names_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_path = tmp_path / "does-not-exist" / "episode.md"
        result = runner.invoke(app, [str(input_file), "--lang", "es", "-o", str(output_path)])
        assert "does-not-exist" in result.stderr, f"stderr={result.stderr!r}"

    def test_missing_parent_creates_no_directories(self, runner: CliRunner, tmp_path: Path) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        missing_parent = tmp_path / "does-not-exist"
        output_path = missing_parent / "episode.md"
        runner.invoke(app, [str(input_file), "--lang", "es", "-o", str(output_path)])
        assert not missing_parent.exists(), "cli must not create the missing parent"

    def test_missing_parent_with_force_still_exits_3(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # SRS AC-US-6.4: "with or without --force".
        input_file = _touch(tmp_path, "episode.mp3")
        output_path = tmp_path / "does-not-exist" / "episode.md"
        result = runner.invoke(
            app,
            [str(input_file), "--lang", "es", "-f", "-o", str(output_path)],
        )
        assert result.exit_code == 3, f"stderr={result.stderr!r}"

    def test_missing_parent_emits_logfmt_event_input_io_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        input_file = _touch(tmp_path, "episode.mp3")
        output_path = tmp_path / "does-not-exist" / "episode.md"
        result = runner.invoke(app, [str(input_file), "--lang", "es", "-o", str(output_path)])
        assert "event=input_io_error" in result.stderr
        assert "code=3" in result.stderr


class TestForceOverwrite:
    """POD-023 — `--force`/`-f` opt-in path.

    POD-022 opened the gate (refusal without `--force`); POD-023 closes
    out US-6 by demonstrating end-to-end through the cli that:

    * AC-US-6.2 — with ``--force``/``-f``, the existing file is replaced
      by the freshly produced transcript and exit code is 0.
    * AC-US-6.3 — when the run fails *after* the gate, the prior file is
      preserved (atomic-write invariant from POD-009 / ADR-0005); no temp
      file leaks at the resolved output path's directory.

    The pipeline is monkeypatched to keep these tests in the cli's
    Tier-1 boundary (no ffmpeg, no model). The unit-level atomic_write
    invariants are covered separately in ``tests/test_atomic_write.py``.
    """

    def test_force_actually_replaces_existing_output_AC_US_6_2(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-6.2: "the existing episode.md is replaced with the freshly
        # generated transcript and the tool exits 0."
        from podcast_script import atomic_write as atomic_module
        from podcast_script import cli as cli_module

        fresh = "# fresh transcript\n\nbody from this run\n"

        def fake_run_pipeline(**kwargs: object) -> None:
            output_path = kwargs["output_path"]
            assert isinstance(output_path, Path)
            atomic_module.atomic_write(output_path, fresh)

        monkeypatch.setattr(cli_module, "_run_pipeline", fake_run_pipeline)

        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("hand-edited transcript\n", encoding="utf-8")

        result = runner.invoke(app, [str(input_file), "--lang", "es", "--force"])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        assert output_file.read_text(encoding="utf-8") == fresh

    def test_short_dash_f_replaces_existing_output_AC_US_6_2(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-6.2 explicitly names ``-f`` alongside ``--force``.
        from podcast_script import atomic_write as atomic_module
        from podcast_script import cli as cli_module

        fresh = "# fresh\n"

        def fake_run_pipeline(**kwargs: object) -> None:
            output_path = kwargs["output_path"]
            assert isinstance(output_path, Path)
            atomic_module.atomic_write(output_path, fresh)

        monkeypatch.setattr(cli_module, "_run_pipeline", fake_run_pipeline)

        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        output_file.write_text("prior\n", encoding="utf-8")

        result = runner.invoke(app, [str(input_file), "--lang", "es", "-f"])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        assert output_file.read_text(encoding="utf-8") == fresh

    def test_force_propagates_to_pipeline_runner(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Sanity that the cli composition root forwards the resolved
        # ``force=True`` to the pipeline runner — without this, downstream
        # debug-dir refuse-without-force reuse (POD-025) would silently
        # diverge from the cli flag.
        from podcast_script import cli as cli_module

        seen: dict[str, object] = {}

        def fake_run_pipeline(**kwargs: object) -> None:
            seen.update(kwargs)

        monkeypatch.setattr(cli_module, "_run_pipeline", fake_run_pipeline)

        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "es", "--force"])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        assert seen.get("force") is True

    def test_force_run_failure_preserves_prior_file_AC_US_6_3(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-6.3: "Given any failure during transcription after a
        # --force run has begun, when the failure occurs, then the
        # previous episode.md is preserved." Inject a typed pipeline
        # failure that reaches the cli error-translation path; assert
        # the prior bytes are intact and no temp file was left behind.
        from podcast_script import cli as cli_module
        from podcast_script.errors import DecodeError

        def fake_run_pipeline(**_kwargs: object) -> None:
            raise DecodeError("ffmpeg returned nonzero exit (synthetic for AC-US-6.3)")

        monkeypatch.setattr(cli_module, "_run_pipeline", fake_run_pipeline)

        input_file = _touch(tmp_path, "episode.mp3")
        output_file = tmp_path / "episode.md"
        prior = "hand-edited transcript\nDO NOT CLOBBER\n"
        output_file.write_text(prior, encoding="utf-8")

        result = runner.invoke(app, [str(input_file), "--lang", "es", "--force"])

        # ADR-0006: DecodeError → exit code 4.
        assert result.exit_code == 4, f"stderr={result.stderr!r}"
        # AC-US-6.3: prior file survives byte-for-byte.
        assert output_file.read_text(encoding="utf-8") == prior
        # ADR-0005 §Consequences: no ``*.md.tmp`` debris left behind.
        leftover = list(tmp_path.glob("*.md.tmp"))
        assert leftover == [], f"unexpected temp leftovers: {leftover!r}"


class TestCliConfigMerge:
    """POD-016 — US-4 acceptance criteria at the CLI surface.

    AC-US-4.3 already lives in :class:`TestCliMissingLang`. The three
    here cover the config-aware paths: TOML supplies a missing flag,
    CLI overrides TOML, and a TOML-loaded ``lang = "ja"`` is rejected
    just like a CLI ``--lang ja`` would be.
    """

    def _write_config(self, path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def test_toml_lang_used_when_cli_omits_it_AC_US_4_1(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-4.1: with config.toml(lang="es") and no --lang flag,
        # the run proceeds with lang=es. The pipeline is stubbed so the
        # test isolates the merge path from segmenter/backend startup.
        from podcast_script import cli as cli_module

        config_path = tmp_path / "config.toml"
        self._write_config(config_path, 'lang = "es"\nmodel = "large-v3"\n')
        monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", config_path)

        seen: dict[str, object] = {}

        def fake_run_pipeline(**kwargs: object) -> None:
            seen.update(kwargs)

        monkeypatch.setattr(cli_module, "_run_pipeline", fake_run_pipeline)

        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file)])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        assert seen.get("lang") == "es"
        assert seen.get("model") == "large-v3"

    def test_cli_flags_override_toml_AC_US_4_2(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-4.2: same config(lang="es", model="large-v3"), CLI
        # passes --lang en --model tiny → CLI wins on both fields.
        from podcast_script import cli as cli_module

        config_path = tmp_path / "config.toml"
        self._write_config(config_path, 'lang = "es"\nmodel = "large-v3"\n')
        monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", config_path)

        seen: dict[str, object] = {}
        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **kw: seen.update(kw))

        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file), "--lang", "en", "--model", "tiny"])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        assert seen.get("lang") == "en"
        assert seen.get("model") == "tiny"

    def test_unsupported_toml_lang_rejected_AC_US_4_4(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # AC-US-4.4: config.toml(lang="ja") + no --lang → exit 2,
        # same AC-US-1.5 validation as a CLI --lang ja would trigger.
        config_path = tmp_path / "config.toml"
        self._write_config(config_path, 'lang = "ja"\n')
        monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", config_path)

        input_file = _touch(tmp_path, "episode.mp3")
        result = runner.invoke(app, [str(input_file)])

        assert result.exit_code == 2, f"stderr={result.stderr!r}"
        # Same logfmt token as any other usage error (ADR-0006 + ADR-0008).
        assert "event=usage_error" in result.stderr
        assert "ja" in result.stderr
        # AC-US-4.4 says the same validation as AC-US-1.5 fires, which
        # includes the did-you-mean hint when within edit-distance 2.
        # ``ja`` is distance 1 from ``ca`` (j→c) — pin the suggestion so
        # a future refactor that bypasses ``validate_lang`` for the TOML
        # path can't pass this test silently.
        assert "did you mean `ca`" in result.stderr


class TestEventCatalogue:
    """POD-015 — ADR-0012 event catalogue freeze.

    The catalogue is the implicit grep contract for shell scripts wrapping
    the tool (SRS Risk #9). These tests lock the four lifecycle tokens
    that depend on cli orchestration; the phase-boundary tokens are
    covered by ``tests/test_pipeline.py``.
    """

    def _events_in(self, stderr: str) -> list[str]:
        """Pull the ``event=<token>`` value from each logfmt line."""
        out: list[str] = []
        for line in stderr.splitlines():
            for chunk in line.split():
                if chunk.startswith("event="):
                    out.append(chunk.removeprefix("event="))
                    break
        return out

    def test_startup_event_fires_first(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ADR-0012 lifecycle — ``event=startup`` is the first event
        emitted (argv parsed, before any work)."""
        from podcast_script import cli as cli_module

        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **_: None)
        input_file = _touch(tmp_path, "episode.mp3")

        result = runner.invoke(app, [str(input_file), "--lang", "es"])

        assert result.exit_code == 0, f"stderr={result.stderr!r}"
        events = self._events_in(result.stderr)
        assert events, f"no events emitted; stderr={result.stderr!r}"
        assert events[0] == "startup", f"events={events!r}"

    def test_config_loaded_event_fires_after_merge(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ADR-0012 lifecycle — ``event=config_loaded`` fires after the
        cli + TOML merge (AC-US-4.1/4.2 path) succeeds."""
        from podcast_script import cli as cli_module

        monkeypatch.setattr(cli_module, "_run_pipeline", lambda **_: None)
        input_file = _touch(tmp_path, "episode.mp3")

        result = runner.invoke(app, [str(input_file), "--lang", "es"])

        events = self._events_in(result.stderr)
        assert "config_loaded" in events
        # config_loaded comes after startup, before any pipeline event.
        assert events.index("config_loaded") > events.index("startup")
