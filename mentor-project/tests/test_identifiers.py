"""Phase 4 gate: identifier splitting (spec Phase 4)."""
from mentor.index import identifiers as I


def test_split_cases():
    assert I.split_identifier("getUserById") == ["get", "user", "by", "id"]
    assert I.split_identifier("create_user") == ["create", "user"]
    assert I.split_identifier("User") == ["user"]
    assert I.split_identifier("HTTPServer") == ["http", "server"]
    assert I.split_identifier("API_V1_STR") == ["api", "v", "1", "str"]
    assert I.split_identifier("OAuth2Token") == ["o", "auth", "2", "token"]
    assert I.split_identifier("") == []
    assert I.split_identifier("x") == ["x"]


def test_identifiers_text_has_original_and_parts():
    text = I.identifiers_text("def register_user():\n    pass\n",
                              "backend/app/api/routes/users.py")
    for term in ("register_user", "register", "user", "users", "routes", "backend", "py"):
        assert term in text.split(" ")
    # No duplicates.
    terms = text.split(" ")
    assert len(terms) == len(set(terms))
