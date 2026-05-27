from notes_recovery.services import timeline


def test_build_keyword_where_escape() -> None:
    where, params = timeline.build_keyword_where("o", ["ZTITLE1"], "a%b_")
    assert "ESCAPE '!'" in where
    assert params
    assert "!%" in params[0]
    assert "!_" in params[0]
