"""Cover for the property-read scoring path.

The defect: a property read's gold is a *value* -- a description, an alias, a
platform name -- placed in ``must_include_related``, which `score_answer_coverage`
resolved through `_surfaced_ids`. That set holds identifiers only, so no property
value could ever be credited and every D1 question scored at most its anchor:
exactly ``1 / (gold_width + 1)``. These tests pin the new rule and, just as
importantly, pin that non-property scoring did not move.
"""

from __future__ import annotations

from utils.evaluation.property_gold import (
    contains_tokens,
    is_property_read,
    normalize_tokens,
    score_property_values,
)
from utils.evaluation.score_e2e import score_answer_coverage
from utils.synthesis.contracts import Claim, SynthesizedAnswer

DESCRIPTION = (
    "Adversaries may use scripts automatically executed at boot or logon "
    "initialization to establish persistence.(Citation: Mandiant APT29 Eye Spy "
    "Email Nov 22) Initialization scripts can be used to perform administrative "
    "functions."
)


def _answer(narrative: str, entity_ids: tuple[str, ...] = ()) -> SynthesizedAnswer:
    return SynthesizedAnswer(
        request="q",
        narrative=narrative,
        claims=[Claim(text=narrative, entity_ids=entity_ids)],
    )


def _property_entry(anchor: str, values: list[str], shape: str) -> dict:
    return {
        "assertions": {"must_include_ids": [anchor], "must_include_related": values},
        "spec": {"steps": [], "shapes": [shape], "anchor_label": shape.split(".")[0]},
    }


class TestNormalisation:
    def test_citations_are_stripped_from_both_sides(self):
        assert "mandiant" not in normalize_tokens(DESCRIPTION)

    def test_punctuation_and_case_do_not_matter(self):
        assert normalize_tokens("Spandex Tempest") == normalize_tokens("spandex, tempest!")


class TestContainment:
    def test_word_boundaries_come_free_with_contiguity(self):
        # A raw substring test would credit gold "True" from the word "truest".
        assert not contains_tokens(normalize_tokens("the truest thing"), normalize_tokens("True"))
        assert contains_tokens(normalize_tokens("is_family: True"), normalize_tokens("True"))

    def test_the_run_must_be_contiguous(self):
        assert not contains_tokens(normalize_tokens("alpha then beta"), normalize_tokens("alpha beta"))

    def test_an_empty_value_is_surfaced_by_nothing(self):
        assert not contains_tokens(normalize_tokens("anything at all"), ())


class TestIsPropertyRead:
    def test_a_property_shape_is_one(self):
        assert is_property_read({"spec": {"steps": [], "shapes": ["Group.aliases"]}})

    def test_a_traversal_shape_is_not(self):
        assert not is_property_read(
            {"spec": {"steps": [{"predicate": "uses"}],
                      "shapes": ["Group -[uses]-> Technique"]}}
        )

    def test_the_golden_catalogue_carries_no_spec_and_is_never_caught(self):
        assert not is_property_read({"assertions": {"must_include_ids": ["T1037"]}})


class TestScorePropertyValues:
    def test_credit_is_the_fraction_surfaced(self):
        got = score_property_values(
            "Also called CHIMBORAZO and Hive0065.",
            ["CHIMBORAZO", "Hive0065", "Spandex Tempest"],
        )
        assert (got["gold"], got["found"]) == (3, 2)
        assert got["missing"] == ["Spandex Tempest"]

    def test_a_truncated_value_earns_nothing(self):
        # Deliberate: half a description is not the answer, and partial credit
        # here would be a tunable knob.
        got = score_property_values(DESCRIPTION[:40], [DESCRIPTION])
        assert got["found"] == 0


class TestScoreAnswerCoverage:
    def test_the_regression_a_stated_description_now_scores_full(self):
        entry = _property_entry("T1037", [DESCRIPTION], "Technique.description")
        answer = _answer(f"T1037 (Boot or Logon Initialization Scripts): {DESCRIPTION}",
                         entity_ids=("T1037",))
        got = score_answer_coverage(entry, answer)
        assert got["coverage"] == 1.0
        assert got["property_read"] is True

    def test_an_answer_naming_only_the_anchor_still_scores_the_old_way(self):
        # The rule credits what the answer says -- it does not blanket-credit.
        # This reproduces the 1/(gold_width+1) figure the whole tier used to get.
        entry = _property_entry("T1037", [DESCRIPTION], "Technique.description")
        answer = _answer("Found 1 record: Boot or Logon Initialization Scripts (T1037).",
                         entity_ids=("T1037",))
        assert score_answer_coverage(entry, answer)["coverage"] == 0.5

    def test_set_valued_property_gold_is_scored_per_value(self):
        entry = _property_entry("G0092", ["CHIMBORAZO", "Hive0065", "Spandex Tempest"],
                                "Group.aliases")
        answer = _answer("G0092 is also called CHIMBORAZO and Hive0065.",
                         entity_ids=("G0092",))
        # anchor + 2 of 3 values, out of 4.
        assert score_answer_coverage(entry, answer)["coverage"] == 0.75

    def test_non_property_entries_are_untouched(self):
        entry = {
            "assertions": {"must_include_ids": ["G0092"],
                           "must_include_related": ["T1037", "T1059"]},
            "spec": {"steps": [{"predicate": "uses"}],
                     "shapes": ["Group -[uses]-> Technique"]},
        }
        answer = _answer("G0092 uses T1037.", entity_ids=("G0092", "T1037"))
        got = score_answer_coverage(entry, answer)
        assert got["coverage"] == 2 / 3
        assert "property_read" not in got

    def test_an_entry_with_no_gold_still_returns_none(self):
        assert score_answer_coverage({"assertions": {}}, _answer("anything")) is None


class TestMarkdownLinks:
    """STIX prose carries links; the composer renders the label and drops the url.

    Without resolving them the url's words sit inside the gold token run and
    break contiguity -- which is not what rule 1 says should happen.
    """

    def test_a_link_matches_its_rendered_label(self):
        gold = "[Operation Spalax](https://attack.mitre.org/campaigns/C0005) was a campaign"
        rendered = "C0005 (Operation Spalax): Operation Spalax was a campaign that targeted"
        assert contains_tokens(normalize_tokens(rendered), normalize_tokens(gold))

    def test_the_url_itself_is_not_treated_as_content(self):
        assert "https" not in normalize_tokens("[x](https://example.org/y)")


class TestBooleanValuesMustBeQualified:
    """Rule 4. A bare "False" is satisfied by any boolean the composer prints.

    The real case: "Can T1072 be applied remotely?", gold ``False``. The answer
    never mentions x_mitre_remote_support, but its trailer carries
    ``revoked: False`` -- which credited the question before this rule existed.
    """

    TRAILER = ("T1072 (Software Deployment Tools) has revoked: False; "
               "stix_type: attack-pattern; x_mitre_is_subtechnique: False.")

    def test_a_different_propertys_boolean_does_not_count(self):
        got = score_property_values(self.TRAILER, ["False"], "x_mitre_remote_support")
        assert got["found"] == 0

    def test_the_named_property_does_count(self):
        got = score_property_values(self.TRAILER, ["False"], "x_mitre_is_subtechnique")
        assert got["found"] == 1

    def test_multi_token_values_stay_on_plain_containment(self):
        got = score_property_values(
            "Also called Spandex Tempest.", ["Spandex Tempest"], "aliases"
        )
        assert got["found"] == 1

    def test_a_distinctive_one_token_value_is_not_caught_by_the_rule(self):
        # The first attempt required qualification of every one-token value and
        # wrongly rejected this: an alias is not a boolean and the composer
        # never prints it as another property's value.
        got = score_property_values(
            "G0092 is also called CHIMBORAZO.", ["CHIMBORAZO"], "aliases"
        )
        assert got["found"] == 1

    def test_property_name_is_read_off_the_shape(self):
        from utils.evaluation.property_gold import property_name_of
        assert property_name_of({"spec": {"shapes": ["Technique.x_mitre_platforms"]}}) == "x_mitre_platforms"
        assert property_name_of({"spec": {"shapes": ["Group -[uses]-> Technique"]}}) is None
