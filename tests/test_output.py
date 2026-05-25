from pathlib import Path
from reporter.output import deliver


def test_deliver_writes_file_and_echoes(tmp_path: Path, capsys):
    out_file = tmp_path / "report.md"
    deliver("HELLO REPORT", out_file, clipboard=False)
    assert out_file.read_text() == "HELLO REPORT"
    captured = capsys.readouterr()
    assert "HELLO REPORT" in captured.out


def test_deliver_calls_clipboard_when_enabled(tmp_path: Path, mocker):
    mock_copy = mocker.patch("reporter.output.pyperclip.copy")
    out_file = tmp_path / "r.md"
    deliver("X", out_file, clipboard=True)
    mock_copy.assert_called_once_with("X")


def test_deliver_skips_clipboard_when_disabled(tmp_path: Path, mocker):
    mock_copy = mocker.patch("reporter.output.pyperclip.copy")
    deliver("X", tmp_path / "r.md", clipboard=False)
    mock_copy.assert_not_called()


def test_deliver_survives_clipboard_failure(tmp_path: Path, mocker, capsys):
    mocker.patch(
        "reporter.output.pyperclip.copy",
        side_effect=Exception("no display"),
    )
    out_file = tmp_path / "r.md"
    deliver("X", out_file, clipboard=True)
    assert out_file.read_text() == "X"
    captured = capsys.readouterr()
    assert "clipboard" in captured.err.lower()


def test_deliver_creates_parent_dirs(tmp_path: Path):
    out_file = tmp_path / "nested" / "dir" / "r.md"
    deliver("X", out_file, clipboard=False)
    assert out_file.read_text() == "X"
