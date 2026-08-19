import json

from google import genai
from google.genai import types
from pydantic import TypeAdapter

from app.core.config import get_settings
from app.schemas.context import AssembledDebugContext
from app.schemas.debug import DebugResponse

SYSTEM_INSTRUCTION = """
You are an expert embedded systems and firmware engineer.
Analyze the provided C/C++ firmware code, compiler output, serial logs, uploaded files, and context
to diagnose the root cause of the issue.
Adhere to the following rules:
1. Distinguish evidence from inference.
2. If evidence is insufficient, explicitly state uncertainty.
3. Provide actionable debugging steps.
4. Format your response strictly according to the provided JSON schema.
"""


def analyze_debugging_context(
    context_or_firmware: AssembledDebugContext | str,
    compiler_output: str = "",
    serial_logs: str = "",
) -> DebugResponse:
    """Analyze the debugging context using Gemini and return a structured diagnosis.

    Accepts either a structured AssembledDebugContext or legacy positional string arguments.
    """
    settings = get_settings()

    # Initialize the genai client with the API key from settings
    client = genai.Client(api_key=settings.gemini_api_key)

    if isinstance(context_or_firmware, AssembledDebugContext):
        assembled_body = context_or_firmware.format_prompt()
        prompt = f"""
Please analyze the following embedded debugging context:

{assembled_body}
"""
    else:
        firmware_code = context_or_firmware
        prompt = f"""
Please analyze the following embedded debugging context:

<firmware_code>
{firmware_code}
</firmware_code>

<compiler_output>
{compiler_output}
</compiler_output>

<serial_logs>
{serial_logs}
</serial_logs>
"""

    # Call Gemini using the structured output format
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=DebugResponse,
            temperature=0.2,
        ),
    )

    # Parse the JSON response
    # The SDK natively returns a string of JSON when response_schema is used in this way
    if not response.text:
        raise ValueError("Empty response from Gemini API.")

    parsed_json = json.loads(response.text)
    return TypeAdapter(DebugResponse).validate_python(parsed_json)

