import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Table, JSON, Enum
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
# Using pgvector extension for Postgres (already installed in DB image)
from app.db.base import Base

# Many-to-many relationship for Document and Tag
document_tag_association = Table(
    "document_tag_association",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class DocumentProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    s3_url = Column(String, nullable=False) # Path to stored file in S3-like storage
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    content = Column(Text, nullable=True) # Extracted text from OCR
    classification = Column(String, nullable=True) # Type of document (e.g., Contract, Ruling)
    language = Column(String, nullable=True) # e.g., 'he', 'en'
    page_count = Column(Integer, default=0) # Number of pages in document

    # Email auto-ingestion provenance
    ingestion_method = Column(String(20), default="manual")  # "manual" | "email_inbound"
    email_from = Column(String(255), nullable=True)
    email_subject = Column(String(512), nullable=True)
    email_received_at = Column(DateTime, nullable=True)
    
    # NEW: Processing Status & Embeddings
    processing_status = Column(
        Enum(
            DocumentProcessingStatus,
            name="documentprocessingstatus",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=DocumentProcessingStatus.PENDING,
    )
    processing_stage = Column(String(50), default="uploaded")
    processing_progress = Column(Float, default=0.0)
    processed_chunks = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    
    # Deprecated JSON placeholder. We are moving to the structured DocumentChunk model
    # embeddings = Column(JSON, nullable=True) 

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="documents")
    uploaded_by = relationship("User", backref="uploaded_documents")
    organization = relationship("Organization", backref="documents")
    tags = relationship("Tag", secondary=document_tag_association, back_populates="documents")
    summary = relationship("Summary", uselist=False, back_populates="document", cascade="all, delete-orphan") 
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    document_metadata = relationship("DocumentMetadata", uselist=False, back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(filename='{self.filename}', case_id={self.case_id})>"

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    # Optional page number this chunk was sourced from (1-based index).
    # For non-paginated content this may be null or 1.
    page_number = Column(Integer, nullable=True)
    
    # Store the highly-dimensional mathematical vector array. (768 for text-embedding-004)
    embedding = Column(Vector(768), nullable=True)
    
    # NEW: Store LLM mapping outputs for the Map-Reduce pipeline
    chunk_analysis = Column(JSON, nullable=True)
    
    document = relationship("Document", back_populates="chunks")
