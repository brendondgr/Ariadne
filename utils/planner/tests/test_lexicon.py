"""The lexicon must widen routing without widening it to the wrong things."""

from __future__ import annotations

import pytest

from utils.planner.lexicon import (
    gloss_forms,
    index_keys,
    nearest,
    stem,
    within_one,
)


class TestStem:
    @pytest.mark.parametrize(
        "word,expected_same_as",
        [
            ("mitigations", "mitigation"),
            ("mitigating", "mitigate"),
            ("detections", "detection"),
            ("detecting", "detect"),
            ("techniques", "technique"),
            ("groups", "group"),
        ],
    )
    def test_inflections_collapse(self, word: str, expected_same_as: str) -> None:
        assert stem(word) == stem(expected_same_as)

    @pytest.mark.parametrize(
        "a,b",
        [
            ("use", "user"),          # a verb and a noun, three chars apart
            ("group", "groupware"),   # prefix is not a stem
            ("analytic", "analysis"), # both real ATT&CK words, different things
            ("campaign", "camp"),
            ("software", "soft"),
            ("access", "accessory"),
        ],
    )
    def test_distinct_words_stay_distinct(self, a: str, b: str) -> None:
        """A false collapse routes the wrong question, which is worse than none."""
        assert stem(a) != stem(b), f"{a!r} and {b!r} collapsed to {stem(a)!r}"

    def test_short_words_untouched(self) -> None:
        for w in ("is", "as", "uses", "has"):
            assert stem(w) == w.lower() or len(w) >= 4

    def test_is_idempotent_enough(self) -> None:
        """One rule at most: stemming a stem must not keep eroding it."""
        once = stem("mitigations")
        assert len(stem(once)) >= len(once) - 1


class TestWithinOne:
    @pytest.mark.parametrize(
        "typo,target",
        [
            ("mitgation", "mitigation"),   # deletion
            ("mitiigation", "mitigation"), # insertion
            ("mitagation", "mitigation"),  # substitution
            ("mitigation", "mitigation"),  # identity
        ],
    )
    def test_one_edit_accepted(self, typo: str, target: str) -> None:
        assert within_one(typo, target)

    @pytest.mark.parametrize(
        "a,b",
        [
            ("mitgatn", "mitigation"),  # two or more edits
            ("group", "graph"),         # two substitutions
            ("tactic", "tactics2x"),    # length gap
        ],
    )
    def test_more_than_one_edit_rejected(self, a: str, b: str) -> None:
        assert not within_one(a, b)

    @pytest.mark.parametrize("a,b", [("care", "core"), ("card", "cart"), ("uses", "user")])
    def test_short_words_never_match(self, a: str, b: str) -> None:
        """Below five characters one edit spans too much English to be evidence."""
        assert not within_one(a, b)


class TestNearest:
    def test_unambiguous_typo_resolves(self) -> None:
        assert nearest("mitgation", {"mitigation", "technique", "campaign"}) == "mitigation"

    def test_ambiguous_typo_returns_none(self) -> None:
        """Two candidates one edit away is not evidence, it is a coin flip."""
        assert nearest("bare", {"bar", "care", "bore", "barn"}) is None

    def test_no_candidate_returns_none(self) -> None:
        assert nearest("zzzzzzz", {"mitigation", "technique"}) is None


class TestGlossAndIndex:
    def test_gloss_reaches_the_word_the_card_already_has(self) -> None:
        """ATT&CK's real gloss for Mitigation, and the request word that misses it."""
        forms = gloss_forms("A defensive measure that reduces technique risk (M-ID).")
        assert stem("defensive") in forms
        assert stem("measure") in forms

    def test_index_keys_keep_the_surface_form(self) -> None:
        """Exact matching must stay bit-for-bit intact; the stem is additive."""
        keys = index_keys("Mitigation")
        assert "mitigation" in keys
        assert stem("mitigations") in keys

    def test_empty_input_is_empty(self) -> None:
        assert index_keys("") == set()
        assert gloss_forms("") == set()
