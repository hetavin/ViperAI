import requests
import base64
from config import Config


def ask_llm(question, file_contents=None):
    """
    file_contents: list of dicts with keys:
      - type: 'image' | 'text'
      - name: filename
      - data: base64 string (image) or plain text string (text/pdf/csv)
      - mime: mime type string (for images)
    """
    headers = {
        "Authorization": f"Bearer {Config.API_KEY}",
        "Content-Type": "application/json"
    }

    # Build content array
    content = []

    # Attach text file contents as context before the question
    if file_contents:
        for f in file_contents:
            if f["type"] == "text":
                content.append({
                    "type": "text",
                    "text": f"[File: {f['name']}]\n{f['data']}"
                })
            elif f["type"] == "image":
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{f['mime']};base64,{f['data']}"
                    }
                })

    content.append({"type": "text", "text": question})

    payload = {
        "model": Config.MODEL,
        "messages": [{"role": "user", "content": content}]
    }

    try:
        response = requests.post(
            f"{Config.API_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"