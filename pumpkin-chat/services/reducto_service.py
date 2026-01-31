"""Reducto API service for parsing PDFs into structured text."""

import logging
import tempfile
from pathlib import Path

import requests
from reducto import Reducto

from config import REDUCTO_API_KEY

logger = logging.getLogger(__name__)

_client = None  # type: Reducto | None


def _get_client():
    """Lazy-init Reducto client."""
    global _client
    if _client is None:
        _client = Reducto(api_key=REDUCTO_API_KEY)
    return _client


def parse_pdf(file_bytes, filename="document.pdf"):
    """Parse a PDF using Reducto and return combined text content."""
    client = _get_client()

    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        logger.info("Uploading %s to Reducto (%d bytes)", filename, len(file_bytes))
        upload_result = client.upload(file=tmp_path)

        logger.info("Parsing %s with Reducto (file_id: %s)", filename, upload_result.file_id)
        parse_response = client.parse.run(
            input=f"reducto://{upload_result.file_id}",
        )

        result = parse_response.result
        chunks = []

        if hasattr(result, "chunks"):
            for chunk in result.chunks:
                if chunk.content:
                    chunks.append(chunk.content)
        elif hasattr(result, "url"):
            logger.info("Result returned as URL, fetching: %s", result.url)
            resp = requests.get(result.url, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            for chunk in data.get("chunks", []):
                content = chunk.get("content", "")
                if content:
                    chunks.append(content)

        combined = "\n\n".join(chunks)

        if not combined.strip():
            logger.warning("Reducto returned empty content for %s", filename)
            return "[Document could not be parsed — no text content extracted]"

        logger.info("Parsed %s: %d chunks, %d chars", filename, len(chunks), len(combined))
        return combined

    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
