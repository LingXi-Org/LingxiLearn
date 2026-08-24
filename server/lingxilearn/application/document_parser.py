from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import re
import zipfile
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from .workspace_errors import WorkspaceDomainError, WorkspacePayloadTooLarge
from .workspace_files import safe_leaf_name, validated_mime_type


class KnowledgeDocumentParser:
    def __init__(self, max_size: int) -> None:
        self._max_size = max_size

    def parse(self, body: dict[str, Any]) -> tuple[str, str, str]:
        name = safe_leaf_name(
            str(body.get("name") or body.get("fileName") or body.get("filename") or "文档.txt")
        )
        mime = validated_mime_type(name, body.get("mimeType") or body.get("contentType"))
        raw = self._decode_content(body)
        if len(raw) > self._max_size:
            raise WorkspacePayloadTooLarge("document_too_large")
        return name, mime, self._extract_text(name, mime, raw)[: self._max_size]

    @staticmethod
    def _decode_content(body: dict[str, Any]) -> bytes:
        supplied = body.get("content", "")
        file_url = body.get("fileUrl")
        encoding = body.get("encoding")
        if not supplied and isinstance(file_url, str) and file_url.lower().startswith("data:"):
            header, _, encoded = file_url.partition(",")
            if ";base64" in header.lower():
                supplied = encoded
                encoding = "base64"
            else:
                supplied = unquote(encoded)
        if encoding == "base64":
            try:
                return base64.b64decode(str(supplied), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise WorkspaceDomainError("invalid_base64_content") from exc
        if isinstance(supplied, str):
            return supplied.encode("utf-8")
        return json.dumps(supplied, ensure_ascii=False).encode("utf-8")

    def _extract_text(self, name: str, mime: str, raw: bytes) -> str:
        lower_mime = mime.casefold()
        suffix = Path(name).suffix.casefold()
        if lower_mime in {"application/json", "text/json"} or suffix == ".json":
            try:
                return json.dumps(json.loads(raw.decode("utf-8")), ensure_ascii=False, indent=2)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise WorkspaceDomainError("invalid_json_document") from exc
        if lower_mime in {"text/csv", "application/csv"} or suffix == ".csv":
            try:
                rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
                return "\n".join("\t".join(cell.strip() for cell in row) for row in rows)
            except UnicodeDecodeError as exc:
                raise WorkspaceDomainError("invalid_csv_document") from exc
        if lower_mime in {"text/html", "application/xhtml+xml"} or suffix in {".html", ".htm"}:
            return unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")))
        if (
            lower_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or suffix == ".docx"
        ):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    info = archive.getinfo("word/document.xml")
                    if info.file_size > self._max_size:
                        raise WorkspacePayloadTooLarge("document_too_large")
                    xml = archive.read("word/document.xml")
                root = ElementTree.fromstring(xml)
                return " ".join(part for part in root.itertext() if part.strip())
            except WorkspacePayloadTooLarge:
                raise
            except (KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                raise WorkspaceDomainError("invalid_docx_document") from exc
        if lower_mime == "application/pdf" or suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore[import-not-found]

                return "\n".join(
                    page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages
                )
            except Exception:  # noqa: BLE001 - optional parser with safe fallback
                return " ".join(
                    unescape(match.decode("utf-8", errors="ignore"))
                    for match in re.findall(rb"\(([^()]*)\)", raw)
                )
        return raw.decode("utf-8", errors="replace")
