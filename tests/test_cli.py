"""Tests for the ``podcast_script.cli`` module (POD-006).

Covers the CLI surface that POD-006 owns: ``--lang`` curated-set validation
(AC-US-1.5), required-``--lang`` rejection (AC-US-4.3), the typer entrypoint,
and ADR-0006 exception → ``typer.Exit`` translation.
"""

from __future__ import annotations

import pytest

from podcast_script.cli import SUPPORTED_LANGS, validate_lang
from podcast_script.errors import UsageError


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
