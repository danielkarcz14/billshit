import shutil
from pathlib import Path

from billshit.config import Paths, TogglSettings, load_settings, prepare
from billshit.storage import load_toml, save_toml

ROOT = Path(__file__).resolve().parents[1]


def project(directory, configured=True):
    root = Path(directory) / "app with spaces"
    root.mkdir()
    shutil.copy(ROOT / "billshit", root)
    shutil.copy(ROOT / "config.example.toml", root)
    shutil.copytree(ROOT / "sablona", root / "sablona")
    shutil.copytree(ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
    paths = Paths(root, Path(directory) / "token")
    if configured:
        prepare(paths, False)
        settings = load_toml(paths.config)
        settings["nastaveni"]["prefix"] = "test"
        save_toml(paths.config, settings)
        template = load_toml(paths.template)
        for item in template["polozky"]:
            item["cena"] = 100
        save_toml(paths.template, template)
        paths.token.write_text("fake-token", encoding="utf-8")
    return paths


def rules(paths):
    return TogglSettings.from_config(load_settings(paths)[0])


PROFILE = {
    "workspaces": [{"id": 1, "name": "DataSentics"}],
    "clients": [{"id": 10, "name": "DataSentics Pre-Sales & Edu"}],
    "projects": [
        {"id": 20, "name": "Internal", "client_id": 10},
        {"id": 21, "name": "External", "client_id": 11},
    ],
}
ENTRIES = [
    {"workspace_id": 1, "project_id": 20, "duration": 3600, "tags": []},
    {"workspace_id": 1, "project_id": 21, "duration": 7200, "tags": ["foreign trip (only for SUBCO)"]},
]
