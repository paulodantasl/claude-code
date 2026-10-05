"""Text out of a bid-tab PDF, for cross-checking a visual read. Tries pdfplumber (if installed),
then poppler's `pdftotext -layout`, then pypdf. Scanned tabs return little or no text: read
those pages visually and say so in the package notes."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class NoExtractor(RuntimeError):
    pass


def parse_pages(spec: str | None) -> list[int] | None:
    """'1-3,5' -> [1, 2, 3, 5] (1-based)."""
    if not spec:
        return None
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        elif part:
            pages.append(int(part))
    return pages


def extract_text(pdf: Path | str, pages: list[int] | None = None) -> str:
    pdf = Path(pdf)
    if not pdf.exists():
        raise FileNotFoundError(pdf)
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(pdf) as doc:
            idx = [p - 1 for p in pages] if pages else range(len(doc.pages))
            return "\n\f".join(doc.pages[i].extract_text(layout=True) or "" for i in idx)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        chunks = []
        for p in pages or [None]:
            cmd = ["pdftotext", "-layout"]
            if p:
                cmd += ["-f", str(p), "-l", str(p)]
            cmd += [str(pdf), "-"]
            chunks.append(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)
        return "\n\f".join(chunks)
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf))
        idx = [p - 1 for p in pages] if pages else range(len(reader.pages))
        return "\n\f".join(reader.pages[i].extract_text() or "" for i in idx)
    except ImportError:
        pass
    raise NoExtractor("no PDF text extractor: install poppler-utils (pdftotext) or `pip install pdfplumber`")
