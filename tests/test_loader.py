import datetime
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from loader import InputError, load_prices, load_rules


class TestLoader(unittest.TestCase):
    def create_temp_file(self, content, mode="w", encoding="utf-8", suffix=".csv"):
        """Helper to create a temporary file with the given content."""
        f = tempfile.NamedTemporaryFile(mode=mode, delete=False, encoding=encoding if "b" not in mode else None, suffix=suffix)
        f.write(content)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_shuffled_dates_sorted_by_real_date(self):
        """Out-of-order date rows are sorted ascending by real date object, not string."""
        content = (
            "date,instrument,close\n"
            "2026-09-03,INFY,1500.0\n"
            "2026-09-01,INFY,1520.0\n"
            "2026-09-02,INFY,1510.0\n"
        )
        path = self.create_temp_file(content)
        data = load_prices(path)
        expected_dates = [
            datetime.date(2026, 9, 1),
            datetime.date(2026, 9, 2),
            datetime.date(2026, 9, 3),
        ]
        self.assertEqual([d for d, _ in data["INFY"]], expected_dates)

    def test_weekend_gap_is_fine(self):
        """Calendar gaps between trading dates (e.g., Friday to Monday) load cleanly."""
        content = "date,instrument,close\n2026-09-04,INFY,100.0\n2026-09-07,INFY,105.0\n"
        path = self.create_temp_file(content)
        data = load_prices(path)
        self.assertEqual(len(data["INFY"]), 2)

    def test_bom_handling(self):
        """UTF-8 byte order mark (BOM) is transparently stripped from prices CSV."""
        content = b"\xef\xbb\xbfdate,instrument,close\n2026-09-01,INFY,1500.0\n"
        path = self.create_temp_file(content, mode="wb")
        data = load_prices(path)
        self.assertIn("INFY", data)

    def test_crlf_handling(self):
        """Windows CRLF (\\r\\n) line endings are handled without error."""
        content = "date,instrument,close\r\n2026-09-01,INFY,1500.0\r\n"
        path = self.create_temp_file(content)
        data = load_prices(path)
        self.assertIn("INFY", data)

    def test_trailing_blank_line(self):
        """Trailing and embedded blank lines are skipped without error."""
        content = "date,instrument,close\n\n2026-09-01,INFY,1500.0\n\n   \n"
        path = self.create_temp_file(content)
        data = load_prices(path)
        self.assertEqual(len(data["INFY"]), 1)

    def test_header_only_returns_empty_dict(self):
        """A CSV file containing only the header returns an empty dictionary."""
        path = self.create_temp_file("date,instrument,close\n")
        self.assertEqual(load_prices(path), {})

    def test_zero_byte_file_raises(self):
        """A 0-byte file with no header raises InputError."""
        path = self.create_temp_file("")
        with self.assertRaises(InputError):
            load_prices(path)

    def test_whitespace_only_file_raises(self):
        """A file with only whitespace raises InputError because header is missing."""
        path = self.create_temp_file("   \n\t  \n")
        with self.assertRaises(InputError):
            load_prices(path)

    def test_capitalised_header_works(self):
        """Header column names are compared case-insensitively so Date,Instrument,Close succeeds."""
        path = self.create_temp_file("Date,Instrument,Close\n2026-09-01,INFY,1500\n")
        data = load_prices(path)
        self.assertIn("INFY", data)

    def test_duplicate_header_column_raises(self):
        """A header containing duplicate columns raises InputError."""
        path = self.create_temp_file("date,date,instrument,close\n2026-09-01,2026-09-01,INFY,1500\n")
        with self.assertRaises(InputError):
            load_prices(path)

    def test_bad_date_format_raises(self):
        """Date strings not matching YYYY-MM-DD exactly (e.g. 2026-9-1) raise InputError with line number."""
        path = self.create_temp_file("date,instrument,close\n2026-9-1,INFY,1500\n")
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        self.assertIn("line 2", str(ctx.exception))

    def test_impossible_calendar_date_raises(self):
        """Impossible calendar dates like 2026-02-31 pass regex but raise InputError during parsing."""
        path = self.create_temp_file("date,instrument,close\n2026-02-31,INFY,1500\n")
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        self.assertIn("line 2", str(ctx.exception))

    def test_bad_close_values_raise(self):
        """Malformed or non-positive close values raise InputError with line number."""
        bad_values = ["1,520.50", "NA", "inf", "nan", "0", "-5", "1_520"]
        for bad in bad_values:
            with self.subTest(bad=bad):
                path = self.create_temp_file(f"date,instrument,close\n2026-09-01,INFY,{bad}\n")
                with self.assertRaises(InputError) as ctx:
                    load_prices(path)
                self.assertIn("line 2", str(ctx.exception))

    def test_wrong_field_count_raises(self):
        """A row with fewer or more fields than the header raises InputError with line number."""
        path = self.create_temp_file("date,instrument,close\n2026-09-01,INFY\n")
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        self.assertIn("line 2", str(ctx.exception))

    def test_duplicate_row_raises_with_both_line_numbers(self):
        """Duplicate (date, instrument) rows raise InputError referencing both line numbers."""
        content = "date,instrument,close\n2026-09-01,INFY,1500.0\n2026-09-01,INFY,1520.0\n"
        path = self.create_temp_file(content)
        with self.assertRaises(InputError) as ctx:
            load_prices(path)
        msg = str(ctx.exception)
        self.assertIn("line 3", msg)
        self.assertIn("line 2", msg)

    def test_invalid_byte_raises_input_error(self):
        """An invalid raw UTF-8 byte in the CSV raises InputError instead of an unhandled traceback."""
        path = self.create_temp_file(b"date,instrument,close\n2026-09-01,INFY,\xff\n", mode="wb")
        with self.assertRaises(InputError):
            load_prices(path)

    # JSON Rules tests
    def test_rules_empty_list_is_ok(self):
        """An empty JSON rule list returns an empty list."""
        path = self.create_temp_file("[]", suffix=".json")
        self.assertEqual(load_rules(path), [])

    def test_rules_bool_level_raises(self):
        """A boolean level value (true/false) in a level rule raises InputError."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": true}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_short_gte_long_raises(self):
        """An MA rule where short >= long raises InputError."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "ma_cross", "direction": "above", "short": 5, "long": 5}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_float_window_raises(self):
        """Float window parameters like 5.0 raise InputError because integers are required."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "ma_cross", "direction": "above", "short": 5.0, "long": 20}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_duplicate_id_raises(self):
        """Duplicate rule IDs across the rules file raise InputError."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500},'
            '{"id": "r1", "instrument": "TCS", "type": "level", "direction": "above", "level": 3000}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_unknown_type_raises(self):
        """A rule with an unsupported type raises InputError."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "rsi", "direction": "below"}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_bad_direction_raises(self):
        """A rule with an invalid or uppercase direction raises InputError."""
        path = self.create_temp_file(
            '[{"id": "r1", "instrument": "INFY", "type": "level", "direction": "BELOW", "level": 1500}]',
            suffix=".json",
        )
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_invalid_json_raises(self):
        """Malformed JSON syntax raises InputError."""
        path = self.create_temp_file("[{bad json", suffix=".json")
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_top_level_not_a_list_raises(self):
        """A top-level JSON structure that is not a list raises InputError."""
        path = self.create_temp_file('{"id": "r1"}', suffix=".json")
        with self.assertRaises(InputError):
            load_rules(path)

    def test_rules_id_and_instrument_are_stripped(self):
        """Rule ID and instrument whitespace is stripped upon loading."""
        path = self.create_temp_file(
            '[{"id": "  r1  ", "instrument": "  INFY  ", "type": "level", "direction": "below", "level": 1500}]',
            suffix=".json",
        )
        rules = load_rules(path)
        self.assertEqual(rules[0]["id"], "r1")
        self.assertEqual(rules[0]["instrument"], "INFY")


if __name__ == "__main__":
    unittest.main()
