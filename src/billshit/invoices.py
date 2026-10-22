"""Invoice documents and billing rules, independent of HTTP and rendering."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .config import TogglSettings, number
from .errors import BillshitError
from .period import Period


@dataclass(frozen=True)
class Hours:
    internal: Decimal
    projects: Decimal
    foreign: Decimal
    unassigned: Decimal


@dataclass
class Invoice:
    document: dict

    @classmethod
    def create(cls, template: dict, period: Period):
        document = deepcopy(template)
        document.update(cislo=period.number, vystaveno=period.issued, splatnost=period.due)
        return cls(document)

    def set_expenses(self, amount: Decimal):
        self.document["vydaje"] = number(amount, "Expenses")

    def apply_hours(self, hours: Hours, settings: TogglSettings, template: dict | None = None):
        items = self.document.setdefault("polozky", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise BillshitError("Invoice polozky must be an array of tables")
        for name, amount in (
            (settings.internal_item, hours.internal),
            (settings.project_item, hours.projects),
            (settings.foreign_item, hours.foreign),
        ):
            matches = [item for item in items if item.get("nazev") == name]
            if len(matches) > 1:
                raise BillshitError(f"Duplicate invoice item: {name}")
            if matches:
                matches[0]["mnozstvi"] = amount
            elif amount and name == settings.foreign_item and template is not None:
                candidates = [item for item in template.get("polozky", []) if item.get("nazev") == name]
                if len(candidates) != 1:
                    raise BillshitError(f"Expected one surcharge item in the template: {name}")
                item = deepcopy(candidates[0])
                item["mnozstvi"] = amount
                items.append(item)
            elif amount:
                raise BillshitError(f"Missing invoice item: {name} ({amount} h). Check the template and Toggl settings.")

    def validate(self):
        if not isinstance(self.document.get("cislo"), (str, int)) or isinstance(self.document["cislo"], bool):
            raise BillshitError("Invoice cislo must be a string or integer")
        for key in ("vystaveno", "splatnost"):
            if not isinstance(self.document.get(key), (date, str)):
                raise BillshitError(f"Invoice {key} must be a date or string")
        number(self.document.get("vydaje", 0), "Invoice vydaje")
        items = self.document.get("polozky", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise BillshitError("Invoice polozky must be an array of tables")
        for item in items:
            if not isinstance(item.get("nazev"), str) or not item["nazev"]:
                raise BillshitError("Each invoice item needs a nazev")
            number(item.get("cena"), f"Price of {item['nazev']}")
            if "mnozstvi" in item:
                number(item["mnozstvi"], f"Quantity of {item['nazev']}")
