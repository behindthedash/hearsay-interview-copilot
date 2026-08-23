from __future__ import annotations

import hashlib
import re

from .models import KnowledgeChunk, ManifestDocument

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def normalize_text(text: str) -> str:
    return "\n".join(
        line.rstrip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()


def _blocks(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    blocks: list[str] = []
    current_heading: str | None = None
    paragraph: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        body = " ".join(line.strip() for line in paragraph if line.strip()).strip()
        paragraph = []
        if not body:
            return
        blocks.append(f"{current_heading}\n\n{body}" if current_heading else body)

    for line in normalized.split("\n"):
        heading = _HEADING.match(line)
        if heading:
            flush()
            current_heading = heading.group(2).strip()
            continue
        if not line.strip():
            flush()
            continue
        paragraph.append(line)

    flush()
    return blocks or [normalized]


def chunk_document(document: ManifestDocument, text: str) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for ordinal, content in enumerate(_blocks(text)):
        normalized = normalize_text(content)
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        identity = f"{document.source_uri}\0{ordinal}\0{content_hash}".encode("utf-8")
        chunk_id = hashlib.sha256(identity).hexdigest()[:32]
        chunks.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                source_uri=document.source_uri,
                ordinal=ordinal,
                content=normalized,
                content_hash=content_hash,
                title=document.title,
                experience_status=document.experience_status,
                project=document.project,
                topics=document.topics,
                skills=document.skills,
                metadata=dict(document.metadata),
            )
        )
    return chunks
