"""
Storage format for a chat message.

A message that carries attachments is stored as a small JSON envelope so the
file names survive into the history, the admin view and the memory pipeline.
Plain messages are stored verbatim, so every reader has to be able to handle
both shapes — hence one implementation, shared.
"""

import json


def decode_message(raw):
    """Return (text, [file names]) for a stored message."""

    if not raw or not raw.startswith("{"):
        return raw or "", []

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return raw, []

    if not isinstance(payload, dict) or "text" not in payload:
        return raw, []

    files = payload.get("files")

    if not isinstance(files, list):
        files = []

    return payload.get("text") or "", [str(f) for f in files]


def encode_message(text, file_names):
    """Return the value to store for a message with optional attachments."""

    if not file_names:
        return text

    return json.dumps({
        "text": text,
        "files": file_names
    })
