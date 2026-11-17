"""Safe text extraction for common resume formats."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re


def _pdf_link_lines(reader, text: str) -> str:
    """URLs behind clickable text such as 'LinkedIn' or 'GitHub' that the page text does not show."""
    urls = []
    try:
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                uri = (annot.get_object().get("/A") or {}).get("/URI")
                if uri and str(uri) not in text and str(uri) not in urls and not str(uri).startswith("mailto:"):
                    urls.append(str(uri))
    except Exception:
        return ""
    return ("\n" + "\n".join(urls)) if urls else ""


def extract_resume_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(payload))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError("This PDF is password-protected. Upload an unlocked PDF.") from exc
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            if not text.strip():
                raise ValueError("No selectable text was found. This may be a scanned PDF; run OCR and upload it again.")
            return text + _pdf_link_lines(reader, text)
        except ImportError as exc:
            raise ValueError("PDF support is missing. Install the project requirements again.") from exc
    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(BytesIO(payload))
            lines = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:   # many CV templates put sections or contact details in tables
                for row in table.rows:
                    seen = []
                    for cell in row.cells:
                        if cell.text.strip() and cell.text.strip() not in seen:
                            seen.append(cell.text.strip())
                    if seen:
                        lines.append(" | ".join(seen) if len(seen) > 1 else seen[0])
            links = [rel.target_ref for rel in doc.part.rels.values() if rel.reltype.endswith("/hyperlink")]
            lines += [u for u in links if u not in "\n".join(lines)]   # "LinkedIn" / "GitHub" link text hides the URL
            return "\n".join(lines)
        except ImportError as exc:
            raise ValueError("DOCX support is missing. Install the project requirements again.") from exc
        except Exception as exc:
            raise ValueError("Could not read this DOCX file. Please re-save it and try again.") from exc
    if suffix == ".txt":
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}. Use PDF, DOCX or TXT.")


def split_pasted_resumes(text: str) -> list[str]:
    """Split on explicit separators; otherwise treat all pasted text as one resume."""
    text = text.strip()
    if not text:
        return []
    chunks = re.split(r"(?im)^\s*(?:---+|={3,}|RESUME\s*\d+)\s*$", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]
