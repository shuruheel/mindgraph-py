"""Static-shape smoke tests for public ontology type models."""

from typing import get_args

from mindgraph import (
    OntologicalBaseKind,
    SemanticMatch,
    SemanticParticipantSlot,
    SemanticValidationAuthoringMode,
)


def test_semantic_enums_match_the_wire_contract():
    assert set(get_args(OntologicalBaseKind)) == {
        "kind",
        "subkind",
        "dependent_particular",
        "collective",
        "relator",
        "event",
        "quality",
        "unspecified",
    }
    assert set(get_args(SemanticValidationAuthoringMode)) == {
        "off",
        "advisory",
    }


def test_match_models_preserve_required_and_defaultable_keys():
    assert SemanticMatch.__required_keys__ == {
        "version",
        "template",
        "status",
        "evidence",
        "negative_control",
        "confidence",
        "rationale",
    }
    assert "bindings" in SemanticMatch.__optional_keys__
    assert SemanticParticipantSlot.__required_keys__ == {"name", "template_slot"}
