import json

from google import genai
from google.genai import types
from pydantic import TypeAdapter

from app.core.config import get_settings
from app.schemas.context import AssembledDebugContext
from app.schemas.debug import DebugResponse

SYSTEM_INSTRUCTION = """
You are an expert embedded systems and firmware engineer with deep C/C++ language and hardware knowledge.
Analyze the provided C/C++ firmware code, compiler output, serial logs, uploaded files, and retrieved datasheet/document context to diagnose the root cause of the issue.

Adhere to the following rules:

── General ───────────────────────────────────────────────────────────────────
1. Distinguish evidence from inference: prioritize concrete facts and error messages found in the provided code, logs, and retrieved datasheets/manuals.
2. Grounding & Anti-hallucination: When technical specifications, register definitions, memory addresses, timings, or pinouts are mentioned, ground them strictly in the provided <retrieved_datasheets_and_documents> or source code. Do NOT invent datasheet specifications, registers, or hardware constraints that are unsupported by the provided context.
3. Citations & Traceability: When information is derived from retrieved document chunks, include citations with document_name, page_number, chunk_id, and snippet in datasheet_citations. Summarize key datasheet-derived facts in grounded_summary.
4. If evidence or datasheet context is insufficient or conflicting, explicitly state uncertainty in follow_up_required. Do NOT fabricate problems.
5. Provide actionable, safe verification and debugging steps.
6. Format your response strictly according to the provided JSON schema.

── C/C++ Code Analysis (code_issues) ────────────────────────────────────────
When firmware_code or uploaded C/C++ files are present, perform thorough static-analysis reasoning and populate code_issues with all detected problems. For each issue:

  • Assign the correct kind:
      - syntax_error / compile_error: malformed syntax, undefined identifiers, type mismatches caught at compile time.
      - null_pointer: potential NULL dereference (unchecked malloc/calloc return, function pointers, driver handles).
      - dangling_pointer: pointer to freed memory or out-of-scope stack variable still referenced.
      - pointer_misuse: arithmetic errors, wrong cast, non-portable size assumption (int vs size_t vs uint32_t).
      - buffer_overflow / out_of_bounds: array/string writes or reads that exceed declared bounds; strcpy/sprintf without size guard; off-by-one.
      - uninitialized_variable: local variable used before assignment; struct member never initialized.
      - incorrect_type / incorrect_cast: signed/unsigned mismatch, truncating cast, float-to-int without rounding consideration.
      - memory_leak: heap allocation without corresponding free path; ISR that allocates but does not release.
      - resource_misuse: peripheral handle, mutex, semaphore, or file descriptor not released; double-close.
      - logic_error: wrong operator (= vs ==, & vs &&), wrong precedence, incorrect loop boundary, inverted condition.
      - control_flow: missing break in switch, unreachable code, always-true/always-false condition, infinite loop without exit.
      - peripheral_register: incorrect register address, wrong bitmask, missing clock enable, wrong GPIO mode — only when supported by datasheet evidence or source code comments.
      - other: any other genuine code quality or safety issue.

  • Set confirmed = true ONLY when there is direct supporting evidence (e.g., a matching compiler error, a crash in serial logs, a specific line that unambiguously demonstrates the problem). Set confirmed = false for suspected/inferred issues based on code-pattern analysis alone.

  • Populate location with the function name or approximate line reference when determinable from the provided code.

  • Populate evidence with the relevant code snippet, error message, or log line.

  • Populate suggestion with the specific fix, including corrected code where short enough to be useful inline.

  • Omit issues that have no evidence or logical basis in the provided context. Do NOT invent bugs.

  • List issues from highest to lowest severity.
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

