import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import patch

from billshit.app import Options, run
from billshit.config import number
from billshit.errors import BillshitError
from billshit.pdf import Renderer
from billshit.period import Period
from billshit.storage import load_toml, save_toml
from billshit.toggl import summarize
from tests.support import ENTRIES, PROFILE, project


class FakeClient:
    def __init__(self, token):
        assert token == "fake-token"

    def report(self, period, settings):
        return summarize(PROFILE, ENTRIES, settings)


class CliTests(unittest.TestCase):
    def test_help_errors_setup_and_removed_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = project(directory, configured=False)
            executable = paths.root / "billshit"
            def invoke(*args):
                return subprocess.run([sys.executable, str(executable), *args], cwd=directory,
                                      env={**os.environ, "TOGGL_TOKEN_FILE": str(paths.token)},
                                      capture_output=True, text=True)
            for flag in ("--help", "-h"):
                result = invoke(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--expenses", result.stdout)
                self.assertNotIn("--vydaje", result.stdout)
                self.assertFalse(paths.config.exists())
            for args in (("--unknown",), ("--expenses",), ("13-2026",),
                         *((flag,) for flag in ("--nova", "--vydaje", "nova",
                                                "--new", "--toggl", "--open", "--watch"))):
                result = invoke(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(paths.config.exists())
            result = invoke("10-2026")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("Configuration files created", result.stdout)
            original = paths.config.read_bytes()
            result = invoke("--pdf", "02-2024")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(paths.invoice(Period.parse("02-2024")).exists())
            self.assertEqual(paths.config.read_bytes(), original)
            self.assertFalse(paths.token.exists())
            link = paths.root.parent / "command-link"
            link.symlink_to(executable)
            result = subprocess.run([sys.executable, str(link), "--help"], cwd=directory, capture_output=True)
            self.assertEqual(result.returncode, 0)


@unittest.skipUnless(shutil.which("typst"), "Typst is required for PDF integration tests")
class WorkflowTests(unittest.TestCase):
    def test_default_workflow_repeat_and_failed_import_are_safe(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            paths = project(directory)
            period = Period.parse("10-2026")
            self.assertEqual(run(Options(period=period, expenses=Decimal("99.50")), paths,
                                 client_factory=FakeClient), 0)
            invoice_path = paths.invoice(period)
            pdf_path = paths.pdf(period, "test")
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            invoice = load_toml(invoice_path)
            self.assertEqual({row["nazev"]: row["mnozstvi"] for row in invoice["polozky"]}, {
                "Projektové práce - vyšší sazba": 2,
                "Interní projekty": 1,
                "Zvýšená sazba za práci v zahraničí": 2,
            })
            self.assertEqual(invoice["cislo"], "20261001")
            self.assertEqual(str(invoice["vystaveno"]), "2026-10-31")
            self.assertEqual(str(invoice["splatnost"]), "2026-11-30")
            invoice["cislo"] = "custom-number"
            invoice["polozky"][0]["cena"] = Decimal("123.45")
            save_toml(invoice_path, invoice)
            run(Options(period=period), paths, client_factory=FakeClient)
            updated = load_toml(invoice_path)
            self.assertEqual(updated["cislo"], "custom-number")
            self.assertEqual(updated["vydaje"], Decimal("99.50"))
            self.assertEqual(number(updated["polozky"][0]["cena"], "price"), Decimal("123.45"))
            before = invoice_path.read_bytes(), pdf_path.read_bytes()
            with patch.object(FakeClient, "report", side_effect=BillshitError("API failed")):
                with self.assertRaisesRegex(BillshitError, "API failed"):
                    run(Options(period=period), paths, client_factory=FakeClient)
                next_month = Period.parse("11-2026")
                with self.assertRaises(BillshitError):
                    run(Options(period=next_month), paths, client_factory=FakeClient)
                self.assertFalse(paths.invoice(next_month).exists())
            self.assertEqual((invoice_path.read_bytes(), pdf_path.read_bytes()), before)
            paths.token.unlink()
            # Rendering locally remains possible without token or network.
            run(Options(period=period, pdf=True), paths)

    def test_old_invoice_expenses_and_pdf_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            paths = project(directory)
            period = Period.parse("12-2026")
            run(Options(period=period), paths, client_factory=FakeClient)
            invoice_path, output = paths.invoice(period), paths.pdf(period, "test")
            document = load_toml(invoice_path)
            document.pop("vydaje")
            document["odberatel"] = {"nazev": "Jiná firma"}
            save_toml(invoice_path, document)
            run(Options(period=period, expenses=Decimal("12.50"), pdf=True), paths)
            updated = load_toml(invoice_path)
            self.assertEqual(updated["vydaje"], Decimal("12.50"))
            self.assertEqual(updated["odberatel"]["nazev"], "Jiná firma")
            self.assertEqual(str(updated["splatnost"]), "2027-01-31")
            renderer = Renderer(paths)
            before = output.read_bytes()
            with patch("billshit.pdf.subprocess.run", side_effect=subprocess.CalledProcessError(1, "typst")):
                with self.assertRaises(BillshitError):
                    renderer.render(invoice_path, output)
            self.assertEqual(output.read_bytes(), before)
            output.write_bytes(b"foreign PDF")
            with patch("billshit.pdf.subprocess.run") as process:
                with self.assertRaisesRegex(BillshitError, "--force"):
                    renderer.render(invoice_path, output)
                process.assert_not_called()
            renderer.render(invoice_path, output, force=True)
            self.assertTrue(output.read_bytes().startswith(b"%PDF"))
