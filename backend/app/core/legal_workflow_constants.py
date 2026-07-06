import enum


class WorkflowType(str, enum.Enum):
    COURT_RESPONSE_BUNDLE = "court_response_bundle"


class WorkflowStatus(str, enum.Enum):
    CREATED = "CREATED"
    INTAKE_RECEIVED = "INTAKE_RECEIVED"
    INGESTING = "INGESTING"
    INGESTION_FAILED = "INGESTION_FAILED"
    AI_ANALYZING = "AI_ANALYZING"
    AI_DRAFTING = "AI_DRAFTING"
    AI_DRAFT_FAILED = "AI_DRAFT_FAILED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    IN_HUMAN_REVIEW = "IN_HUMAN_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    APPROVED_FOR_ASSEMBLY = "APPROVED_FOR_ASSEMBLY"
    ASSEMBLING_BUNDLE = "ASSEMBLING_BUNDLE"
    ASSEMBLY_FAILED = "ASSEMBLY_FAILED"
    READY_FOR_COURT_SUBMISSION = "READY_FOR_COURT_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"


class WorkflowStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class WorkflowStepKey(str, enum.Enum):
    INTAKE_CAPTURE = "intake.capture"
    INTAKE_PERSIST_SOURCE_DOCUMENT = "intake.persist_source_document"
    DOCUMENT_OCR = "document.ocr"
    DOCUMENT_AI_ANALYSIS = "document.ai_analysis"
    DRAFT_GENERATE = "draft.generate"
    DRAFT_NORMALIZE_TO_EDITOR_DOC = "draft.normalize_to_editor_doc"
    REVIEW_HUMAN_EDIT = "review.human_edit"
    REVIEW_APPROVE = "review.approve"
    BUNDLE_COLLECT_ATTACHMENTS = "bundle.collect_attachments"
    BUNDLE_REDACT = "bundle.redact"
    BUNDLE_PAGINATE = "bundle.paginate"
    BUNDLE_TABLE_OF_CONTENTS = "bundle.table_of_contents"
    BUNDLE_VALIDATE_SIZE = "bundle.validate_size"
    BUNDLE_CHUNK_FOR_COURT = "bundle.chunk_for_court"
    BUNDLE_FINALIZE = "bundle.finalize"


class WorkflowStepType(str, enum.Enum):
    AUTOMATED = "automated"
    HUMAN = "human"


class LegalArtifactType(str, enum.Enum):
    SOURCE_DOCUMENT = "source_document"
    OCR_TEXT = "ocr_text"
    AI_ANALYSIS = "ai_analysis"
    DRAFT_HTML = "draft_html"
    DRAFT_PDF = "draft_pdf"
    ATTACHMENT = "attachment"
    REDACTION_MANIFEST = "redaction_manifest"
    TABLE_OF_CONTENTS = "table_of_contents"
    FINAL_BUNDLE = "final_bundle"
    COURT_CHUNK = "court_chunk"
    BUNDLE_MANIFEST = "bundle_manifest"


class LegalDraftStatus(str, enum.Enum):
    AI_GENERATED = "AI_GENERATED"
    IN_REVIEW = "IN_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"


class CourtBundleStatus(str, enum.Enum):
    PENDING = "PENDING"
    ASSEMBLING = "ASSEMBLING"
    FAILED = "FAILED"
    READY = "READY"


class WorkflowActorType(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    WORKER = "worker"
    AI = "ai"


DEFAULT_COURT_BUNDLE_MAX_CHUNK_BYTES = 25 * 1024 * 1024
DEFAULT_DRAFT_EDITOR_FORMAT = "tiptap_json"

DEFAULT_COURT_RESPONSE_WORKFLOW_STEPS = [
    (WorkflowStepKey.INTAKE_CAPTURE.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.INTAKE_PERSIST_SOURCE_DOCUMENT.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.DOCUMENT_OCR.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.DOCUMENT_AI_ANALYSIS.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.DRAFT_GENERATE.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.DRAFT_NORMALIZE_TO_EDITOR_DOC.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.REVIEW_HUMAN_EDIT.value, WorkflowStepType.HUMAN.value),
    (WorkflowStepKey.REVIEW_APPROVE.value, WorkflowStepType.HUMAN.value),
    (WorkflowStepKey.BUNDLE_COLLECT_ATTACHMENTS.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.BUNDLE_REDACT.value, WorkflowStepType.HUMAN.value),
    (WorkflowStepKey.BUNDLE_PAGINATE.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.BUNDLE_TABLE_OF_CONTENTS.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.BUNDLE_VALIDATE_SIZE.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.BUNDLE_CHUNK_FOR_COURT.value, WorkflowStepType.AUTOMATED.value),
    (WorkflowStepKey.BUNDLE_FINALIZE.value, WorkflowStepType.AUTOMATED.value),
]
