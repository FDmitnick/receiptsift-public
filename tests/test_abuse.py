from pathlib import Path

import pytest

from backend.abuse import AbuseRepository, protected_subject


def test_subjects_are_pseudonymous_and_namespaced():
    secret = "a" * 32

    email = protected_subject(secret, "email", " User@Example.com ")
    same_email = protected_subject(secret, "email", "user@example.com")
    network = protected_subject(secret, "ip", "user@example.com")

    assert email == same_email
    assert email != network
    assert "example.com" not in email
    with pytest.raises(RuntimeError):
        protected_subject("short", "email", "user@example.com")


def test_rate_limit_and_challenge_threshold(tmp_path: Path):
    repository = AbuseRepository(tmp_path / "abuse.sqlite3")

    first = repository.check_and_record(
        subject_hash="network-1",
        action="registration",
        limit=3,
        window_seconds=86400,
        challenge_after=2,
    )
    second = repository.check_and_record(
        subject_hash="network-1",
        action="registration",
        limit=3,
        window_seconds=86400,
        challenge_after=2,
    )
    third = repository.check_and_record(
        subject_hash="network-1",
        action="registration",
        limit=3,
        window_seconds=86400,
        challenge_after=2,
    )
    blocked = repository.check_and_record(
        subject_hash="network-1",
        action="registration",
        limit=3,
        window_seconds=86400,
        challenge_after=2,
    )

    assert first.allowed is True and first.challenge_required is False
    assert second.allowed is True and second.challenge_required is True
    assert third.allowed is True and third.challenge_required is True
    assert blocked.allowed is False and blocked.retry_after_seconds > 0


def test_free_identity_cannot_be_immediately_reclaimed(tmp_path: Path):
    repository = AbuseRepository(tmp_path / "abuse.sqlite3")

    assert repository.claim_free_identity("identity-1", "user-1") is True
    assert repository.claim_free_identity("identity-1", "user-1") is True
    assert repository.claim_free_identity("identity-1", "user-2") is False
