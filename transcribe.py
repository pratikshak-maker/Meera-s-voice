from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

client = genai.Client(api_key=GEMINI_API_KEY)

TRANSCRIBE_PROMPT = (
    "Transcribe this voice note verbatim. The speaker may mix English and "
    "Hindi. Output only the transcript text, no commentary, no timestamps."
)


def transcribe_voice(audio_bytes: bytes) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
            TRANSCRIBE_PROMPT,
        ],
    )
    return response.text.strip()
