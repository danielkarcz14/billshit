"""Project paths, first-run setup and validated configuration."""

import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from tomlkit.items import Float

from .errors import BillshitError
from .storage import load_toml


@dataclass(frozen=True)
class Paths:
    root: Path
    token: Path

    @classmethod
    def for_project(cls, root: Path):
        token = Path(os.environ.get("TOGGL_TOKEN_FILE", str(Path.home() / ".config/toggl/token")))
        return cls(root.resolve(), token.expanduser().resolve())

    @property
    def config(self):
        return self.root / "data/config.toml"

    @property
    def template(self):
        return self.root / "data/nova.toml"

    def invoice(self, period):
        return self.root / "data/faktury" / period.label / "faktura.toml"

    def pdf(self, period, prefix):
        return self.invoice(period).with_name(f"{prefix}-{period.label}.pdf")


def prepare(paths: Paths, use_toggl: bool) -> bool:
    """Create missing user files. Return True when setup needs user input."""
    created = False
    for source, target in (
        (paths.root / "config.example.toml", paths.config),
        (paths.root / "sablona/nova.example.toml", paths.template),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and not target.is_symlink():
            contents = source.read_bytes()
            try:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            with os.fdopen(fd, "wb") as stream:
                stream.write(contents)
            created = True
    if use_toggl:
        paths.token.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return created


def number(value, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise BillshitError(f"{label} must be a number")
    result = Decimal(value.as_string().replace("_", "") if isinstance(value, Float) else str(value))
    if not result.is_finite():
        raise BillshitError(f"{label} must be finite")
    return result


@dataclass(frozen=True)
class TogglSettings:
    workspace: str
    internal_clients: tuple[str, ...]
    internal_item: str
    project_item: str
    foreign_tag: str
    foreign_item: str

    @classmethod
    def from_config(cls, config: dict):
        raw = config.get("toggl", {})
        if not isinstance(raw, dict):
            raise BillshitError("[toggl] must be a table")
        def text(key, default=None):
            value = raw.get(key, default)
            if not isinstance(value, str) or (not value and key != "tag_zahranici"):
                raise BillshitError(f"[toggl].{key} must be a non-empty string")
            return value
        clients = raw.get("interni_klienti")
        if not isinstance(clients, list) or not all(isinstance(item, str) for item in clients):
            raise BillshitError("[toggl].interni_klienti must be an array of strings")
        result = cls(text("workspace"), tuple(clients), text("polozka_interni"),
                     text("polozka_projekty"), text("tag_zahranici", ""),
                     text("polozka_zahranici"))
        if len({result.internal_item, result.project_item, result.foreign_item}) != 3:
            raise BillshitError("Toggl invoice item names must be distinct")
        return result


def load_settings(paths: Paths) -> tuple[dict, str]:
    settings = load_toml(paths.config)
    options = settings.get("nastaveni", {})
    if not isinstance(options, dict):
        raise BillshitError("[nastaveni] must be a table")
    prefix = options.get("prefix", "faktura")
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise BillshitError("[nastaveni].prefix may only contain ASCII letters, digits, _ and -")
    return settings, prefix
