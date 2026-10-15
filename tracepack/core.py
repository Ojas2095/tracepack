"""Core evidence discovery, timeline extraction, and case-pack generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable

MAX_TEXT_BYTES = 512_000
HASH_CHUNK_BYTES = 1024 * 1024

TEXT_EXTENSIONS = {
    ".csv",
    ".css",
    ".html",
    ".json",
    ".log",
    ".md",
    ".py",
    ".txt",
    ".tsv",
    ".xml",
    ".yaml",
    ".yml",
    ".svg",
}

CATEGORY_BY_EXTENSION = {
    ".csv": "Data",
    ".json": "Data",
    ".tsv": "Data",
    ".yaml": "Data",
    ".yml": "Data",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".log": "Logs",
    ".md": "Notes",
    ".txt": "Notes",
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
}

TIMESTAMP_PATTERN = re.compile(
    r"\b(?P<stamp>\d{4}-\d{2}-\d{2}"
    r"(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2})?"
    r"(?:Z|[+-][0-9]{2}:?[0-9]{2})?)?)"
)


@dataclass(frozen=True)
class EvidenceFile:
    """A discovered source file and the metadata needed by every output."""

    relative_path: str
    category: str
    extension: str
    size: int
    modified_at: datetime
    sha256: str
    is_text: bool
    content: str
    content_truncated: bool
    date_tokens: tuple[str, ...]


@dataclass(frozen=True)
class TimelineEvent:
    """A human-readable event derived from evidence content or file metadata."""

    at: datetime
    source: str
    label: str
    detail: str


def _utc_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text_preview(path: Path) -> tuple[bool, str, bool]:
    """Read a bounded, forgiving preview without making binary files noisy."""

    with path.open("rb") as handle:
        sample = handle.read(8192)
        if b"\x00" in sample and path.suffix.lower() not in TEXT_EXTENSIONS:
            return False, "", False
        remainder = handle.read(MAX_TEXT_BYTES + 1 - len(sample))
        raw = sample + remainder

    truncated = len(raw) > MAX_TEXT_BYTES
    if truncated:
        raw = raw[:MAX_TEXT_BYTES]
    return True, raw.decode("utf-8", errors="replace"), truncated


def _date_tokens(value: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in TIMESTAMP_PATTERN.finditer(value):
        token = match.group("stamp")
        if token not in found:
            found.append(token)
    return tuple(found)


def parse_timestamp(token: str) -> datetime:
    """Parse TracePack's ISO-like timestamp tokens as timezone-aware UTC."""

    if len(token) == 10:
        return datetime.strptime(token, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    normalized = token.replace("Z", "+00:00")
    if re.search(r"[+-]\d{4}$", normalized):
        normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def category_for(path: Path) -> str:
    """Return a useful human label for a file extension."""

    return CATEGORY_BY_EXTENSION.get(path.suffix.lower(), "Other")


def discover_evidence(input_dir: Path) -> list[EvidenceFile]:
    """Recursively discover regular files in stable relative-path order."""

    input_dir = input_dir.expanduser()
    if not input_dir.is_dir():
        raise ValueError(f"Evidence folder does not exist or is not a directory: {input_dir}")

    evidence: list[EvidenceFile] = []
    for path in sorted((candidate for candidate in input_dir.rglob("*") if candidate.is_file()), key=lambda p: p.as_posix().lower()):
        relative_path = path.relative_to(input_dir).as_posix()
        is_text, content, truncated = _read_text_preview(path)
        evidence.append(
            EvidenceFile(
                relative_path=relative_path,
                category=category_for(path),
                extension=path.suffix.lower() or "(none)",
                size=path.stat().st_size,
                modified_at=_utc_datetime(path.stat().st_mtime),
                sha256=_hash_file(path),
                is_text=is_text,
                content=content,
                content_truncated=truncated,
                date_tokens=_date_tokens(f"{relative_path}\n{content}"),
            )
        )
    return evidence


def _event_detail(line: str) -> str:
    detail = " ".join(line.strip().split())
    return detail[:240] + ("…" if len(detail) > 240 else "")


def build_timeline(evidence: Iterable[EvidenceFile]) -> list[TimelineEvent]:
    """Extract dated lines and provide a metadata fallback for every file."""

    events: list[TimelineEvent] = []
    for item in evidence:
        item_events: list[TimelineEvent] = []
        if item.is_text:
            for line in item.content.splitlines():
                match = TIMESTAMP_PATTERN.search(line)
                if not match:
                    continue
                item_events.append(
                    TimelineEvent(
                        at=parse_timestamp(match.group("stamp")),
                        source=item.relative_path,
                        label="Evidence note",
                        detail=_event_detail(line),
                    )
                )
        if item_events:
            events.extend(item_events)
            continue

        fallback = parse_timestamp(item.date_tokens[0]) if item.date_tokens else item.modified_at
        events.append(
            TimelineEvent(
                at=fallback,
                source=item.relative_path,
                label="Evidence captured",
                detail=f"{item.category} file · {item.size:,} bytes · SHA-256 {item.sha256[:12]}…",
            )
        )
    return sorted(events, key=lambda event: (event.at, event.source, event.detail))


def _manifest_data(title: str, evidence: list[EvidenceFile]) -> dict[str, object]:
    return {
        "format": "tracepack-manifest/v1",
        "case_title": title,
        "source_file_count": len(evidence),
        "files": [
            {
                "path": item.relative_path,
                "category": item.category,
                "extension": item.extension,
                "bytes": item.size,
                "modified_utc": item.modified_at.isoformat().replace("+00:00", "Z"),
                "text": item.is_text,
                "sha256": item.sha256,
            }
            for item in evidence
        ],
    }


def write_case_pack(input_dir: Path, output_dir: Path, title: str, *, force: bool = False) -> dict[str, Path]:
    """Build every offline artifact and return the generated paths."""

    from .render import render_html, render_markdown_summary, render_timeline, styles_css, app_js

    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if input_dir == output_dir:
        raise ValueError("Output folder must be different from the evidence folder")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise ValueError(f"Output folder is not empty; pass --force to replace it: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence = discover_evidence(input_dir)
    timeline = build_timeline(evidence)
    generated_at = datetime.now(timezone.utc)
    manifest = _manifest_data(title, evidence)
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_bytes = manifest_text.encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    files = {
        "html": output_dir / "case_pack.html",
        "summary": output_dir / "summary.md",
        "timeline": output_dir / "timeline.md",
        "manifest": output_dir / "manifest.json",
        "manifest_hash": output_dir / "manifest.sha256",
        "styles": output_dir / "styles.css",
        "script": output_dir / "app.js",
    }
    files["html"].write_text(
        render_html(title, evidence, timeline, manifest_hash, generated_at), encoding="utf-8"
    )
    files["summary"].write_text(
        render_markdown_summary(title, evidence, timeline, manifest_hash, generated_at), encoding="utf-8"
    )
    files["timeline"].write_text(render_timeline(timeline), encoding="utf-8")
    files["manifest"].write_bytes(manifest_bytes)
    files["manifest_hash"].write_text(f"{manifest_hash}  manifest.json\n", encoding="utf-8")
    files["styles"].write_text(styles_css(), encoding="utf-8")
    files["script"].write_text(app_js(), encoding="utf-8")
    return files
