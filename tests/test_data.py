import tempfile
import tomllib
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from decimal import Decimal

from billshit.errors import BillshitError
from billshit.config import number
from billshit.invoices import Hours, Invoice
from billshit.period import Period
from billshit.storage import load_toml, save_toml
from tests.support import project, rules


class PeriodTests(unittest.TestCase):
    def test_month_end_and_numbering(self):
        february = Period.parse("02-2024")
        self.assertEqual(february.number, "20240201")
        self.assertEqual(february.issued, date(2024, 2, 29))
        self.assertEqual(february.due, date(2024, 3, 31))
        self.assertEqual(Period.parse("12-2026").due, date(2027, 1, 31))

    def test_invalid_months(self):
        for value in ("00-2026", "13-2026", "1-2026", "2026-10", "01-0000", "12-9999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Period.parse(value)


class StorageTests(unittest.TestCase):
    def test_invoice_updates_preserve_comments_and_decimal_precision(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = project(directory)
            path = paths.invoice(Period.parse("10-2026"))
            path.parent.mkdir(parents=True)
            path.write_text('# Invoice note\ncislo = "custom"\nvystaveno = 2026-10-31\n'
                            'splatnost = 2026-11-30\n[[polozky]]\n'
                            'nazev = "Práce" # keep this\n'
                            'cena = 123.1234567890123456789 # exact rate\n')
            invoice = Invoice(load_toml(path))
            invoice.set_expenses(Decimal("1193.26"))
            invoice.validate()
            self.assertEqual(number(invoice.document["polozky"][0]["cena"], "price"),
                             Decimal("123.1234567890123456789"))
            save_toml(path, invoice.document)
            text = path.read_text()
            self.assertIn('# Invoice note', text)
            self.assertIn('nazev = "Práce" # keep this', text)
            self.assertIn('cena = 123.1234567890123456789 # exact rate', text)
            self.assertEqual(tomllib.loads(text, parse_float=Decimal)["vydaje"], Decimal("1193.26"))

    def test_failed_save_leaves_existing_invoice_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.toml"
            original = b'cislo = "20261001" # manual note\n'
            path.write_bytes(original)
            with self.assertRaises(BillshitError):
                save_toml(path, {"invalid": object()})
            self.assertEqual(path.read_bytes(), original)


class InvoiceTests(unittest.TestCase):
    def test_updates_preserve_rates_dates_overrides_and_expenses(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = project(directory)
            invoice = Invoice.create(load_toml(paths.template), Period.parse("10-2026"))
            invoice.document["cislo"] = "custom-number"
            invoice.document["odberatel"] = {"nazev": "Custom customer"}
            invoice.set_expenses(Decimal("12.50"))
            original = deepcopy(invoice.document)
            invoice.apply_hours(Hours(Decimal(1), Decimal(2), Decimal(3), Decimal(0)), rules(paths))
            invoice.validate()
            self.assertEqual(invoice.document["cislo"], "custom-number")
            self.assertEqual(invoice.document["vydaje"], Decimal("12.50"))
            for key in ("vystaveno", "splatnost", "odberatel"):
                self.assertEqual(invoice.document[key], original[key])
            self.assertEqual([row["cena"] for row in invoice.document["polozky"]], [100, 100, 100])

    def test_missing_base_item_fails_and_missing_surcharge_uses_template(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = project(directory)
            invoice = Invoice.create(load_toml(paths.template), Period.parse("10-2026"))
            invoice.document["polozky"].pop()
            template = load_toml(paths.template)
            template["polozky"][-1]["cena"] = 275
            invoice.apply_hours(Hours(Decimal(1), Decimal(2), Decimal(3), Decimal(0)),
                                rules(paths), template)
            self.assertEqual(invoice.document["polozky"][-1]["cena"], 275)
            template["polozky"][-1]["cena"] = 350
            invoice.apply_hours(Hours(Decimal(1), Decimal(2), Decimal(3), Decimal(0)),
                                rules(paths), template)
            self.assertEqual(invoice.document["polozky"][-1]["cena"], 275)
            invoice.document["polozky"].pop(0)
            with self.assertRaisesRegex(BillshitError, "Missing invoice item"):
                invoice.apply_hours(Hours(Decimal(1), Decimal(2), Decimal(0), Decimal(0)), rules(paths))
