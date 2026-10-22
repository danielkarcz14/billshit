import io
import tempfile
import unittest
from decimal import Decimal
from urllib.error import HTTPError, URLError

from billshit.errors import BillshitError
from billshit.period import Period
from billshit.toggl import TogglClient, quarter_hours, summarize
from tests.support import ENTRIES, PROFILE, project, rules


class TogglTests(unittest.TestCase):
    def test_aggregation_filtering_and_rounding(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = rules(project(directory))
            entries = ENTRIES + [
                {"workspace_id": 1, "project_id": 20, "duration": 450},
                {"workspace_id": 1, "project_id": None, "duration": 900},
                {"workspace_id": 1, "project_id": 20, "duration": -1234},
                {"workspace_id": 2, "project_id": 20, "duration": 100000},
            ]
            report = summarize(PROFILE, entries, settings)
            self.assertEqual(report.hours.internal, Decimal("1.25"))
            self.assertEqual(report.hours.projects, 2)
            self.assertEqual(report.hours.foreign, 2)
            self.assertEqual(report.hours.unassigned, Decimal("0.25"))
            self.assertEqual(quarter_hours(Decimal(449)), 0)
            self.assertEqual(quarter_hours(Decimal(450)), Decimal("0.25"))
            self.assertEqual(summarize(PROFILE, [], settings).hours.internal, 0)
            with self.assertRaisesRegex(BillshitError, "workspace not found"):
                summarize({"workspaces": []}, entries, settings)
            with self.assertRaisesRegex(BillshitError, "invalid time entries"):
                summarize(PROFILE, {"error": "bad payload"}, settings)

    def test_http_errors_and_invalid_payload(self):
        for code, expected in ((401, "invalid token"), (429, "API limit"), (500, "HTTP error")):
            def fail(request, timeout, status=code):
                raise HTTPError(request.full_url, status, "failure", {}, None)
            with self.subTest(code=code), self.assertRaisesRegex(BillshitError, expected):
                TogglClient("fake-token", opener=fail).get("")
        def offline(request, timeout):
            raise URLError("offline")
        with self.assertRaisesRegex(BillshitError, "connection failed"):
            TogglClient("fake-token", opener=offline).get("")
        with self.assertRaisesRegex(BillshitError, "invalid JSON"):
            TogglClient("fake-token", opener=lambda *args, **kwargs: io.BytesIO(b"not JSON")).get("")

    def test_two_requests_with_correct_month_range(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            settings = rules(project(directory))
            calls = []
            def respond(request, timeout):
                calls.append(request.full_url)
                self.assertEqual(timeout, 30)
                self.assertTrue(request.get_header("Authorization").startswith("Basic "))
                payload = ENTRIES if "/time_entries?" in request.full_url else PROFILE
                return io.BytesIO(json.dumps(payload).encode())
            report = TogglClient("fake-token", opener=respond).report(Period.parse("12-2026"), settings)
            self.assertEqual(report.hours.projects, 2)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].endswith("?with_related_data=true"))
            self.assertTrue(calls[1].endswith("start_date=2026-12-01&end_date=2027-01-01"))
