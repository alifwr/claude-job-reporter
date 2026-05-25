from pathlib import Path
from reporter.crawler import path_to_slug


def test_simple_path():
    assert path_to_slug(Path("/home/seratusjuta/reporter")) == "-home-seratusjuta-reporter"


def test_root_path():
    assert path_to_slug(Path("/")) == "-"


def test_path_with_dashes_preserved():
    assert path_to_slug(Path("/home/me/my-proj")) == "-home-me-my-proj"
