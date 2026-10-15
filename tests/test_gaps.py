import datetime
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from loader import InputError, load_prices
from rules import level_alerts, ma_cross_alerts


class TestMutationGaps(unittest.TestCase):
    def create_temp_file(self, content, suffix=".csv"):
        """Helper to create a temporary file with the given content."""
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=suffix)
        f.write(content)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def run_cli(self, args):
        """Helper to run alerts.py via subprocess with PROJECT_ROOT as cwd."""
        cmd = [sys.executable, "alerts.py"] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

    def test_level_loop_does_not_wrap_to_last_element_at_index_zero(self):
        """Index 0 must not be compared with series[-1] via negative index wrap-around."""
        # If loop started at 0 and compared series[0] with series[-1],
        # curr=1490 and prev=1510 would falsely trigger a below alert on 2026-09-01.
        series = [
            (datetime.date(2026, 9, 1), 1490.0),
            (datetime.date(2026, 9, 2), 1490.0),
            (datetime.date(2026, 9, 3), 1510.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [])

    def test_ma_cross_does_not_fire_on_first_full_window_row_with_undefined_prior(self):
        """An MA cross cannot fire at row long (index long - 1) because prior MA is undefined."""
        # For long=3, row 3 has a valid 3-day average, but row 2 did not.
        # With 4 rows, the drop on row 3 has no previous long average, and rows 3->4 stay below.
        series = [
            (datetime.date(2026, 9, 1), 100.0),
            (datetime.date(2026, 9, 2), 100.0),
            (datetime.date(2026, 9, 3), 50.0),
            (datetime.date(2026, 9, 4), 50.0),
        ]
        rule = {"type": "ma_cross", "direction": "below", "short": 2, "long": 3}
        self.assertEqual(ma_cross_alerts(series, rule), [])

    def test_date_regex_rejects_compact_iso_date(self):
        """Date 20260901 is accepted by Python 3.11+ fromisoformat but rejected by the regex."""
        path = self.create_temp_file("date,instrument,close\n20260901,INFY,1500\n")
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        self.assertIn("invalid date format", str(ctx.exception))

    def test_date_regex_rejects_week_date_format(self):
        """Date 2026-W36-1 is accepted by Python 3.11+ fromisoformat but rejected by the regex."""
        path = self.create_temp_file("date,instrument,close\n2026-W36-1,INFY,1500\n")
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        self.assertIn("invalid date format", str(ctx.exception))

    def test_csv_whitespace_stripped_around_fields(self):
        """Leading and trailing whitespace around CSV fields is stripped during loading."""
        content = (
            "  date  ,  instrument  ,  close  \n"
            " 2026-09-01 , INFY , 1520.50 \n"
            " 2026-09-02 , INFY , 1480.00 \n"
        )
        path = self.create_temp_file(content)
        data = load_prices(path)
        self.assertIn("INFY", data)
        self.assertEqual(data["INFY"][0], (datetime.date(2026, 9, 1), 1520.50))
        self.assertEqual(data["INFY"][1], (datetime.date(2026, 9, 2), 1480.00))

    def test_e2e_formats_float_whole_number_level_as_integer(self):
        """A rule level specified as 1500.0 in JSON prints as 1500 in end-to-end output."""
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1510.0\n"
            "2026-09-02,INFY,1490.0\n"
        )
        rules_json = '[{"id":"r1","instrument":"INFY","type":"level","direction":"below","level":1500.0}]'
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "2026-09-02 r1 INFY level below 1500\n")

    def test_e2e_sorts_by_date_then_id_across_multiple_dates(self):
        """Alerts across multiple dates are sorted primarily by date, not rule ID."""
        # z_rule on 2026-09-01 must precede a_rule on 2026-09-02 despite alphabetical id ordering
        prices_csv = (
            "date,instrument,close\n"
            "2026-08-31,INFY,1520.0\n"
            "2026-09-01,INFY,1490.0\n"
            "2026-09-02,INFY,1530.0\n"
        )
        rules_json = (
            "[\n"
            '  {"id":"z_rule","instrument":"INFY","type":"level","direction":"below","level":1500},\n'
            '  {"id":"a_rule","instrument":"INFY","type":"level","direction":"above","level":1510}\n'
            "]"
        )
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        expected_stdout = (
            "2026-09-01 z_rule INFY level below 1500\n"
            "2026-09-02 a_rule INFY level above 1510\n"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, expected_stdout)

    def test_level_below_pass_through_exact_equality(self):
        """Pass-through below (1510 -> 1500 -> 1490) confirms prev >= level is enforced."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1500.0),
            (datetime.date(2026, 9, 3), 1490.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 3)])

    def test_level_above_pass_through_exact_equality(self):
        """Pass-through above (1490 -> 1500 -> 1510) confirms prev <= level is enforced."""
        series = [
            (datetime.date(2026, 9, 1), 1490.0),
            (datetime.date(2026, 9, 2), 1500.0),
            (datetime.date(2026, 9, 3), 1510.0),
        ]
        rule = {"type": "level", "direction": "above", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 3)])


if __name__ == "__main__":
    unittest.main()
