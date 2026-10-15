import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestEndToEnd(unittest.TestCase):
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

    def test_brief_sample_and_same_day_sorting(self):
        """Shuffled rows are sorted chronologically, and same-day ties sort lexicographically (r1, r10, r2)."""
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-03,INFY,1498.00\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-02,INFY,1534.10\n"
        )
        rules_json = (
            "[\n"
            '  {"id":"r1","instrument":"INFY","type":"level","direction":"below","level":1500},\n'
            '  {"id":"r10","instrument":"INFY","type":"level","direction":"below","level":1510},\n'
            '  {"id":"r2","instrument":"INFY","type":"level","direction":"below","level":1500.5}\n'
            "]"
        )
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        expected_stdout = (
            "2026-09-03 r1 INFY level below 1500\n"
            "2026-09-03 r10 INFY level below 1510\n"
            "2026-09-03 r2 INFY level below 1500.5\n"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, expected_stdout)

    def test_weekend_gap_ma_cross(self):
        """A series with a weekend gap (Fri 09-04 to Mon 09-07) fires correctly on the 4th row (09-09)."""
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-04,TCS,10.0\n"
            "2026-09-07,TCS,10.0\n"
            "2026-09-08,TCS,10.0\n"
            "2026-09-09,TCS,8.0\n"
            "2026-09-10,TCS,12.0\n"
            "2026-09-11,TCS,14.0\n"
        )
        rules_json = (
            '[\n  {"id":"r3","instrument":"TCS","type":"ma_cross","short":2,"long":3,"direction":"below"}\n]'
        )
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        expected_stdout = "2026-09-09 r3 TCS ma_cross 2/3 below\n"
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, expected_stdout)

    def test_two_instruments_interleaved(self):
        """Interleaved rows of multiple instruments evaluate independently and sort by date then rule id."""
        prices_csv = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.0\n"
            "2026-09-01,TCS,3000.0\n"
            "2026-09-02,INFY,1490.0\n"
            "2026-09-02,TCS,3050.0\n"
        )
        rules_json = (
            "[\n"
            '  {"id":"r1","instrument":"INFY","type":"level","direction":"below","level":1500},\n'
            '  {"id":"r2","instrument":"TCS","type":"level","direction":"above","level":3020}\n'
            "]"
        )
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        expected_stdout = (
            "2026-09-02 r1 INFY level below 1500\n"
            "2026-09-02 r2 TCS level above 3020\n"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, expected_stdout)

    def test_unknown_instrument_prints_warning_and_exits_zero(self):
        """A rule referencing an instrument absent from prices logs a warning to stderr and exits 0."""
        prices_csv = "date,instrument,close\n2026-09-01,INFY,1500.0\n"
        rules_json = '[{"id":"r1","instrument":"BTC","type":"level","direction":"below","level":100}]'
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertIn("warning: rule r1: instrument BTC not found in prices", proc.stderr)

    def test_no_alerts_prints_nothing_and_exits_zero(self):
        """When no alert conditions are met, stdout is empty and exit code is 0."""
        prices_csv = "date,instrument,close\n2026-09-01,INFY,1500.0\n2026-09-02,INFY,1510.0\n"
        rules_json = '[{"id":"r1","instrument":"INFY","type":"level","direction":"below","level":1400}]'
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_bad_csv_gives_exit_one_and_stderr_message(self):
        """Malformed input data raises InputError, printing to stderr, empty stdout, and exit code 1."""
        prices_csv = "date,instrument,close\n2026-09-01,INFY,bad_close\n"
        rules_json = "[]"
        p_path = self.create_temp_file(prices_csv, suffix=".csv")
        r_path = self.create_temp_file(rules_json, suffix=".json")

        proc = self.run_cli([p_path, r_path])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("invalid close price 'bad_close'", proc.stderr)

    def test_wrong_argument_count_gives_exit_two(self):
        """Invoking alerts.py with incorrect argument count prints usage to stderr and exits 2."""
        proc = self.run_cli([])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("usage:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
