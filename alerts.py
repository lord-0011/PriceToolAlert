import sys

from loader import InputError, load_prices, load_rules
from rules import level_alerts, ma_cross_alerts


def format_level(val):
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    if isinstance(val, int):
        return str(val)
    return repr(val)


def main():
    if len(sys.argv) != 3:
        print("usage: python alerts.py prices.csv rules.json", file=sys.stderr)
        return 2

    prices_path = sys.argv[1]
    rules_path = sys.argv[2]

    try:
        prices = load_prices(prices_path)
        rules = load_rules(rules_path)
    except InputError as e:
        print(e, file=sys.stderr)
        return 1

    alerts = []
    for rule in rules:
        inst = rule["instrument"]
        rule_id = rule["id"]
        if inst not in prices:
            print(
                f"warning: rule {rule_id}: instrument {inst} not found in prices",
                file=sys.stderr,
            )
            continue

        series = prices[inst]
        if rule["type"] == "level":
            fired_dates = level_alerts(series, rule)
        else:
            fired_dates = ma_cross_alerts(series, rule)

        for d in fired_dates:
            alerts.append((d, rule_id, rule))

    alerts.sort(key=lambda item: (item[0], item[1]))

    for d, _, rule in alerts:
        date_str = d.isoformat()
        r_id = rule["id"]
        inst = rule["instrument"]
        direction = rule["direction"]

        if rule["type"] == "level":
            lvl_str = format_level(rule["level"])
            print(f"{date_str} {r_id} {inst} level {direction} {lvl_str}")
        else:
            s_win = rule["short"]
            l_win = rule["long"]
            print(f"{date_str} {r_id} {inst} ma_cross {s_win}/{l_win} {direction}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
