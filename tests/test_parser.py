"""Unit tests for the integer output and thinking parser."""

import pytest
from rsi_bench.parser import (
    clean_markdown_formatting,
    extract_inline_thinking,
    parse_integer_output,
)


class TestInlineThinkingExtraction:
    def test_extract_standard_think_tags(self):
        text = "<think>Let me choose an integer. 42 is nice.</think>42"
        cleaned, thinking = extract_inline_thinking(text)
        assert thinking == "Let me choose an integer. 42 is nice."
        assert cleaned == "42"

    def test_extract_thought_tags(self):
        text = "<thought>Thinking deeply about numbers...</thought>-77"
        cleaned, thinking = extract_inline_thinking(text)
        assert thinking == "Thinking deeply about numbers..."
        assert cleaned == "-77"

    def test_extract_multiline_thinking(self):
        text = "<think>\nStep 1: Pick a range\nStep 2: Generate 100\n</think>\n100"
        cleaned, thinking = extract_inline_thinking(text)
        assert "Step 1: Pick a range" in thinking
        assert cleaned == "100"

    def test_no_thinking_tags(self):
        text = "42"
        cleaned, thinking = extract_inline_thinking(text)
        assert thinking is None
        assert cleaned == "42"

    def test_unclosed_thinking_tag(self):
        text = "<think>Model got cut off mid-thought"
        cleaned, thinking = extract_inline_thinking(text)
        assert thinking == "Model got cut off mid-thought"
        assert cleaned == ""


class TestMarkdownCleaning:
    def test_clean_backticks(self):
        assert clean_markdown_formatting("`42`") == "42"
        assert clean_markdown_formatting("```\n42\n```") == "42"
        assert clean_markdown_formatting("```json\n-99\n```") == "-99"

    def test_clean_bold_and_italics(self):
        assert clean_markdown_formatting("**42**") == "42"
        assert clean_markdown_formatting("*42*") == "42"
        assert clean_markdown_formatting("__-500__") == "-500"

    def test_clean_brackets(self):
        assert clean_markdown_formatting("[42]") == "42"
        assert clean_markdown_formatting("(42)") == "42"


class TestParseIntegerOutput:
    def test_plain_integers(self):
        assert parse_integer_output("42").integer == 42
        assert parse_integer_output("42").success is True
        assert parse_integer_output("-100").integer == -100
        assert parse_integer_output("0").integer == 0
        assert parse_integer_output("9999999999").integer == 9999999999

    def test_whitespace_and_newlines(self):
        assert parse_integer_output("  42  \n").integer == 42
        assert parse_integer_output("\n\n-7\n\n").integer == -7

    def test_markdown_wrapped_integers(self):
        assert parse_integer_output("**42**").integer == 42
        assert parse_integer_output("`42`").integer == 42
        assert parse_integer_output("```\n42\n```").integer == 42
        assert parse_integer_output("```text\n-12\n```").integer == -12

    def test_trailing_punctuation(self):
        assert parse_integer_output("42.").integer == 42
        assert parse_integer_output("42!").integer == 42
        assert parse_integer_output("**42**.").integer == 42

    def test_common_prefix_formats(self):
        assert parse_integer_output("Output: 42").integer == 42
        assert parse_integer_output("Answer: -8").integer == -8
        assert parse_integer_output("Result: 100").integer == 100
        assert parse_integer_output("Random integer: 7").integer == 7
        assert parse_integer_output("Generated integer: 42").integer == 42

    def test_thinking_with_integer(self):
        res = parse_integer_output("<think>I need a random int</think>42")
        assert res.integer == 42
        assert res.success is True
        assert res.extracted_thinking == "I need a random int"

    def test_thinking_passed_from_provider(self):
        res = parse_integer_output("42", existing_thinking="Native provider reasoning")
        assert res.integer == 42
        assert res.extracted_thinking == "Native provider reasoning"

    def test_conversational_and_multiline_output(self):
        text = "Sure, here is your random integer:\n\n42"
        res = parse_integer_output(text)
        assert res.integer == 42
        assert res.success is True

    def test_empty_input(self):
        res = parse_integer_output("")
        assert res.integer is None
        assert res.success is False
        assert "Empty" in res.error_message

    def test_none_input(self):
        res = parse_integer_output(None)
        assert res.integer is None
        assert res.success is False

    def test_invalid_non_numeric(self):
        res = parse_integer_output("forty two")
        assert res.integer is None
        assert res.success is False

    def test_floating_point_is_not_an_integer(self):
        # The prompt asks for an integer, not a float
        res = parse_integer_output("3.14159")
        # Standalone integer regex won't match 3.14159 directly;
        # if inline integer regex matches 3, let's see if 3.14159 is rejected
        # Our INLINE_INTEGER_REGEX uses (?<![.\d])(-?\d+)(?![.\d]) which rejects 3.14159!
        assert res.success is False
