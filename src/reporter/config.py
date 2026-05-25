"""Reporter configuration: load and save the TOML config file."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

DEFAULT_CONFIG_PATH = Path("~/.config/reporter/config.toml").expanduser()

DEFAULTS: dict[str, Any] = {
    "since": "24h",
    "model": "sonnet",
    "out_dir": Path("~/reports").expanduser(),
    "clipboard": True,
    "claude_binary": "claude",
}


@dataclass
class Config:
    projects: list[Path] = field(default_factory=list)
    since: str = DEFAULTS["since"]
    model: str = DEFAULTS["model"]
    out_dir: Path = DEFAULTS["out_dir"]
    clipboard: bool = DEFAULTS["clipboard"]
    claude_binary: str = DEFAULTS["claude_binary"]


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def load(path: Path) -> Config:
    """Load config from a TOML file. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with path.open("rb") as f:
        data = tomllib.load(f)

    defaults = data.get("defaults", {})
    claude_section = data.get("claude", {})

    return Config(
        projects=[_expand(p) for p in data.get("projects", [])],
        since=defaults.get("since", DEFAULTS["since"]),
        model=defaults.get("model", DEFAULTS["model"]),
        out_dir=_expand(defaults.get("out_dir", str(DEFAULTS["out_dir"]))),
        clipboard=defaults.get("clipboard", DEFAULTS["clipboard"]),
        claude_binary=claude_section.get("binary", DEFAULTS["claude_binary"]),
    )


def save(cfg: Config, path: Path) -> None:
    """Write config to a TOML file. Creates parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "projects": [str(p) for p in cfg.projects],
        "defaults": {
            "since": cfg.since,
            "model": cfg.model,
            "out_dir": str(cfg.out_dir),
            "clipboard": cfg.clipboard,
        },
        "claude": {"binary": cfg.claude_binary},
    }
    with path.open("wb") as f:
        tomli_w.dump(data, f)
