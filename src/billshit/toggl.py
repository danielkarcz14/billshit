"""Toggl HTTP client and pure time-entry aggregation."""

import base64
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import TogglSettings, number
from .errors import BillshitError
from .invoices import Hours
from .period import Period


def read_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise BillshitError(f"Cannot read Toggl token: {path}") from error
    if not token:
        raise BillshitError(f"Toggl token file is empty: {path}")
    return token


class TogglClient:
    BASE_URL = "https://api.track.toggl.com/api/v9/me"

    def __init__(self, token: str, opener=None):
        self._authorization = base64.b64encode(f"{token}:api_token".encode()).decode()
        self._open = opener or urlopen

    def get(self, path: str):
        request = Request(self.BASE_URL + path, headers={
            "Authorization": f"Basic {self._authorization}", "Accept": "application/json",
        })
        try:
            with self._open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            error.close()
            if error.code in (401, 403):
                message = "Toggl: invalid token or access denied"
            elif error.code in (402, 429):
                message = f"Toggl: API limit reached (HTTP {error.code})"
            else:
                message = f"Toggl: HTTP error {error.code}"
            raise BillshitError(message) from error
        except (URLError, TimeoutError, OSError) as error:
            raise BillshitError("Toggl: connection failed") from error
        except (ValueError, UnicodeError) as error:
            raise BillshitError("Toggl: invalid JSON response") from error

    def report(self, period: Period, settings: TogglSettings):
        profile = self.get("?with_related_data=true")
        query = urlencode({"start_date": period.start.isoformat(), "end_date": period.next_start.isoformat()})
        entries = self.get(f"/time_entries?{query}")
        return summarize(profile, entries, settings)


def quarter_hours(seconds: Decimal) -> Decimal:
    return (seconds / 900).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 4


@dataclass
class ProjectTotal:
    name: str
    category: str
    seconds: Decimal = Decimal(0)
    foreign_seconds: Decimal = Decimal(0)


@dataclass
class Report:
    hours: Hours
    projects: list[ProjectTotal] = field(default_factory=list)

    def print_summary(self, period: Period, settings: TogglSettings):
        for project in self.projects:
            hours = (project.seconds / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            suffix = ""
            if project.foreign_seconds:
                abroad = (project.foreign_seconds / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                suffix = f" (including {abroad} h abroad)"
            print(f"  {hours} h\t{project.category}\t{project.name}{suffix}")
        print(f"Toggl {period.label}: {settings.project_item} = {self.hours.projects} h, "
              f"{settings.internal_item} = {self.hours.internal} h, "
              f"{settings.foreign_item} = {self.hours.foreign} h")
        if self.hours.unassigned:
            print(f"WARNING: {self.hours.unassigned} h in Toggl have no project and were excluded from base hours.")


def _objects(value, label: str) -> list[dict]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise BillshitError(f"Toggl: invalid {label} response")
    return value


def summarize(profile, entries, settings: TogglSettings) -> Report:
    if not isinstance(profile, dict):
        raise BillshitError("Toggl: invalid profile response")
    workspaces = _objects(profile.get("workspaces", []), "workspaces")
    matching = [ws for ws in workspaces if ws.get("name") == settings.workspace]
    if len(matching) != 1 or matching[0].get("id") is None:
        raise BillshitError(f"Toggl: workspace not found or ambiguous: {settings.workspace}")
    workspace_id = matching[0]["id"]
    clients = {client.get("id"): client.get("name", "")
               for client in _objects(profile.get("clients") or [], "clients")}
    projects = {project.get("id"): project
                for project in _objects(profile.get("projects") or [], "projects")}
    totals = {key: Decimal(0) for key in ("internal", "projects", "foreign", "unassigned")}
    rows = {}
    for entry in _objects(entries, "time entries"):
        if entry.get("workspace_id") != workspace_id:
            continue
        seconds = number(entry.get("duration"), "Toggl duration")
        if seconds <= 0:
            continue  
        project = projects.get(entry.get("project_id"))
        if project is None:
            category, name = "unassigned", "(no project)"
        else:
            category = "internal" if clients.get(project.get("client_id"), "") in settings.internal_clients else "projects"
            name = project.get("name", "(unnamed project)")
        tags = entry.get("tags") or []
        if not isinstance(tags, list):
            raise BillshitError("Toggl: entry tags must be an array")
        foreign = bool(settings.foreign_tag and settings.foreign_tag in tags)
        totals[category] += seconds
        if foreign:
            totals["foreign"] += seconds
        row = rows.setdefault((name, category), ProjectTotal(name, category))
        row.seconds += seconds
        if foreign:
            row.foreign_seconds += seconds
    hours = Hours(*(quarter_hours(totals[key]) for key in ("internal", "projects", "foreign", "unassigned")))
    return Report(hours, sorted(rows.values(), key=lambda row: (row.name, row.category)))
