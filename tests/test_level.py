import datetime
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rules import level_alerts


class TestLevelAlerts(unittest.TestCase):
    def test_level_cross_fires(self):
        """A normal crossing from strictly above to strictly below fires on the second day."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1490.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 2)])

    def test_touch_then_bounce_does_not_fire(self):
        """Touching the exact level and bouncing back does not count as a crossing."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1500.0),
            (datetime.date(2026, 9, 3), 1510.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [])

    def test_pass_through_equality_below_fires_on_third_day(self):
        """Moving through the exact level (1510 -> 1500 -> 1490) fires on the third day for below."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1500.0),
            (datetime.date(2026, 9, 3), 1490.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 3)])

    def test_pass_through_equality_above_fires_on_third_day(self):
        """Moving through the exact level (1490 -> 1500 -> 1510) fires on the third day for above."""
        series = [
            (datetime.date(2026, 9, 1), 1490.0),
            (datetime.date(2026, 9, 2), 1500.0),
            (datetime.date(2026, 9, 3), 1510.0),
        ]
        rule = {"type": "level", "direction": "above", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 3)])

    def test_first_day_never_fires(self):
        """The initial day has no previous day so it can never fire an alert."""
        series = [
            (datetime.date(2026, 9, 1), 1490.0),
            (datetime.date(2026, 9, 2), 1480.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [])

    def test_crossing_recrossing_and_crossing_again(self):
        """Crossing, returning to the other side, and crossing again fires on every crossing."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1490.0),
            (datetime.date(2026, 9, 3), 1510.0),
            (datetime.date(2026, 9, 4), 1490.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        expected = [datetime.date(2026, 9, 2), datetime.date(2026, 9, 4)]
        self.assertEqual(level_alerts(series, rule), expected)

    def test_staying_below_after_cross_does_not_refire(self):
        """Staying on the crossed side across multiple days does not re-fire."""
        series = [
            (datetime.date(2026, 9, 1), 1510.0),
            (datetime.date(2026, 9, 2), 1490.0),
            (datetime.date(2026, 9, 3), 1480.0),
            (datetime.date(2026, 9, 4), 1470.0),
        ]
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts(series, rule), [datetime.date(2026, 9, 2)])

    def test_single_row_and_empty_series_return_empty(self):
        """A series with only one row or zero rows returns an empty alert list."""
        rule = {"type": "level", "direction": "below", "level": 1500}
        self.assertEqual(level_alerts([], rule), [])
        single_row = [(datetime.date(2026, 9, 1), 1490.0)]
        self.assertEqual(level_alerts(single_row, rule), [])


if __name__ == "__main__":
    unittest.main()
