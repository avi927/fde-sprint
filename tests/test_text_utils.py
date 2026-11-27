"""Unit tests for app/text_utils.py."""

from app.text_utils import strip_code_fences


def test_plain_json_is_unchanged():
    assert strip_code_fences('{"a": 1}') == '{"a": 1}'


def test_json_fence_is_removed():
    assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_plain_fence_is_removed():
    assert strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_surrounding_whitespace_is_removed():
    assert strip_code_fences('  \n```json\n{"a": 1}\n```\n  ') == '{"a": 1}'