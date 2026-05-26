"""AI tools — Whisper transcription, GPT vision OCR, and GPT dictionary agent."""

import json
import os

from openai import OpenAI

from mcp_server.tools.utils.log_decorator import log_mcp_call


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )


@log_mcp_call(operation_type="tool")
def transcribe_audio(local_audio_path: str) -> str:
    """Transcribe a voice file using OpenAI Whisper.

    When MOCK_AUDIO_TRANSCRIPTION=true (default) returns a fixed word since the
    downloaded placeholder is not a real audio file.
    """
    if os.environ.get("MOCK_AUDIO_TRANSCRIPTION", "true").lower() == "true":
        return json.dumps({
            "text": "serendipity",
            "mock": True,
            "source_file": local_audio_path,
        })
    client = _get_client()
    with open(local_audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    return json.dumps({"text": transcript.text, "mock": False, "source_file": local_audio_path})


@log_mcp_call(operation_type="tool")
def analyze_image(local_image_path: str) -> str:
    """Extract English words from an image using GPT vision.

    Falls back to a placeholder word if the model does not support vision or the
    image contains no recognisable text.
    """
    import base64

    client = _get_client()
    model = os.environ.get("MODEL", "gpt-5.1")

    try:
        with open(local_image_path, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode()

        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract any English words or text from this image. "
                            "Output only the words, no explanations. "
                            "If no words are found, output: ephemeral"
                        ),
                    },
                ],
            }],
            max_tokens=100,
        )
        extracted = response.choices[0].message.content.strip() or "ephemeral"
    except Exception:
        extracted = "ephemeral"

    return json.dumps({"content": extracted, "source_file": local_image_path})


@log_mcp_call(operation_type="tool")
def dictionary_agent(chat_input: str, target_language: str = "Traditional Chinese") -> str:
    """GPT dictionary agent: spell-check input, then return structured vocabulary data.

    Returns JSON with fields: word, definition, translation, part_of_speech,
    example_sentence, example_translation.
    """
    client = _get_client()
    model = os.environ.get("MODEL", "gpt-5.1")

    system_prompt = f"""You are a vocabulary assistant. For the English word or phrase provided:

1. Check spelling — if incorrect, identify the most likely intended word (e.g. guibble → quibble) and look up that corrected word.
2. If spelling is correct, look up the word directly.

The 'translation' and 'example_translation' fields MUST be written in {target_language}.

Return ONLY valid JSON with these exact fields — no additional text:
{{
  "word": "...",
  "definition": "...",
  "translation": "...",
  "part_of_speech": "...",
  "example_sentence": "...",
  "example_translation": "..."
}}

If a field cannot be filled, use "N/A"."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chat_input},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = response.choices[0].message.content.strip()
    parsed = json.loads(content)
    return json.dumps({"output": parsed}, ensure_ascii=False)
