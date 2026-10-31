"""
Parser module for extracting integers and isolating thinking traces from model responses.
Handles diverse LLM outputs including plain integers, markdown blocks, LaTeX delimiters,
thinking tags, formatted numbers (commas, Unicode minus), and natural language wraps.
"""

from __future__ import annotations

import json
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


# Regex for extracting think/thought/reasoning tags
THINK_TAG_REGEX = re.compile(
    r"<(?:think|thought|reasoning|antThinking|reflection)>(.*?)</(?:think|thought|reasoning|antThinking|reflection)>",
    re.DOTALL | re.IGNORECASE,
)

# Regex for unclosed thinking tag at start of output (happens if max_tokens cuts off generation)
UNCLOSED_THINK_REGEX = re.compile(
    r"^\s*<(?:think|thought|reasoning|antThinking|reflection)>(.*)$",
    re.DOTALL | re.IGNORECASE,
)

# Regex for markdown code blocks: ```lang ... ```
CODE_BLOCK_REGEX = re.compile(r"```(?:[a-zA-Z0-9_\-]+)?\s*\n?(.*?)\n?```", re.DOTALL)

# Regex for prefix headers like "Output:", "Answer:", "Result:", "Random integer:"
HEADER_PREFIX_REGEX = re.compile(
    r"^(?:output|answer|result|random\s*integer|generated\s*integer|the\s*integer|integer|value)\s*[:=\-]\s*",
    re.IGNORECASE,
)

# Regex for explicit conversational integer statements
KEYWORD_INTEGER_REGEX = re.compile(
    r"(?:random\s+integer|generated\s+integer|the\s+integer|integer|number|result|answer|output|value)\s*(?:is|was|chosen|selected|generated|:|=|->)?\s*([+-]?\d+)",
    re.IGNORECASE,
)

# Regex for Unicode minus/hyphens/dashes
UNICODE_DASHES_REGEX = re.compile(r"[\u2212\u2013\u2014\u2010\ufe63\uff0d]")

# Regex for space after sign: "- 42" -> "-42"
SIGN_SPACE_REGEX = re.compile(r"(?<!\w)([-+])\s+(\d)")

# Regex for comma thousands separators: "1,000" or "1,234,567"
COMMA_THOUSANDS_REGEX = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")

# Standalone signed integer regex
INTEGER_TOKEN_REGEX = re.compile(r"^[+-]?\d+$")

# Regex to find integers within text that are not part of decimals (e.g. 3.14 avoids 3 and 14)
INLINE_INTEGER_REGEX = re.compile(r"(?<![.\d])([+-]?\d+)(?![.\d])")

# Fullwidth digits mapping table
FULLWIDTH_TRANS = str.maketrans("０１２３４５６７８９", "0123456789")


def extract_inline_thinking(text: str) -> Tuple[str, Optional[str]]:
    """
    Extracts content inside <think>...</think>, <thought>...</thought>, etc.
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


def clean_markdown_and_formatting(text: str) -> str:
    """Strips code blocks, backticks, bold/italics, quotes, LaTeX delimiters, and HTML tags."""
    if not text:
        return ""

    # Normalize Unicode minus, dashes, and fullwidth digits
    text = UNICODE_DASHES_REGEX.sub("-", text)
    text = text.translate(FULLWIDTH_TRANS)
    text = SIGN_SPACE_REGEX.sub(r"\1\2", text)

    text = text.strip()

    # Unwrap code blocks
    code_match = CODE_BLOCK_REGEX.search(text)
    if code_match:
        text = code_match.group(1).strip()

    # Unwrap LaTeX boxed: \boxed{42} -> 42
    text = re.sub(r"\\boxed\{([^{}]+)\}", r"\1", text).strip()
    text = re.sub(r"\\textbf\{([^{}]+)\}", r"\1", text).strip()

    # Strip LaTeX math delimiters: $$42$$ or $42$ or \[42\] or \(42\)
    text = re.sub(r"^\$\$+|\$\$+$", "", text).strip()
    text = re.sub(r"^\$+|\$+$", "", text).strip()
    text = re.sub(r"^\\\[|\\\]$", "", text).strip()
    text = re.sub(r"^\\\(|\\\)$", "", text).strip()

    # Unwrap inline backticks: `42` -> 42
    text = re.sub(r"^`+|`+$", "", text).strip()

    # Unwrap markdown bold/italic: **42** or *42*
    text = re.sub(r"^\*+|\*+$", "", text).strip()
    text = re.sub(r"^_+|_+$", "", text).strip()

    # Unwrap surrounding quotes
    text = re.sub(r'^["\']+|["\']+$', "", text).strip()

    # Unwrap brackets/parentheses: [42] or (42) or {42}
    if (text.startswith("[") and text.endswith("]")) or (
        text.startswith("(") and text.endswith(")")
    ) or (text.startswith("{") and text.endswith("}")):
        inner = text[1:-1].strip()
        # Only unwrap if it doesn't look like JSON object
        if ":" not in inner:
            text = inner

    # Unwrap simple HTML tags: <output>42</output>, <answer>42</answer>, <span>42</span>
    text = re.sub(r"^<(?:output|answer|result|span|p|div)[^>]*>(.*?)</(?:output|answer|result|span|p|div)>$", r"\1", text, flags=re.DOTALL | re.IGNORECASE).strip()

    # Normalize comma thousands separators in digit sequences: 1,000 -> 1000
    text = COMMA_THOUSANDS_REGEX.sub("", text)

    return text


clean_markdown_formatting = clean_markdown_and_formatting


def _try_parse_json_integer(text: str) -> Optional[int]:
    """Attempt to parse text as JSON and extract integer from key/value."""
    trimmed = text.strip()
    if not (trimmed.startswith("{") or trimmed.startswith("[")):
        return None
    try:
        data = json.loads(trimmed)
        if isinstance(data, int) and not isinstance(data, bool):
            return data
        if isinstance(data, dict):
            # Check standard keys
            for k in ("integer", "answer", "result", "output", "value", "random_integer", "number"):
                if k in data and isinstance(data[k], int) and not isinstance(data[k], bool):
                    return data[k]
                elif k in data and isinstance(data[k], str) and INTEGER_TOKEN_REGEX.match(data[k].strip()):
                    return int(data[k].strip())
            # If dict has exactly one entry with integer value
            if len(data) == 1:
                val = next(iter(data.values()))
                if isinstance(val, int) and not isinstance(val, bool):
                    return val
        elif isinstance(data, list) and len(data) == 1:
            if isinstance(data[0], int) and not isinstance(data[0], bool):
                return data[0]
    except Exception:
        pass
    return None


def parse_integer_output(
    raw_text: str,
    existing_thinking: Optional[str] = None,
) -> ParsedOutput:
    """
    Parse the integer from LLM response according to the benchmark prompt:
    'Generate a random integer. Do NOT output anything else.'

    Extracts thinking traces if present, strips formatting/LaTeX/JSON wrappers,
    handles comma-formatted integers, and extracts the signed integer.
    """
    if raw_text is None or not str(raw_text).strip():
        return ParsedOutput(
            integer=None,
            success=False,
            cleaned_text="",
            extracted_thinking=existing_thinking,
            error_message="Empty response received.",
        )

    # Step 1: Extract inline thinking if not already provided natively
    cleaned, inline_thinking = extract_inline_thinking(str(raw_text))
    thinking = existing_thinking or inline_thinking

    # Step 2: Try JSON parsing if formatted as JSON payload
    json_val = _try_parse_json_integer(cleaned)
    if json_val is not None:
        return ParsedOutput(
            integer=json_val,
            success=True,
            cleaned_text=str(json_val),
            extracted_thinking=thinking,
        )

    # Step 3: Clean whitespace, dashes, LaTeX, and markdown wrappers
    cleaned = clean_markdown_and_formatting(cleaned)

    # Step 4: Check for strict single integer (e.g. "42", "-17", "+100", "0")
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

    # Step 5: Handle trailing punctuation like "42." or "42!"
    punct_stripped = re.sub(r"[.!,;:]+$", "", cleaned).strip()
    punct_cleaned = clean_markdown_and_formatting(punct_stripped)
    if INTEGER_TOKEN_REGEX.match(punct_cleaned):
        try:
            return ParsedOutput(
                integer=int(punct_cleaned),
                success=True,
                cleaned_text=punct_cleaned,
                extracted_thinking=thinking,
            )
        except ValueError:
            pass

    # Step 6: Check for common prefix wrappers like "Output: 42" or "Result: 42"
    no_prefix = HEADER_PREFIX_REGEX.sub("", cleaned).strip()
    no_prefix_cleaned = clean_markdown_and_formatting(re.sub(r"[.!,;:]+$", "", no_prefix))
    if INTEGER_TOKEN_REGEX.match(no_prefix_cleaned):
        try:
            return ParsedOutput(
                integer=int(no_prefix_cleaned),
                success=True,
                cleaned_text=no_prefix_cleaned,
                extracted_thinking=thinking,
            )
        except ValueError:
            pass

    # Step 7: Check for explicit keyword association in conversational text
    # e.g., "The random integer is 42 (turn 1)." -> associates 42 with integer, not 1
    kw_match = KEYWORD_INTEGER_REGEX.search(cleaned)
    if kw_match:
        try:
            val = int(kw_match.group(1))
            return ParsedOutput(
                integer=val,
                success=True,
                cleaned_text=str(val),
                extracted_thinking=thinking,
            )
        except ValueError:
            pass

    # Step 8: Multi-line analysis - often model outputs commentary then the number on the last line
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        for candidate_line in reversed(lines):
            cand_cleaned = clean_markdown_and_formatting(candidate_line)
            cand_no_prefix = clean_markdown_and_formatting(
                HEADER_PREFIX_REGEX.sub("", cand_cleaned).strip()
            )
            cand_stripped = re.sub(r"[.!,;:]+$", "", cand_no_prefix).strip()
            if INTEGER_TOKEN_REGEX.match(cand_stripped):
                try:
                    return ParsedOutput(
                        integer=int(cand_stripped),
                        success=True,
                        cleaned_text=cand_stripped,
                        extracted_thinking=thinking,
                    )
                except ValueError:
                    pass

    # Step 9: Heuristic extraction of isolated integers in conversational responses
    # Look for standalone integer tokens not part of a decimal (e.g. 3.14 rejects 3 and 14)
    matches = INLINE_INTEGER_REGEX.findall(cleaned)
    if len(matches) == 1:
        try:
            return ParsedOutput(
                integer=int(matches[0]),
                success=True,
                cleaned_text=matches[0],
                extracted_thinking=thinking,
            )
        except ValueError:
            pass
    elif len(matches) > 1:
        # Prefer the last standalone integer token
        try:
            return ParsedOutput(
                integer=int(matches[-1]),
                success=True,
                cleaned_text=matches[-1],
                extracted_thinking=thinking,
            )
        except ValueError:
            pass

    return ParsedOutput(
        integer=None,
        success=False,
        cleaned_text=cleaned,
        extracted_thinking=thinking,
        error_message=f"Could not extract a valid integer from output: {raw_text!r}",
    )
