"""
Parser module for extracting integers and isolating thinking traces from model responses.
Handles diverse LLM outputs including plain integers, markdown blocks, thinking tags,
and natural language wraps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ParsedOutput:
    """Result of parsing an LLM turn response."""
    integer: Optional[int]
    success: bool
    cleaned_text: str
    extracted_thinking: Optional[str] = None
    error_message: Optional[str] = None


# Regex for extracting think/thought tags
THINK_TAG_REGEX = re.compile(r"<(?:think|thought)>(.*?)</(?:think|thought)>", re.DOTALL | re.IGNORECASE)

# Regex for unclosed thinking tag at start of output (happens if max_tokens cuts off)
UNCLOSED_THINK_REGEX = re.compile(r"^\s*<(?:think|thought)>(.*)$", re.DOTALL | re.IGNORECASE)

# Regex for markdown code blocks: ```lang ... ```
CODE_BLOCK_REGEX = re.compile(r"```(?:[a-zA-Z0-9_\-]+)?\s*\n?(.*?)\n?```", re.DOTALL)

# Regex for prefix headers like "Output:", "Answer:", "Result:", "Random integer:"
HEADER_PREFIX_REGEX = re.compile(
    r"^(?:output|answer|result|random\s*integer|generated\s*integer|integer)\s*[:=\-]\s*",
    re.IGNORECASE,
)

# Standalone signed integer regex
INTEGER_TOKEN_REGEX = re.compile(r"^-?\d+$")

# Regex to find integers within text
INLINE_INTEGER_REGEX = re.compile(r"(?<![.\d])(-?\d+)(?![.\d])")


def extract_inline_thinking(text: str) -> Tuple[str, Optional[str]]:
    """
    Extracts content inside <think>...</think> or <thought>...</thought> tags.
    Returns (cleaned_text, extracted_thinking).
    """
    if not text:
        return "", None

    thoughts: list[str] = []

    def _replace_tag(match: re.Match) -> str:
        thoughts.append(match.group(1).strip())
        return ""

    cleaned = THINK_TAG_REGEX.sub(_replace_tag, text)

    # Check for unclosed think tag (e.g. if generation terminated mid-thinking)
    if not thoughts:
        unclosed = UNCLOSED_THINK_REGEX.match(text)
        if unclosed:
            thoughts.append(unclosed.group(1).strip())
            cleaned = ""

    extracted = "\n\n".join(thoughts).strip() if thoughts else None
    return cleaned.strip(), extracted


def clean_markdown_formatting(text: str) -> str:
    """Strips code blocks, backticks, bold/italics, and quotes."""
    text = text.strip()

    # Unwrap code blocks
    code_match = CODE_BLOCK_REGEX.search(text)
    if code_match:
        text = code_match.group(1).strip()

    # Unwrap inline backticks: `42` -> 42
    text = re.sub(r"^`+|`+$", "", text).strip()

    # Unwrap markdown bold/italic: **42** or *42*
    text = re.sub(r"^\*+|\*+$", "", text).strip()
    text = re.sub(r"^_+|_+$", "", text).strip()

    # Unwrap surrounding quotes
    text = re.sub(r'^["\']+|["\']+$', "", text).strip()

    # Unwrap brackets/parentheses: [42] or (42)
    if (text.startswith("[") and text.endswith("]")) or (text.startswith("(") and text.endswith(")")):
        text = text[1:-1].strip()

    return text


def parse_integer_output(
    raw_text: str,
    existing_thinking: Optional[str] = None,
) -> ParsedOutput:
    """
    Parse the integer from LLM response according to the benchmark prompt:
    'Generate a random integer. Do NOT output anything else.'

    Extracts thinking if present, strips formatting, and extracts the signed integer.
    """
    if raw_text is None or not raw_text.strip():
        return ParsedOutput(
            integer=None,
            success=False,
            cleaned_text="",
            extracted_thinking=existing_thinking,
            error_message="Empty response received.",
        )

    # Step 1: Extract inline thinking if not already provided natively
    cleaned, inline_thinking = extract_inline_thinking(raw_text)
    thinking = existing_thinking or inline_thinking

    # Step 2: Clean whitespace and markdown wrappers
    cleaned = clean_markdown_formatting(cleaned)

    # Step 3: Check for strict single integer
    # e.g., "42", "-17", "0"
    if INTEGER_TOKEN_REGEX.match(cleaned):
        try:
            return ParsedOutput(
                integer=int(cleaned),
                success=True,
                cleaned_text=cleaned,
                extracted_thinking=thinking,
            )
        except ValueError as e:
            return ParsedOutput(
                integer=None,
                success=False,
                cleaned_text=cleaned,
                extracted_thinking=thinking,
                error_message=f"Integer conversion error: {e}",
            )

    # Step 4: Handle trailing punctuation like "42." or "42!"
    punct_stripped = re.sub(r"[.!,;:]+$", "", cleaned).strip()
    punct_cleaned = clean_markdown_formatting(punct_stripped)
    if INTEGER_TOKEN_REGEX.match(punct_cleaned):
        try:
            return ParsedOutput(
                integer=int(punct_cleaned),
                success=True,
                cleaned_text=punct_cleaned,
                extracted_thinking=thinking,
            )
        except ValueError as e:
            pass

    # Step 5: Check for common prefix wrappers like "Output: 42" or "Result: 42"
    no_prefix = HEADER_PREFIX_REGEX.sub("", cleaned).strip()
    no_prefix_cleaned = clean_markdown_formatting(re.sub(r"[.!,;:]+$", "", no_prefix))
    if INTEGER_TOKEN_REGEX.match(no_prefix_cleaned):
        try:
            return ParsedOutput(
                integer=int(no_prefix_cleaned),
                success=True,
                cleaned_text=no_prefix_cleaned,
                extracted_thinking=thinking,
            )
        except ValueError as e:
            pass

    # Step 6: Multi-line analysis - often model outputs commentary then the number on the last line
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        last_line = clean_markdown_formatting(lines[-1])
        last_line_no_prefix = clean_markdown_formatting(HEADER_PREFIX_REGEX.sub("", last_line))
        last_line_stripped = re.sub(r"[.!,;:]+$", "", last_line_no_prefix).strip()
        if INTEGER_TOKEN_REGEX.match(last_line_stripped):
            try:
                return ParsedOutput(
                    integer=int(last_line_stripped),
                    success=True,
                    cleaned_text=last_line_stripped,
                    extracted_thinking=thinking,
                )
            except ValueError as e:
                pass

    # Step 7: Heuristic extraction of isolated integers in conversational responses
    # Look for standalone integer tokens not part of a decimal (e.g. 3.14 should not match 3)
    matches = INLINE_INTEGER_REGEX.findall(cleaned)
    if len(matches) == 1:
        try:
            return ParsedOutput(
                integer=int(matches[0]),
                success=True,
                cleaned_text=matches[0],
                extracted_thinking=thinking,
            )
        except ValueError as e:
            pass
    elif len(matches) > 1:
        # If multiple numbers exist, check if the last line or trailing token has an integer
        # Prefer the last standalone integer token
        try:
            return ParsedOutput(
                integer=int(matches[-1]),
                success=True,
                cleaned_text=matches[-1],
                extracted_thinking=thinking,
            )
        except ValueError as e:
            pass

    return ParsedOutput(
        integer=None,
        success=False,
        cleaned_text=cleaned,
        extracted_thinking=thinking,
        error_message=f"Could not extract a valid integer from output: {raw_text!r}",
    )
