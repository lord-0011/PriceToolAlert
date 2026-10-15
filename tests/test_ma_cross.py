import datetime
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rules import ma_cross_alerts


class TestMACrossAlerts(unittest.TestCase):
    def test_hand_computed_ma_cross_below_and_above(self):
        """Hand-computed 2/3 window series fires below on row 4 and above on row 6."""
        dates = [datetime.date(2026, 9, i) for i in range(1, 7)]
        closes = [10.0, 10.0, 10.0, 8.0, 12.0, 14.0]
        series = list(zip(dates, closes))

        rule_below = {"type": "ma_cross", "direction": "below", "short": 2, "long": 3}
        rule_above = {"type": "ma_cross", "direction": "above", "short": 2, "long": 3}

        # Row 4 is 2026-09-04 (diff goes from 0 to -0.333)
        self.assertEqual(ma_cross_alerts(series, rule_below), [datetime.date(2026, 9, 4)])
        # Row 5 (diff=0) is touching, row 6 (diff goes from 0 to +1.667) is 2026-09-06
        self.assertEqual(ma_cross_alerts(series, rule_above), [datetime.date(2026, 9, 6)])

    def test_series_shorter_than_long_plus_one_returns_empty(self):
        """A series shorter than long + 1 cannot have both diff(i-1) and diff(i) and returns []."""
        dates = [datetime.date(2026, 9, i) for i in range(1, 4)]
        closes = [10.0, 10.0, 8.0]
        series = list(zip(dates, closes))
        rule = {"type": "ma_cross", "direction": "below", "short": 2, "long": 3}
        self.assertEqual(ma_cross_alerts(series, rule), [])

    def test_fires_on_row_long_plus_one_at_earliest(self):
        """Row long + 1 (index long) is the earliest possible row to fire an MA cross."""
        dates = [datetime.date(2026, 9, i) for i in range(1, 5)]
        closes = [10.0, 10.0, 10.0, 8.0]
        series = list(zip(dates, closes))
        rule = {"type": "ma_cross", "direction": "below", "short": 2, "long": 3}
        self.assertEqual(ma_cross_alerts(series, rule), [datetime.date(2026, 9, 4)])

    def test_flat_prices_never_fire(self):
        """A flat series where all prices are identical remains at diff == 0 and never fires."""
        dates = [datetime.date(2026, 9, i) for i in range(1, 10)]
        closes = [100.0] * 9
        series = list(zip(dates, closes))
        rule_above = {"type": "ma_cross", "direction": "above", "short": 2, "long": 5}
        rule_below = {"type": "ma_cross", "direction": "below", "short": 2, "long": 5}
        self.assertEqual(ma_cross_alerts(series, rule_above), [])
        self.assertEqual(ma_cross_alerts(series, rule_below), [])

    def test_decimal_equality_does_not_misfire_from_float_noise(self):
        """Mathematical equality in decimal averages does not trigger spurious crosses due to float noise."""
        closes = [100.3, 100.1, 100.3, 99.9, 100.7, 99.9, 100.2, 100.3, 100.3, 99.9, 100.7, 99.9]
        dates = [datetime.date(2026, 9, i) for i in range(1, len(closes) + 1)]
        series = list(zip(dates, closes))
        rule = {"type": "ma_cross", "direction": "above", "short": 2, "long": 4}

        # Exact rational math fires on rows 5, 9, 12 (0-based indices 4, 8, 11)
        expected = [datetime.date(2026, 9, 5), datetime.date(2026, 9, 9), datetime.date(2026, 9, 12)]
        self.assertEqual(ma_cross_alerts(series, rule), expected)


if __name__ == "__main__":
    unittest.main()
