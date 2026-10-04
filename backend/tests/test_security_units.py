from app.security.passwords import hash_password, password_problems, verify_password
from app.services.audit import record_audit


class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_password_hash_round_trip():
    hashed = hash_password("Correct-Horse-42")
    assert hashed.startswith("$argon2")
    assert verify_password("Correct-Horse-42", hashed)
    assert not verify_password("correct-horse-42", hashed)


def test_verify_password_handles_missing_or_corrupt_hash():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "not-a-hash") is False


def test_password_policy():
    assert password_problems("Correct-Horse-42") == []
    assert len(password_problems("short")) == 3


def test_audit_strips_secret_fields():
    db = _FakeDb()
    entry = record_audit(
        db, "x", details={"email": "a@b.c", "password": "hunter2", "Token": "t", "cookies": "c"}
    )
    assert entry.details == {"email": "a@b.c"}
