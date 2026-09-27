from wamah.cli import main


def test_verify_s1(capsys):
    assert main(["verify", "--tier", "S1"]) == 0
    out = capsys.readouterr().out
    assert "OK" in out and "HARM" in out


def test_verify_s2(capsys):
    assert main(["verify", "--tier", "S2"]) == 0
    assert "441" in capsys.readouterr().out


def test_alphabet_print(capsys):
    assert main(["alphabet"]) == 0
    out = capsys.readouterr().out
    assert "21 PROBES" in out and "21 HARNESSES" in out
    assert "T21" in out and "H12" in out


def test_generate_s5_refused_with_clear_message(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as exc:
        main(["generate", "--tier", "S5", "--out", str(tmp_path)])
    assert "capped at S4" in str(exc.value)
    assert not (tmp_path / "S5").exists()


def test_generate_s4_partial_with_limit(tmp_path):
    assert main(["generate", "--tier", "S4", "--category", "Q",
                 "--limit", "5", "--out", str(tmp_path)]) == 0
    path = tmp_path / "S4" / "q.jsonl"
    assert path.exists()
    rows = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 5


def test_review_survives_narrow_console(monkeypatch):
    # S4 poison payloads split the canary with zero-width characters; a cp1252
    # console cannot encode them, so printing must degrade instead of crash.
    import io
    import sys

    buf = io.BytesIO()
    narrow = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", narrow)

    assert main(["review", "--tier", "S4", "--category", "P", "--n", "1"]) == 0

    narrow.flush()
    assert b"S4-P-" in buf.getvalue()
