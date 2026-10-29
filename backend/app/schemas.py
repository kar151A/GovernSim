from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal['COMPLIANT', 'EVIDENCE_GAP', 'HUMAN_REVIEW_REQUIRED', 'CONDITIONAL_APPROVAL', 'BLOCKED']
EvidenceType = Literal['MODEL_CARD', 'RISK_ASSESSMENT', 'DPA', 'APPROVAL', 'EVALUATION_REPORT', 'DATA_LINEAGE', 'ACCESS_REVIEW', 'INCIDENT_LOG', 'MONITORING_REPORT', 'POLICY_DOCUMENT', 'HUMAN_OVERSIGHT_RECORD', 'VENDOR_ATTESTATION']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class AssetInput(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    asset_type: Literal['MODEL', 'LLM_APPLICATION', 'AI_AGENT', 'DATASET', 'PROMPT_TEMPLATE', 'VENDOR_MODEL', 'API'] = 'AI_AGENT'
    version: str = Field(default='1.0', min_length=1, max_length=100)
    owner: str = Field(min_length=2, max_length=120)
    business_purpose: str = Field(min_length=5, max_length=2000)
    intended_users: str = Field(default='Internal support team', max_length=500)
    deployment_geographies: list[Literal['IN', 'EU', 'US', 'UK', 'OTHER']] = Field(default_factory=lambda: ['IN'], min_length=1, max_length=5)
    autonomy_level: Literal['ADVISORY', 'ACTION_WITH_APPROVAL', 'AUTONOMOUS'] = 'ACTION_WITH_APPROVAL'
    risk_tier: Literal['LOW', 'LIMITED', 'HIGH', 'CRITICAL'] = 'LIMITED'
    lifecycle_stage: Literal['INTAKE', 'DEVELOPMENT', 'VALIDATION', 'STAGING', 'PRODUCTION', 'RETIRED'] = 'STAGING'
    dependencies: list[str] = Field(default_factory=list, max_length=50)
    data_sources: list[str] = Field(default_factory=lambda: ['Support knowledge base'], max_length=50)
    tools_and_permissions: list[str] = Field(default_factory=lambda: ['tickets:read'], max_length=50)
    model_provider: str = Field(default='Enterprise model gateway', max_length=120)
    monitoring_config: dict[str, Any] = Field(default_factory=lambda: {'enabled': True, 'threshold_breached': False})
    processes_personal_data: bool = True
    sensitive_data: bool = False
    ai_act_high_risk: bool = False
    dpia_required: bool = False
    interacts_with_people: bool = True
    incident_open: bool = False
    prompt_version: str = Field(default='1.0', min_length=1, max_length=100)
    policy_version: Literal['baseline-v1', 'strict-v2'] = 'baseline-v1'

    @field_validator('dependencies', 'data_sources', 'tools_and_permissions')
    @classmethod
    def bounded_items(cls, value):
        if any(not item or len(item) > 200 for item in value):
            raise ValueError('List items must contain 1 to 200 characters')
        return list(dict.fromkeys(value))

class EvidenceInput(StrictModel):
    control_id: str
    evidence_type: EvidenceType
    source_system: str = Field(min_length=2, max_length=120)
    source_uri: str = Field(min_length=3, max_length=500)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: datetime
    raw_content: str = Field(min_length=20, max_length=100_000)
    confidence: float = Field(default=1, ge=0, le=1)
    expected_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def valid_dates(self):
        for name in ('captured_at', 'valid_until'):
            value = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f'{name} must include timezone')
        if self.captured_at > datetime.now(timezone.utc):
            raise ValueError('captured_at cannot be in the future')
        if self.valid_until <= self.captured_at:
            raise ValueError('valid_until must be after captured_at')
        return self

class EvidenceReview(StrictModel):
    action: Literal['VERIFY', 'REJECT', 'CONFLICT']
    comment: str = Field(min_length=10, max_length=2000)

class ReviewInput(StrictModel):
    action: Literal['APPROVE', 'REJECT', 'CHALLENGE', 'OVERRIDE']
    comment: str = Field(min_length=20, max_length=2000)

class ChangeInput(StrictModel):
    asset_id: str
    change_type: Literal['GEOGRAPHY', 'MODEL_CHANGE', 'DATA_CHANGE', 'VENDOR_CHANGE', 'TOOL_PERMISSION_CHANGE', 'AUTONOMY_CHANGE', 'POLICY_CHANGE', 'INCIDENT', 'PROMPT_CHANGE']
    proposed_change: dict[str, Any]
    reason: str = Field(default='Governance impact assessment', min_length=5, max_length=1000)
    expected_context_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def validate_change(self):
        allowed = {
            'GEOGRAPHY': {'deployment_geographies'}, 'MODEL_CHANGE': {'version'},
            'DATA_CHANGE': {'data_sources', 'sensitive_data', 'processes_personal_data', 'dpia_required'},
            'VENDOR_CHANGE': {'model_provider', 'version'}, 'TOOL_PERMISSION_CHANGE': {'tools_and_permissions'},
            'AUTONOMY_CHANGE': {'autonomy_level'}, 'POLICY_CHANGE': {'policy_version'},
            'INCIDENT': {'incident_open', 'monitoring_config'}, 'PROMPT_CHANGE': {'prompt_version'},
        }[self.change_type]
        if not self.proposed_change or not set(self.proposed_change).issubset(allowed):
            raise ValueError(f'Allowed fields for {self.change_type}: {sorted(allowed)}')
        return self

class ControlInput(StrictModel):
    control_id: str = Field(pattern=r'^C-[A-Z0-9-]{2,30}$')
    name: str = Field(min_length=3, max_length=160)
    control_type: Literal['TECHNICAL', 'OPERATIONAL', 'ORGANIZATIONAL']
    description: str = Field(min_length=10, max_length=2000)
    owner_role: str = Field(min_length=2, max_length=100)
    linked_evidence_types: list[EvidenceType] = Field(min_length=1)
    scope_fields: list[str] = Field(min_length=1)
    source_terms: list[str] = Field(min_length=1)
    implementation_status: str = 'DEFINED'
    automated_check_available: bool = True

    @field_validator('scope_fields')
    @classmethod
    def known_fields(cls, fields):
        if not set(fields).issubset(AssetInput.model_fields):
            raise ValueError('scope_fields must name asset schema fields')
        return fields

class ObligationInput(StrictModel):
    obligation_id: str = Field(pattern=r'^O-[A-Z0-9-]{2,40}$')
    framework: Literal['NIST_AI_RMF', 'ISO_42001', 'EU_AI_ACT', 'GDPR', 'DPDP', 'INTERNAL_POLICY']
    title: str = Field(min_length=3, max_length=200)
    normalized_requirement: str = Field(min_length=10, max_length=2000)
    source_document: str = Field(min_length=3, max_length=200)
    source_clause: str = Field(min_length=2, max_length=150)
    source_url: str = Field(pattern=r'^https://', max_length=1000)
    applicability_conditions: Literal['ALL', 'EU_INTERACTIVE', 'EU_HIGH_RISK', 'EU_PERSONAL', 'EU_DPIA', 'IN_PERSONAL', 'SENSITIVE', 'INCIDENT', 'AUTONOMOUS']
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] = 'MEDIUM'
    evidence_required: list[EvidenceType] = Field(min_length=1)
    control_ids: list[str] = Field(min_length=1, max_length=10)
    coverage_note: str = Field(default='Representative decision-support requirement; applicability requires legal review.', max_length=1000)

class MappingInput(StrictModel):
    obligation_id: str
    control_id: str
    rationale: str = Field(min_length=20, max_length=2000)

class MappingApproval(StrictModel):
    mapping_id: str
    approve: bool
    comment: str = Field(min_length=20, max_length=2000)

class EvidenceEvent(StrictModel):
    asset_id: str
    event_type: Literal['MODEL_EVALUATED', 'ACCESS_REVIEW_COMPLETED', 'MONITORING_EXPORTED', 'HUMAN_HANDOFF_RECORDED']
    source_system: str = Field(min_length=2, max_length=120)
    source_uri: str = Field(min_length=3, max_length=500)
    content: str = Field(min_length=20, max_length=100_000)
