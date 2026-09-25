from google.genai import types
from config import GEMINI_MODEL
from gemini_client import get_client

TRANSCRIBE_PROMPT = (
    "Transcribe this voice note verbatim. The speaker may mix English and "
    "Hindi. Output only the transcript text, no commentary, no timestamps."
)


def transcribe_voice(audio_bytes: bytes) -> str:
    response = get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
            TRANSCRIBE_PROMPT,
        ],
    )
    return response.text.strip()
