"""TOML documents with preserved comments and atomic writes."""

import os
import stat
import tempfile
from decimal import Decimal
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ConvertError, TOMLKitError

from .errors import BillshitError


@tomlkit.register_encoder
def encode_decimal(value):
    if not isinstance(value, Decimal):
        raise ConvertError()
    if not value.is_finite():
        raise BillshitError("Cannot write a non-finite invoice amount")
    text = format(value, "f")
    return tomlkit.value(text if "." in text else text + ".0")


def load_toml(path: Path):
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, TOMLKitError) as error:
        raise BillshitError(f"Cannot read {path}: {error}") from error


def dumps_toml(document: dict) -> str:
    try:
        return tomlkit.dumps(document)
    except (TOMLKitError, TypeError, ValueError) as error:
        raise BillshitError(f"Cannot serialize invoice: {error}") from error


def save_toml(path: Path, document: dict) -> None:
    text = dumps_toml(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
