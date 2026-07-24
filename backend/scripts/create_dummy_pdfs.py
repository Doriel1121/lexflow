"""Generate lightweight dummy legal PDFs for full-pipeline load tests.

The PDFs are intentionally digital text PDFs, not scanned images. They exercise
upload, file storage, PDF text extraction, AI analysis, metadata, embeddings,
and semantic search without the cost of image OCR.
"""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "test_samples" / "dummy_pdfs"


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(lines: list[str]) -> bytes:
    y = 760
    text_ops = ["BT", "/F1 11 Tf", "72 760 Td", "14 TL"]
    for line in lines:
        text_ops.append(f"({_escape_pdf_text(line)}) Tj")
        text_ops.append("T*")
        y -= 14
        if y < 80:
            break
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n% LexFlow dummy legal fixture\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def make_lines(index: int) -> list[str]:
    amount = 100_000 + (index * 7_500)
    day = 10 + (index % 18)
    return [
        f"Dummy Legal Document {index:03d}",
        "Document Type: Principles Agreement",
        f"Case Number: LF-DUMMY-2026-{index:04d}",
        f"Client: LexFlow Test Client {index}",
        f"Counterparty: Example Holdings {index} Ltd.",
        "Matter: Commercial cooperation and settlement principles",
        f"Agreement Date: 2026-07-{day:02d}",
        f"Response Deadline: 2026-08-{day:02d}",
        f"Amount: {amount:,} ILS",
        "Summary: This document records a principles agreement between the parties.",
        "Obligations: payment schedule, document delivery, confidentiality, and approvals.",
        "Risk: missing board approval and incomplete disclosure schedules.",
        "Search terms: principles agreement, payment obligation, response deadline.",
        "This file is generated for LexFlow processing drain and semantic search testing.",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for index in range(1, args.count + 1):
        path = output_dir / f"dummy-principles-agreement-{index:03d}.pdf"
        path.write_bytes(_build_pdf(make_lines(index)))

    print({"output_dir": str(output_dir), "created": args.count})


if __name__ == "__main__":
    main()
