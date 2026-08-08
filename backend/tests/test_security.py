"""
Regression tests for password length handling in app.core.security.

Covers the review comment: hash_password()/verify_password() must reject
passwords over bcrypt's 72-byte limit instead of silently truncating them
(silent truncation would let two different long passwords that share the
same first 72 bytes authenticate as each other).
"""

import pytest

from app.core.security import PasswordTooLongError, hash_password, verify_password

_OVER_LIMIT_PASSWORD = "a" * 73  # 73 bytes, one over the 72-byte bcrypt limit
_AT_LIMIT_PASSWORD = "a" * 72  # exactly at the limit - should still work


def test_hash_password_rejects_password_over_72_bytes():
    with pytest.raises(PasswordTooLongError):
        hash_password(_OVER_LIMIT_PASSWORD)


def test_verify_password_rejects_password_over_72_bytes():
    hashed = hash_password(_AT_LIMIT_PASSWORD)
    with pytest.raises(PasswordTooLongError):
        verify_password(_OVER_LIMIT_PASSWORD, hashed)


def test_hash_and_verify_password_at_exactly_72_bytes_still_works():
    hashed = hash_password(_AT_LIMIT_PASSWORD)
    assert verify_password(_AT_LIMIT_PASSWORD, hashed) is True


def test_two_long_passwords_sharing_a_72_byte_prefix_are_not_confused():
    # Before the fix, both of these would silently truncate to the same 72
    # bytes and hash identically - this is the exact collision the review
    # comment flagged.
    password_a = "a" * 72 + "AAAA"
    password_b = "a" * 72 + "BBBB"
    with pytest.raises(PasswordTooLongError):
        hash_password(password_a)
    with pytest.raises(PasswordTooLongError):
        hash_password(password_b)
