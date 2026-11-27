"""Smoke test: the app modules import without a database, LLM, or network."""


def test_core_modules_import():
    import app.chunking
    import app.context
    import app.rag
    import app.search
    import app.triage

    assert app.rag.IDK_ANSWER.startswith("I don't know")