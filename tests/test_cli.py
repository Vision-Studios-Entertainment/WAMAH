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


def test_generate_s4_refused_with_clear_message(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as exc:
        main(["generate", "--tier", "S4", "--out", str(tmp_path)])
    assert "capped at S3" in str(exc.value)
    assert not (tmp_path / "S4").exists()
