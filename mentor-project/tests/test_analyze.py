"""Phase 5 gate: query analysis + MATCH building (spec Phase 5, D5.1)."""
import re

from mentor.retrieve import analyze as A
from mentor.retrieve import lexical as L


def test_backticked_identifier_extracted():
    analysis = A.analyze("How does `create_user` work?")
    assert analysis.backticked == ["create_user"]
    assert "create_user" in analysis.identifiers


def test_route_like_token_extracted():
    analysis = A.analyze("What happens at `/users/signup`?")
    assert analysis.routes == ["/users/signup"]
    assert "users" in analysis.words and "signup" in analysis.words


def test_file_like_token_extracted():
    analysis = A.analyze("Show me users.py and the Dockerfile")
    assert "users.py" in analysis.files
    assert "Dockerfile" in analysis.files


def test_original_preserved_and_deduped():
    analysis = A.analyze("`User` model and User fields")
    assert analysis.original == "`User` model and User fields"
    assert analysis.identifiers.count("User") == 1
    assert analysis.identifiers[0] == "User"


def test_match_query_safe_alphabet():
    analysis = A.analyze("x' OR 1=1 -- /*")
    match = L.build_match(A.fts_terms(analysis))
    assert match == "" or re.fullmatch(r'("[a-z0-9]+"( OR "[a-z0-9]+")*)', match)
    # Structural keywords must be inert quoted literals, never syntax.
    assert " OR 1=1" not in match.replace('" OR "', "")


def test_fts_terms_from_all_types():
    analysis = A.analyze("Explain `register_user` at /users/signup in users.py")
    terms = A.fts_terms(analysis)
    for expected in ("register", "user", "users", "signup", "py"):
        assert expected in terms
