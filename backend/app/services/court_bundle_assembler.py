import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.legal_workflow_constants import (
    CourtBundleStatus,
    WorkflowStatus,
    WorkflowStepStatus,
    LegalArtifactType,
)
from app.db.models.legal_workflow import (
    CourtBundle,
    CourtBundleItem,
    LegalWorkflow,
    LegalWorkflowStep,
    LegalDraft,
)
from app.db.models.document import Document as DBDocument
from app.db.models.case import Case as DBCase
from app.services.storage import storage_service
from app.crud.legal_workflow import legal_workflow_crud
from app.schemas.legal_workflow import LegalArtifactCreate
from app.services.workflow_engine import workflow_engine

logger = logging.getLogger(__name__)


def render_html_to_pdf(html_content: str) -> bytes:
    """
    Renders TipTap-generated HTML content to a clean, professional PDF using ReportLab.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()
    
    # Custom styles tailored for legal response drafting
    style_normal = ParagraphStyle(
        'DraftNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
        textColor=colors.HexColor('#1e293b')  # Slate 800
    )
    style_h1 = ParagraphStyle(
        'DraftH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        spaceBefore=14,
        spaceAfter=10,
        keepWithNext=True,
        textColor=colors.HexColor('#0f172a')  # Slate 900
    )
    style_h2 = ParagraphStyle(
        'DraftH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13.5,
        leading=18,
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True,
        textColor=colors.HexColor('#1e293b')  # Slate 800
    )
    style_blockquote = ParagraphStyle(
        'DraftBlockquote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=14.5,
        leftIndent=24,
        rightIndent=24,
        spaceBefore=6,
        spaceAfter=10,
        textColor=colors.HexColor('#475569')  # Slate 600
    )

    # Clean TipTap formatting tags to reportlab compatibility
    html_content = html_content.replace('<strong>', '<b>').replace('</strong>', '</b>')
    html_content = html_content.replace('<em>', '<i>').replace('</em>', '</i>')
    html_content = html_content.replace('<br>', '<br/>').replace('<br >', '<br/>')

    flowables = []
    
    # Simple regex-based block tag splitter
    pattern = re.compile(r'<(?P<tag>p|h1|h2|h3|blockquote|li)[^>]*>(?P<content>.*?)</(?P=tag)>', re.DOTALL)
    blocks = pattern.findall(html_content)

    if not blocks:
        # Fallback to lines if HTML contains no standard block tags
        for line in html_content.split('\n'):
            line_str = line.strip()
            if line_str:
                flowables.append(Paragraph(line_str, style_normal))
                flowables.append(Spacer(1, 6))
    else:
        for tag, content in blocks:
            content = content.strip()
            if not content:
                continue
                
            if tag == 'h1':
                flowables.append(Paragraph(content, style_h1))
                flowables.append(Spacer(1, 8))
            elif tag in ('h2', 'h3'):
                flowables.append(Paragraph(content, style_h2))
                flowables.append(Spacer(1, 6))
            elif tag == 'blockquote':
                flowables.append(Paragraph(content, style_blockquote))
                flowables.append(Spacer(1, 6))
            elif tag == 'li':
                flowables.append(Paragraph(f"&bull; {content}", style_normal))
                flowables.append(Spacer(1, 4))
            else:  # 'p'
                flowables.append(Paragraph(content, style_normal))
                flowables.append(Spacer(1, 6))

    if not flowables:
        flowables.append(Paragraph("Empty draft content.", style_normal))

    doc.build(flowables)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_toc_pdf(items: List[Dict[str, Any]]) -> bytes:
    """
    Generates a formal, professional Table of Contents page using ReportLab.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'TOCTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        alignment=1,  # Center
        spaceAfter=15,
        textColor=colors.HexColor('#0f172a')
    )
    style_subtitle = ParagraphStyle(
        'TOCSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        alignment=1,  # Center
        spaceAfter=25,
        textColor=colors.HexColor('#475569')
    )
    style_header = ParagraphStyle(
        'TOCHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    style_item_label = ParagraphStyle(
        'TOCItemLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#1e293b')
    )
    style_item_page = ParagraphStyle(
        'TOCItemPage',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=15,
        alignment=2,  # Right
        textColor=colors.HexColor('#1e293b')
    )
    
    flowables = [
        Paragraph("COURT SUBMISSION BUNDLE", style_title),
        Paragraph("TABLE OF CONTENTS", style_subtitle),
        Spacer(1, 10)
    ]
    
    # Table header
    table_data = [
        [
            Paragraph("<b>Document Description</b>", style_header),
            Paragraph("<b>Page Range</b>", ParagraphStyle('TOCR', parent=style_header, alignment=2))
        ]
    ]
    
    for item in items:
        label = item["label"]
        page_start = item["page_start"]
        page_end = item["page_end"]
        page_range_str = f"{page_start} &ndash; {page_end}" if page_start != page_end else f"{page_start}"
        table_data.append([
            Paragraph(label, style_item_label),
            Paragraph(page_range_str, style_item_page)
        ])
        
    t = Table(table_data, colWidths=[380, 120])
    t.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.HexColor('#0f172a')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    flowables.append(t)
    
    doc.build(flowables)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


class CourtBundleAssembler:
    async def assemble_bundle(self, db: AsyncSession, workflow_id: int, organization_id: int) -> CourtBundle:
        """
        Runs the complete court bundle assembly workflow stage synchronously (called inside worker).
        1. Compiles draft HTML to PDF.
        2. Resolves and compiles case attachments.
        3. Generates a Table of Contents.
        4. Merges all pages, stamps page numbers.
        5. Validates size, chunks into smaller PDF volumes if limit is exceeded.
        6. Persists artifacts, generates bundle items, sets status to READY/FAILED.
        """
        # Load workflow with steps, drafts, bundles and bundle items
        result = await db.execute(
            select(LegalWorkflow)
            .options(
                selectinload(LegalWorkflow.steps),
                selectinload(LegalWorkflow.drafts),
                selectinload(LegalWorkflow.bundles).selectinload(CourtBundle.items),
            )
            .where(
                LegalWorkflow.id == workflow_id,
                LegalWorkflow.organization_id == organization_id,
            )
        )
        workflow = result.scalars().first()
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found or not accessible")

        # Find the active bundle record
        bundle = next((b for b in workflow.bundles if b.status in (CourtBundleStatus.PENDING.value, CourtBundleStatus.ASSEMBLING.value, CourtBundleStatus.FAILED.value)), None)
        if not bundle:
            # Query for the latest bundle
            bundle_result = await db.execute(
                select(CourtBundle)
                .options(selectinload(CourtBundle.items))
                .where(
                    CourtBundle.workflow_id == workflow_id,
                    CourtBundle.organization_id == organization_id,
                )
                .order_by(CourtBundle.created_at.desc())
                .limit(1)
            )
            bundle = bundle_result.scalars().first()
            
        if not bundle:
            raise ValueError(f"No court bundle found for workflow {workflow_id}")

        bundle.status = CourtBundleStatus.ASSEMBLING.value
        workflow.status = WorkflowStatus.ASSEMBLING_BUNDLE.value
        await db.commit()

        temp_files_to_clean: List[Path] = []
        open_docs: List[fitz.Document] = []

        try:
            # Resolve the approved draft
            draft_id = bundle.approved_draft_id
            draft = next((d for d in workflow.drafts if d.id == draft_id), None)
            if not draft:
                # Eager load draft
                draft_res = await db.execute(select(LegalDraft).where(LegalDraft.id == draft_id))
                draft = draft_res.scalars().first()
            if not draft:
                raise ValueError(f"Approved draft {draft_id} not found")

            # 1. Render draft HTML to PDF
            html_snapshot = draft.html_snapshot or f"<p>{draft.content_text or ''}</p>"
            draft_pdf_bytes = render_html_to_pdf(html_snapshot)
            draft_doc = fitz.open("pdf", draft_pdf_bytes)
            open_docs.append(draft_doc)

            # 2. Collect case attachments
            # We fetch all case documents to merge them
            doc_result = await db.execute(
                select(DBDocument)
                .where(DBDocument.case_id == workflow.case_id)
                .order_by(DBDocument.created_at.asc())
            )
            case_documents = list(doc_result.scalars().all())

            # Prioritize source document first, then remaining attachments
            sorted_docs: List[DBDocument] = []
            if workflow.source_document_id:
                source_doc = next((d for d in case_documents if d.id == workflow.source_document_id), None)
                if source_doc:
                    sorted_docs.append(source_doc)
            
            for doc in case_documents:
                if doc.id != workflow.source_document_id:
                    sorted_docs.append(doc)

            # Load attachment PDFs
            attachments_with_pages: List[Tuple[str, fitz.Document]] = []
            for doc in sorted_docs:
                try:
                    # Strip prefix or resolve relative URL path
                    prefix = "http://localhost:8000/uploads/"
                    url = doc.s3_url
                    if url.startswith(prefix):
                        relative_path = url[len(prefix):]
                    else:
                        marker = "/uploads/"
                        idx = url.find(marker)
                        if idx != -1:
                            relative_path = url[idx + len(marker):]
                        else:
                            relative_path = url
                    
                    local_path = storage_service.upload_dir / relative_path
                    if not local_path.exists():
                        logger.warning("Attachment file not found at %s, skipping", local_path)
                        continue
                    
                    att_doc = fitz.open(local_path)
                    open_docs.append(att_doc)
                    attachments_with_pages.append((doc.filename, att_doc))
                except Exception as e:
                    logger.error("Failed to load attachment document %s: %s", doc.filename, e, exc_info=True)
                    continue

            # 3. Calculate page ranges and build TOC
            # Estimate: TOC is 1 page long
            toc_page_count = 1
            current_page = toc_page_count + 1

            toc_items = []
            
            # Response Draft item
            draft_len = len(draft_doc)
            draft_end = current_page + draft_len - 1
            toc_items.append({
                "label": f"Response Draft: {draft.title}",
                "type": "draft",
                "page_start": current_page,
                "page_end": draft_end
            })
            current_page = draft_end + 1

            # Attachment items
            for filename, att_doc in attachments_with_pages:
                att_len = len(att_doc)
                if att_len == 0:
                    continue
                att_end = current_page + att_len - 1
                toc_items.append({
                    "label": f"Attachment: {filename}",
                    "type": "attachment",
                    "page_start": current_page,
                    "page_end": att_end
                })
                current_page = att_end + 1

            # Generate the Table of Contents PDF
            toc_pdf_bytes = generate_toc_pdf(toc_items)
            toc_doc = fitz.open("pdf", toc_pdf_bytes)
            open_docs.append(toc_doc)

            # 4. Merge all documents
            merged_doc = fitz.open()
            open_docs.append(merged_doc)

            # Insert TOC, Draft, and Attachments
            merged_doc.insert_pdf(toc_doc)
            merged_doc.insert_pdf(draft_doc)
            for _, att_doc in attachments_with_pages:
                merged_doc.insert_pdf(att_doc)

            total_pages = len(merged_doc)

            # Stamp page numbers on all pages (bottom right)
            for page_idx, page in enumerate(merged_doc):
                rect = page.rect
                width = rect.width
                height = rect.height
                
                # Bottom right margin stamp
                page_num_str = f"Page {page_idx + 1} of {total_pages}"
                point = fitz.Point(width - 100, height - 36)
                page.insert_text(
                    point,
                    page_num_str,
                    fontsize=8.5,
                    fontname="helv",
                    color=(0.3, 0.4, 0.5)  # Subtle cool grey
                )

            # 5. Chunking & size validation
            # Save merged document to bytes
            merged_pdf_bytes = merged_doc.tobytes()
            total_size_bytes = len(merged_pdf_bytes)

            chunks_list: List[Tuple[int, int]] = []
            max_chunk_bytes = bundle.max_chunk_bytes or (25 * 1024 * 1024)

            if total_size_bytes <= max_chunk_bytes:
                chunks_list.append((0, total_pages - 1))
            else:
                # Divide into page ranges where each range is under max_chunk_bytes
                chunk_start = 0
                for p_idx in range(total_pages):
                    test_doc = fitz.open()
                    test_doc.insert_pdf(merged_doc, from_page=chunk_start, to_page=p_idx)
                    test_bytes = test_doc.tobytes()
                    test_size = len(test_bytes)
                    test_doc.close()

                    if test_size > max_chunk_bytes:
                        if p_idx == chunk_start:
                            # Edge case: single page exceeds max_chunk_bytes, we have to keep it
                            end_page = p_idx
                        else:
                            end_page = p_idx - 1
                        
                        chunks_list.append((chunk_start, end_page))
                        chunk_start = end_page + 1

                if chunk_start < total_pages:
                    chunks_list.append((chunk_start, total_pages - 1))

            # 6. Save final artifacts
            # Save TOC artifact
            toc_url, toc_path = await storage_service.save_file_bytes(
                toc_pdf_bytes,
                destination=f"workflows/{workflow_id}/bundle",
                filename="table_of_contents.pdf"
            )
            toc_artifact = await legal_workflow_crud.create_artifact(
                db,
                workflow,
                artifact_in=LegalArtifactCreate(
                    organization_id=organization_id,
                    case_id=workflow.case_id,
                    workflow_id=workflow_id,
                    artifact_type=LegalArtifactType.TABLE_OF_CONTENTS.value,
                    filename="table_of_contents.pdf",
                    storage_url=toc_url,
                    size_bytes=len(toc_pdf_bytes),
                    metadata={}
                )
            )
            await db.flush()
            bundle.toc_artifact_id = toc_artifact.id

            # Save full merged PDF artifact
            final_url, final_path = await storage_service.save_file_bytes(
                merged_pdf_bytes,
                destination=f"workflows/{workflow_id}/bundle",
                filename="final_bundle.pdf"
            )
            final_artifact = await legal_workflow_crud.create_artifact(
                db,
                workflow,
                artifact_in=LegalArtifactCreate(
                    organization_id=organization_id,
                    case_id=workflow.case_id,
                    workflow_id=workflow_id,
                    artifact_type=LegalArtifactType.FINAL_BUNDLE.value,
                    filename="final_bundle.pdf",
                    storage_url=final_url,
                    size_bytes=total_size_bytes,
                    metadata={"page_count": total_pages}
                )
            )
            await db.flush()
            bundle.final_artifact_id = final_artifact.id

            # Delete any existing items to support idempotent execution/retries
            from app.db.models.legal_workflow import CourtBundleItem as DBCourtBundleItem
            await db.execute(
                select(DBCourtBundleItem)
                .where(DBCourtBundleItem.bundle_id == bundle.id)
            )
            # SQLAlchemy cascade delete will handle cleanup or we can delete manually
            for item in list(bundle.items):
                db.delete(item)
            await db.flush()

            # Save each court chunk as a separate artifact and bundle item
            chunks_manifest = []
            for idx, (c_start, c_end) in enumerate(chunks_list):
                chunk_doc = fitz.open()
                chunk_doc.insert_pdf(merged_doc, from_page=c_start, to_page=c_end)
                chunk_bytes = chunk_doc.tobytes()
                chunk_doc.close()

                chunk_filename = f"court_bundle_chunk_{idx + 1}.pdf"
                chunk_url, chunk_path = await storage_service.save_file_bytes(
                    chunk_bytes,
                    destination=f"workflows/{workflow_id}/bundle/chunks",
                    filename=chunk_filename
                )

                chunk_artifact = await legal_workflow_crud.create_artifact(
                    db,
                    workflow,
                    artifact_in=LegalArtifactCreate(
                        organization_id=organization_id,
                        case_id=workflow.case_id,
                        workflow_id=workflow_id,
                        artifact_type=LegalArtifactType.COURT_CHUNK.value,
                        filename=chunk_filename,
                        storage_url=chunk_url,
                        size_bytes=len(chunk_bytes),
                        metadata={"page_start": c_start + 1, "page_end": c_end + 1}
                    )
                )
                await db.flush()

                bundle_item = CourtBundleItem(
                    bundle=bundle,
                    artifact_id=chunk_artifact.id,
                    item_type=LegalArtifactType.COURT_CHUNK.value,
                    label=f"Court Bundle Volume {idx + 1}",
                    sort_order=idx + 1,
                    page_start=c_start + 1,
                    page_end=c_end + 1,
                    redaction_status="not_required",
                    metadata_json={"size_bytes": len(chunk_bytes)}
                )
                db.add(bundle_item)

                chunks_manifest.append({
                    "volume": idx + 1,
                    "filename": chunk_filename,
                    "size_bytes": len(chunk_bytes),
                    "page_start": c_start + 1,
                    "page_end": c_end + 1,
                    "url": chunk_url
                })

            # Manifest metadata summary
            bundle.manifest = {
                "total_pages": total_pages,
                "total_size_bytes": total_size_bytes,
                "draft_pages": draft_len,
                "attachments_count": len(attachments_with_pages),
                "chunks_count": len(chunks_list),
                "chunks": chunks_manifest,
                "toc_items": toc_items
            }
            bundle.status = CourtBundleStatus.READY.value
            bundle.error = None

            # Mark all bundle workflow steps as completed
            for step in workflow.steps:
                if step.step_key.startswith("bundle."):
                    step.status = WorkflowStepStatus.COMPLETED.value
                    step.completed_at = datetime.utcnow()
                    step.progress = 100

            # Finalize transition
            await workflow_engine.transition_workflow(
                db,
                workflow,
                WorkflowStatus.READY_FOR_COURT_SUBMISSION.value,
                event_type="workflow.completed",
                payload={"bundle_id": bundle.id}
            )

            await db.commit()
            await workflow_engine.publish_workflow_update(
                db, workflow_id, organization_id, "Court bundle assembled successfully!"
            )
            return bundle

        except Exception as e:
            logger.error("Court bundle assembly failed for workflow %s: %s", workflow_id, e, exc_info=True)
            await db.rollback()

            # Load fresh state to record failure
            try:
                bundle.status = CourtBundleStatus.FAILED.value
                bundle.error = {"detail": str(e), "failed_at": datetime.utcnow().isoformat()}
                
                # Mark running/pending bundle steps as FAILED
                for step in workflow.steps:
                    if step.step_key.startswith("bundle.") and step.status in (WorkflowStepStatus.RUNNING.value, WorkflowStepStatus.PENDING.value):
                        step.status = WorkflowStepStatus.FAILED.value
                        step.error = {"detail": str(e)}
                        step.completed_at = datetime.utcnow()

                workflow.status = WorkflowStatus.ASSEMBLY_FAILED.value
                workflow.error = {"detail": str(e)}

                await db.commit()
                await workflow_engine.publish_workflow_update(
                    db, workflow_id, organization_id, f"Bundle assembly failed: {str(e)}"
                )
            except Exception as internal_err:
                logger.error("Failed to persist bundle failure status: %s", internal_err, exc_info=True)

            raise e

        finally:
            # Safely close all PyMuPDF documents to release locked file handles
            for doc in open_docs:
                try:
                    if not doc.is_closed:
                        doc.close()
                except Exception:
                    pass


court_bundle_assembler = CourtBundleAssembler()
