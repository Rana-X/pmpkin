"""OpenAI service for chat and document analysis."""

import logging
from openai import OpenAI

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

_client = None  # type: OpenAI | None

MODEL = "gpt-4o"

PUMPKIN_SYSTEM_PROMPT = """You are Pumpkin 🎃, a friendly immigration paralegal assistant.

You help with immigration documents, forms, and RFE responses.
When analyzing documents, you should:
1. Identify what type of document this is
2. Summarize the key points or requirements
3. List any additional documents that may be needed
4. Provide helpful guidance in a friendly, conversational tone

Be conversational, warm, and professional.
Use emojis sparingly.
Talk like a helpful colleague, not a robot."""


def _get_client():
    """Lazy-init OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat(messages, system_prompt=None):
    """Send messages to OpenAI and get a response.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        system_prompt: Optional system prompt
        
    Returns:
        The assistant's response text
    """
    client = _get_client()
    
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    
    try:
        logger.info("Sending chat request to OpenAI (%d messages)", len(full_messages))
        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
        )
        
        content = response.choices[0].message.content
        logger.info("Received response from OpenAI (%d chars)", len(content) if content else 0)
        return content or "I received an empty response. Please try again."
        
    except Exception as e:
        logger.error("OpenAI API error: %s", e)
        raise RuntimeError(f"Failed to get response from OpenAI: {e}") from e


def analyze_document(parsed_text, conversation_history=None):
    """Analyze a parsed document and provide guidance."""
    if not parsed_text or not parsed_text.strip():
        return "I couldn't find any text in the document. Could you try uploading it again?"
    
    # Truncate very long documents
    max_chars = 50000
    if len(parsed_text) > max_chars:
        parsed_text = parsed_text[:max_chars] + "\n\n[Document truncated due to length...]"
    
    messages = conversation_history or []
    messages.append({
        "role": "user",
        "content": f"Please analyze this document:\n\n---\n{parsed_text}\n---"
    })

    return chat(messages, system_prompt=PUMPKIN_SYSTEM_PROMPT)
