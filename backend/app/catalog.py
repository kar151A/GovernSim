"""30 authored representative requirements, not a legal corpus or certification."""
RULE_VERSION = 'kernel-1.0.0'
POLICIES = {'baseline-v1': {'max_evidence_age_days': 180}, 'strict-v2': {'max_evidence_age_days': 30}}

CONTROL_SPECS = [
    ('C-01', 'Risk & impact assessment', 'ORGANIZATIONAL', ['RISK_ASSESSMENT'], ['risk_tier', 'autonomy_level', 'sensitive_data', 'business_purpose', 'ai_act_high_risk'], ['risk', 'impact', 'harm']),
    ('C-02', 'Model validation & documentation', 'TECHNICAL', ['MODEL_CARD', 'EVALUATION_REPORT'], ['version', 'model_provider', 'prompt_version', 'dependencies', 'data_sources'], ['model', 'validation', 'evaluation', 'documentation']),
    ('C-03', 'Privacy & data protection', 'ORGANIZATIONAL', ['RISK_ASSESSMENT', 'DATA_LINEAGE', 'POLICY_DOCUMENT'], ['deployment_geographies', 'data_sources', 'sensitive_data', 'processes_personal_data', 'dpia_required'], ['privacy', 'data', 'purpose', 'rights', 'notice']),
    ('C-04', 'Vendor due diligence', 'OPERATIONAL', ['DPA', 'VENDOR_ATTESTATION'], ['model_provider', 'deployment_geographies', 'data_sources', 'version'], ['vendor', 'processor', 'contract']),
    ('C-05', 'Least privilege & tool access', 'TECHNICAL', ['ACCESS_REVIEW'], ['tools_and_permissions', 'autonomy_level', 'dependencies'], ['permission', 'access', 'privilege', 'security']),
    ('C-06', 'Human oversight & accountability', 'ORGANIZATIONAL', ['HUMAN_OVERSIGHT_RECORD', 'APPROVAL'], ['autonomy_level', 'risk_tier', 'owner', 'tools_and_permissions'], ['human', 'accountability', 'oversight', 'responsibility']),
    ('C-07', 'Monitoring & incident response', 'TECHNICAL', ['MONITORING_REPORT', 'INCIDENT_LOG'], ['monitoring_config', 'incident_open', 'version'], ['monitoring', 'incident', 'response']),
    ('C-08', 'AI transparency', 'OPERATIONAL', ['POLICY_DOCUMENT'], ['intended_users', 'interacts_with_people', 'deployment_geographies', 'business_purpose'], ['transparency', 'disclosure', 'information']),
    ('C-09', 'Data lineage & minimization', 'TECHNICAL', ['DATA_LINEAGE'], ['data_sources', 'sensitive_data', 'processes_personal_data', 'deployment_geographies'], ['lineage', 'minimization', 'quality', 'retention']),
    ('C-10', 'Lifecycle change governance', 'OPERATIONAL', ['APPROVAL', 'EVALUATION_REPORT'], ['version', 'prompt_version', 'model_provider', 'tools_and_permissions', 'deployment_geographies', 'autonomy_level', 'data_sources', 'dependencies'], ['change', 'lifecycle', 'review', 'improvement']),
]

CONTROLS = [dict(control_id=i, name=n, control_type=t, description=f'Maintain scoped, reviewed records for {n.lower()}.', owner_role='Compliance reviewer', implementation_status='DEFINED', automated_check_available=True, validation_logic='kernel-1.0.0: hash + reviewer + scope + type + freshness + coverage', linked_evidence_types=et, scope_fields=list(dict.fromkeys(fields + ['policy_version'])), source_terms=terms) for i,n,t,et,fields,terms in CONTROL_SPECS]

# framework, clause, title, control, applicability, evidence, authored requirement
ROWS = {
'NIST_AI_RMF': [
 ('GOVERN 1', 'Governance policy and review', 'C-10', 'ALL', 'APPROVAL', 'Keep a reviewed internal AI governance policy and change approval record.'),
 ('GOVERN 2', 'Named accountability', 'C-06', 'ALL', 'HUMAN_OVERSIGHT_RECORD', 'Document a responsible owner and an operational human escalation route.'),
 ('MAP 1', 'Intended use and risk context', 'C-01', 'ALL', 'RISK_ASSESSMENT', 'Assess intended use, stakeholders and plausible harms before operational release.'),
 ('MEASURE 2', 'Model evaluation', 'C-02', 'ALL', 'EVALUATION_REPORT', 'Retain evaluations of performance and limitations for the deployed model version.'),
 ('MANAGE 4', 'Monitoring and response', 'C-07', 'ALL', 'MONITORING_REPORT', 'Monitor operational risks and maintain a route for corrective action.'),
],
'ISO_42001': [
 ('Principle: accountability', 'AI management responsibilities', 'C-06', 'ALL', 'HUMAN_OVERSIGHT_RECORD', 'Assign and review responsibilities within an AI management process.'),
 ('Principle: risk management', 'AI impact review', 'C-01', 'ALL', 'RISK_ASSESSMENT', 'Maintain an impact review aligned with organizational AI objectives.'),
 ('Principle: lifecycle management', 'Lifecycle documentation', 'C-02', 'ALL', 'MODEL_CARD', 'Maintain system documentation and limitations through its lifecycle.'),
 ('Principle: external relationships', 'Supplier governance', 'C-04', 'ALL', 'VENDOR_ATTESTATION', 'Document supplier suitability and responsibilities for external AI components.'),
 ('Principle: continual improvement', 'Management review', 'C-10', 'ALL', 'APPROVAL', 'Record management review and improvement decisions after material changes.'),
],
'EU_AI_ACT': [
 ('Article 50(1)', 'AI interaction disclosure', 'C-08', 'EU_INTERACTIVE', 'POLICY_DOCUMENT', 'Record how relevant users are informed that they interact with an AI system.'),
 ('Article 9', 'High-risk risk management', 'C-01', 'EU_HIGH_RISK', 'RISK_ASSESSMENT', 'For a confirmed high-risk use, retain a risk-management review.'),
 ('Article 11', 'High-risk technical documentation', 'C-02', 'EU_HIGH_RISK', 'MODEL_CARD', 'For a confirmed high-risk use, retain technical system documentation.'),
 ('Article 14', 'High-risk human oversight', 'C-06', 'EU_HIGH_RISK', 'HUMAN_OVERSIGHT_RECORD', 'For a confirmed high-risk use, document effective human oversight arrangements.'),
 ('Article 15', 'High-risk robustness and evaluation', 'C-02', 'EU_HIGH_RISK', 'EVALUATION_REPORT', 'For a confirmed high-risk use, assess accuracy, robustness and cybersecurity.'),
],
'GDPR': [
 ('Articles 5 and 6', 'Processing purpose and lawful basis', 'C-03', 'EU_PERSONAL', 'POLICY_DOCUMENT', 'Document the processing purpose, lawful-basis assessment and applicable safeguards.'),
 ('Articles 13–15', 'Privacy notice and rights workflow', 'C-03', 'EU_PERSONAL', 'POLICY_DOCUMENT', 'Retain notice information and procedures for relevant data-subject rights.'),
 ('Article 28', 'Processor contract review', 'C-04', 'EU_PERSONAL', 'DPA', 'Review processor arrangements when an external processor handles personal data.'),
 ('Article 35', 'DPIA where required', 'C-03', 'EU_DPIA', 'RISK_ASSESSMENT', 'Record a data protection impact assessment where processing is likely to create high risk.'),
 ('Article 5(1)(c) and (e)', 'Data minimization and retention', 'C-09', 'EU_PERSONAL', 'DATA_LINEAGE', 'Document necessary data categories and retention limits for this processing purpose.'),
],
'DPDP': [
 ('Sections 5–7', 'India notice and processing basis', 'C-03', 'IN_PERSONAL', 'POLICY_DOCUMENT', 'Prepare notice and applicable processing-basis records for digital personal data.'),
 ('Section 8(5)', 'Personal data safeguards', 'C-05', 'IN_PERSONAL', 'ACCESS_REVIEW', 'Maintain reviewed access and security safeguards for personal data.'),
 ('Section 8(6)', 'Personal data breach preparedness', 'C-07', 'IN_PERSONAL', 'MONITORING_REPORT', 'Document monitoring and procedures to address personal-data breaches.'),
 ('Section 8(7)', 'Personal data retention readiness', 'C-09', 'IN_PERSONAL', 'DATA_LINEAGE', 'Maintain records supporting retention and erasure requirements when applicable.'),
 ('Sections 11–13', 'Data principal rights readiness', 'C-03', 'IN_PERSONAL', 'POLICY_DOCUMENT', 'Prepare processes for data-principal access, correction, erasure and grievance handling.'),
],
'INTERNAL_POLICY': [
 ('GS-POL-01', 'Model documentation gate', 'C-02', 'ALL', 'MODEL_CARD', 'Require a reviewed model card for the current model and prompt versions.'),
 ('GS-POL-02', 'Tool permission review', 'C-05', 'ALL', 'ACCESS_REVIEW', 'Review tool permissions and least privilege after permission changes.'),
 ('GS-POL-03', 'Autonomous high-risk release', 'C-06', 'AUTONOMOUS', 'HUMAN_OVERSIGHT_RECORD', 'Require a named reviewer decision for autonomous high-risk release.'),
 ('GS-POL-04', 'Incident remediation review', 'C-07', 'INCIDENT', 'INCIDENT_LOG', 'Retain incident remediation evidence and require risk review before continued release.'),
 ('GS-POL-05', 'Sensitive data lineage', 'C-09', 'SENSITIVE', 'DATA_LINEAGE', 'Review lineage and use restrictions when sensitive data is introduced.'),
]}
SOURCES = {
 'NIST_AI_RMF': ('NIST AI RMF 1.0', 'https://airc.nist.gov/airmf-resources/airmf/5-sec-core/'),
 'ISO_42001': ('ISO/IEC 42001:2023 public overview', 'https://www.iso.org/standard/42001'),
 'EU_AI_ACT': ('Regulation (EU) 2024/1689', 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng'),
 'GDPR': ('Regulation (EU) 2016/679', 'https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng'),
 'DPDP': ('Digital Personal Data Protection Act 2023 and Rules 2025', 'https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa'),
 'INTERNAL_POLICY': ('GovernSim illustrative internal policy v1', '/static/policies/internal-policy.md'),
}
OBLIGATIONS = []
for framework, rows in ROWS.items():
    for index, (clause, title, control, condition, evidence, requirement) in enumerate(rows, 1):
        note = 'Representative decision-support requirement; scope and current legal applicability require qualified review.'
        if framework == 'ISO_42001':
            note = 'Principle aligned to the public ISO overview. No licensed clause mapping or certification claim.'
        if framework == 'DPDP':
            note = 'Readiness control. Phased commencement must be checked against Gazette notifications; not an assertion all provisions are in force.'
        if framework == 'NIST_AI_RMF':
            note = 'Voluntary framework outcome; not a statutory duty or exhaustive checklist.'
        OBLIGATIONS.append(dict(obligation_id=f'O-{framework}-{index:02}', framework=framework, title=title, normalized_requirement=requirement, source_document=SOURCES[framework][0], source_clause=clause, source_url=SOURCES[framework][1], applicability_conditions=condition, severity='HIGH' if condition in ('EU_HIGH_RISK', 'EU_DPIA', 'AUTONOMOUS', 'INCIDENT') else 'MEDIUM', evidence_required=[evidence], control_ids=[control], coverage_note=note, approved=True, version=1))

for control in CONTROLS:
    control['linked_obligation_ids'] = [o['obligation_id'] for o in OBLIGATIONS if control['control_id'] in o['control_ids']]
