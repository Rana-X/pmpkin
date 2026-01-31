"""Services for Reducto PDF parsing/filling and OpenAI chat."""

import os
import logging
import tempfile
from pathlib import Path

import requests
from reducto import Reducto
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")

if not OPENAI_API_KEY or not REDUCTO_API_KEY:
    raise EnvironmentError(
        f"Missing API keys. Ensure {env_path} exists with OPENAI_API_KEY and REDUCTO_API_KEY"
    )

logger = logging.getLogger(__name__)

# Lazy-initialized clients
_reducto_client = None
_openai_client = None


def _get_reducto():
    global _reducto_client
    if _reducto_client is None:
        _reducto_client = Reducto(api_key=REDUCTO_API_KEY)
    return _reducto_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# System prompt for Pumpkin
PUMPKIN_PROMPT = """You are Pumpkin 🎃, a friendly immigration document assistant.
Help users fill out immigration forms.
When you identify a form, tell them exactly what documents you need.
Be conversational, warm, use emojis sparingly.
Keep responses short and helpful."""


def parse_form(file_bytes: bytes, filename: str = "document.pdf") -> str:
    """Parse a PDF using Reducto and return extracted text."""
    client = _get_reducto()
    
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    
    try:
        logger.info("Uploading %s to Reducto (%d bytes)", filename, len(file_bytes))
        upload_result = client.upload(file=tmp_path)
        
        logger.info("Parsing with Reducto (file_id: %s)", upload_result.file_id)
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
            logger.info("Fetching result from URL: %s", result.url)
            resp = requests.get(result.url, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            for chunk in data.get("chunks", []):
                content = chunk.get("content", "")
                if content:
                    chunks.append(content)
        
        combined = "\n\n".join(chunks)
        logger.info("Parsed %s: %d chunks, %d chars", filename, len(chunks), len(combined))
        return combined
        
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def identify_form(parsed_text: str) -> str:
    """Use OpenAI to identify what type of form this is."""
    client = _get_openai()
    
    # Truncate if too long
    text = parsed_text[:10000] if len(parsed_text) > 10000 else parsed_text
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You identify immigration forms. Respond with just the form name/type, nothing else."},
            {"role": "user", "content": f"What form is this?\n\n{text}"}
        ],
        max_tokens=50,
    )
    
    return response.choices[0].message.content.strip()


def fill_form(file_bytes: bytes, filename: str, fill_instructions: str) -> str:
    """Fill a PDF form using Reducto Edit API. Returns URL to filled PDF."""
    client = _get_reducto()
    
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    
    try:
        logger.info("Uploading form for filling: %s", filename)
        upload_result = client.upload(file=tmp_path)
        
        logger.info("Filling form with Reducto Edit API")
        edit_response = client.edit.run(
            document_url=f"reducto://{upload_result.file_id}",
            edit_instructions=fill_instructions,
        )
        
        filled_url = edit_response.document_url
        logger.info("Form filled successfully: %s", filled_url)
        return filled_url
        
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def download_filled_pdf(url: str, save_path: Path) -> Path:
    """Download a filled PDF from Reducto URL and save locally."""
    logger.info("Downloading filled PDF from: %s", url)
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    
    save_path.write_bytes(response.content)
    logger.info("Saved filled PDF to: %s", save_path)
    return save_path


def chat(message: str, context: str = "") -> str:
    """Chat with OpenAI using Pumpkin personality."""
    client = _get_openai()
    
    system = PUMPKIN_PROMPT
    if context:
        system += f"\n\nContext:\n{context}"
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message}
        ],
    )
    
    return response.choices[0].message.content
