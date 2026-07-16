"""Typed request and response shapes for the operational ontology API.

The runtime client intentionally continues to return ordinary dictionaries.
These dependency-free ``TypedDict`` models let callers type those dictionaries
without changing the SDK's permissive wire behavior.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict, Union


SemanticValidationMode = Literal["off", "advisory", "review", "strict"]
SemanticValidationAuthoringMode = Literal["off", "advisory"]
SemanticRuntimeTemplate = Literal[
    "entity",
    "dependent_entity",
    "collective",
    "relationship_object",
    "event",
    "observation",
]
SemanticModifier = Literal["role", "phase", "social_construct"]
OntologicalBaseKind = Literal[
    "kind",
    "subkind",
    "dependent_particular",
    "collective",
    "relator",
    "event",
    "quality",
    "unspecified",
]
SemanticRigidity = Literal["rigid", "anti_rigid", "unspecified"]
SemanticIdentityMode = Literal["provided", "inherited", "derived", "unspecified"]
SemanticDependence = Literal["independent", "bearer", "external", "unspecified"]
SemanticTemporalMode = Literal[
    "persistent",
    "interval",
    "occurrence",
    "observation_time",
    "unspecified",
]
SemanticMatchStatus = Literal["candidate", "accepted", "rejected", "superseded"]
SemanticEvidenceSourceKind = Literal[
    "corpus_span",
    "declared_structure",
    "sql_metadata",
    "graph_usage",
    "human_review",
    "llm_classification",
]
SemanticSignalKind = Literal[
    "own_identity",
    "borrowed_identity",
    "host_attachment",
    "participant_count",
    "membership_relation",
    "occurs_at",
    "observed_at",
    "externally_assigned",
    "lifecycle_stage",
    "institutionally_defined",
    "relation_endpoints",
]
ParticipantSlotKind = Literal[
    "bearer",
    "player",
    "context",
    "subject",
    "source",
    "participant",
    "member",
    "observed_entity",
    "base_type",
]
FieldSemanticKind = Literal[
    "phase_indicator",
    "role_indicator",
    "internal_disposition",
    "event_time",
    "observed_at",
    "source_wording",
]
NormativeKind = Literal["need", "constraint", "obligation", "preference", "unspecified"]
CanonicalAttachmentAuthority = Literal["relation", "reference_field"]
CanonicalAttachmentDirection = Literal["outgoing", "incoming"]
SemanticRelationKind = Literal[
    "association",
    "mediation",
    "participation",
    "membership",
    "characterization",
    "part_whole",
    "derivation",
    "classification",
    "unspecified",
]


class SemanticParticipantSlotRequired(TypedDict):
    name: str
    template_slot: ParticipantSlotKind


class SemanticParticipantSlot(SemanticParticipantSlotRequired, total=False):
    object_types: list[str]
    min: int
    max: int
    relation_type: str


class FieldSemanticRequired(TypedDict):
    field: str
    semantic: FieldSemanticKind


class FieldSemantic(FieldSemanticRequired, total=False):
    temporal_mode: SemanticTemporalMode
    lossy: bool


class CanonicalAttachmentBindingRequired(TypedDict):
    slot: str
    relation_type: str
    authority: CanonicalAttachmentAuthority
    direction: CanonicalAttachmentDirection


class CanonicalAttachmentBinding(CanonicalAttachmentBindingRequired, total=False):
    reference_field: str


class SemanticTemplateRef(TypedDict):
    id: str
    version: int


class SemanticEvidenceRefRequired(TypedDict):
    id: str
    source_kind: SemanticEvidenceSourceKind
    source_ref: str


class SemanticEvidenceRef(SemanticEvidenceRefRequired, total=False):
    asserted_by: str
    asserted_at: str


class SemanticGeneratorRefRequired(TypedDict):
    id: str
    version: int


class SemanticGeneratorRef(SemanticGeneratorRefRequired, total=False):
    proposal_ref: str


class SemanticSignalRequired(TypedDict):
    signal: SemanticSignalKind
    value: Union[bool, int, str]
    evidence_ref: SemanticEvidenceRef
    confidence: float


class SemanticSignal(SemanticSignalRequired, total=False):
    generator: SemanticGeneratorRef
    observed_at: str


class SemanticNegativeControl(TypedDict):
    template: SemanticTemplateRef
    reason: str


class SemanticMatchAlternativeRequired(TypedDict):
    template: SemanticTemplateRef
    confidence: float
    reason: str


class SemanticMatchAlternative(SemanticMatchAlternativeRequired, total=False):
    evidence: list[SemanticSignal]


class SemanticModifierMatch(TypedDict):
    template: SemanticTemplateRef
    evidence: list[SemanticSignal]
    negative_control: SemanticNegativeControl


class SemanticReviewDecisionRequired(TypedDict):
    actor: str
    decided_at: str
    rationale: str


class SemanticReviewDecision(SemanticReviewDecisionRequired, total=False):
    premises: list[str]
    supersedes: str


class SemanticTenantBindings(TypedDict, total=False):
    ontological_base_kind: OntologicalBaseKind
    rigidity: SemanticRigidity
    identity_mode: SemanticIdentityMode
    dependence: SemanticDependence
    temporal_mode: SemanticTemporalMode
    slots: list[SemanticParticipantSlot]
    fields: list[FieldSemantic]
    normative_kind: NormativeKind
    attachments: list[CanonicalAttachmentBinding]


class SemanticMatchRequired(TypedDict):
    version: int
    template: SemanticTemplateRef
    status: SemanticMatchStatus
    evidence: list[SemanticSignal]
    negative_control: SemanticNegativeControl
    confidence: float
    rationale: str


class SemanticMatch(SemanticMatchRequired, total=False):
    modifiers: list[SemanticModifierMatch]
    alternatives: list[SemanticMatchAlternative]
    bindings: SemanticTenantBindings
    proposed_by: list[SemanticGeneratorRef]
    decision: SemanticReviewDecision


class FieldDefinitionRequired(TypedDict):
    name: str
    type: str


class FieldDefinition(FieldDefinitionRequired, total=False):
    required: bool
    description: str
    default: Any
    enum: list[str]
    reference_object_type: str
    array_item_type: str
    extraction_hint: str


class OntologySchemaRequired(TypedDict):
    id: str
    org_id: str
    name: str
    description: Optional[str]
    status: Literal["draft", "active", "deprecated", "archived"]
    version: int
    propose_status: Optional[Literal["pending", "running", "ready", "failed"]]
    propose_job_id: Optional[str]
    propose_error: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: str
    updated_at: str
    activated_at: Optional[str]
    archived_at: Optional[str]


class OntologySchema(OntologySchemaRequired, total=False):
    # Optional so the SDK tolerates servers that predate the field; the server
    # defaults absent rows to "off".
    semantic_validation_mode: SemanticValidationMode


class OntologyObjectType(TypedDict):
    id: str
    schema_id: str
    org_id: str
    name: str
    display_name: Optional[str]
    description: Optional[str]
    fields_json: list[FieldDefinition]
    required_fields: list[str]
    identity_fields: list[str]
    aliases: list[str]
    examples_json: list[dict[str, Any]]
    extraction_hints: Optional[str]
    default_confidence: float
    review_policy: Literal["always", "low_confidence", "never"]
    semantic_match: Optional[SemanticMatch]
    backing: Optional[dict[str, Any]]
    status: Literal["active", "deprecated", "archived"]
    version: int
    created_at: str
    updated_at: str


class OntologyRelationType(TypedDict):
    id: str
    schema_id: str
    org_id: str
    name: str
    display_name: Optional[str]
    description: Optional[str]
    source_type: str
    target_type: str
    cardinality: Optional[Literal["one_to_one", "one_to_many", "many_to_many"]]
    symmetric: bool
    transitive: bool
    inverse_relation_type: Optional[str]
    fields_json: list[FieldDefinition]
    extraction_hints: Optional[str]
    review_policy: Literal["always", "low_confidence", "never"]
    semantic_match: Optional[SemanticMatch]
    backing: Optional[dict[str, Any]]
    status: Literal["active", "deprecated", "archived"]
    version: int
    created_at: str
    updated_at: str


class OntologySchemaDetail(OntologySchema):
    object_types: list[OntologyObjectType]
    relation_types: list[OntologyRelationType]


class CreateOntologySchemaRequestRequired(TypedDict):
    name: str


class CreateOntologySchemaRequest(CreateOntologySchemaRequestRequired, total=False):
    description: str


class UpdateOntologySchemaRequest(TypedDict, total=False):
    name: str
    description: str
    semantic_validation_mode: SemanticValidationAuthoringMode


class OntologyObjectTypeInputRequired(TypedDict):
    name: str


class OntologyObjectTypeInput(OntologyObjectTypeInputRequired, total=False):
    display_name: str
    description: str
    fields: list[FieldDefinition]
    required_fields: list[str]
    identity_fields: list[str]
    aliases: list[str]
    examples: list[dict[str, Any]]
    extraction_hints: str
    default_confidence: float
    review_policy: Literal["always", "low_confidence", "never"]
    semantic_match: Optional[SemanticMatch]
    backing: Optional[dict[str, Any]]


class OntologyRelationTypeInputRequired(TypedDict):
    name: str
    source_type: str
    target_type: str


class OntologyRelationTypeInput(OntologyRelationTypeInputRequired, total=False):
    display_name: str
    description: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_many"]
    symmetric: bool
    transitive: bool
    inverse_relation_type: str
    fields: list[FieldDefinition]
    extraction_hints: str
    review_policy: Literal["always", "low_confidence", "never"]
    semantic_match: Optional[SemanticMatch]
    backing: Optional[dict[str, Any]]
