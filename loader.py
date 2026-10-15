import csv
import datetime
import json
import math
import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InputError(Exception):
    pass


def load_prices(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)

            header_row = None
            for row in reader:
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                header_row = row
                break

            if header_row is None:
                raise InputError(f"{path}: empty file, header missing")

            header = [col.strip().lower() for col in header_row]
            header_len = len(header_row)
            for name in ("date", "instrument", "close"):
                if header.count(name) != 1:
                    raise InputError(f"{path}: header must contain '{name}' exactly once")

            date_idx = header.index("date")
            inst_idx = header.index("instrument")
            close_idx = header.index("close")

            prices = {}
            seen_entries = {}

            for row in reader:
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue

                if len(row) != header_len:
                    raise InputError(
                        f"{path}: line {reader.line_num}: expected {header_len} fields but got {len(row)}: {row}"
                    )

                fields = [col.strip() for col in row]
                inst = fields[inst_idx]
                date_str = fields[date_idx]
                close_str = fields[close_idx]

                if not inst:
                    raise InputError(
                        f"{path}: line {reader.line_num}: instrument name cannot be empty"
                    )

                if not DATE_RE.match(date_str):
                    raise InputError(
                        f"{path}: line {reader.line_num}: invalid date format '{date_str}', expected YYYY-MM-DD"
                    )

                try:
                    parsed_date = datetime.date.fromisoformat(date_str)
                except ValueError:
                    raise InputError(
                        f"{path}: line {reader.line_num}: invalid calendar date '{date_str}'"
                    )

                if "_" in close_str:
                    raise InputError(
                        f"{path}: line {reader.line_num}: invalid close price '{close_str}'"
                    )

                try:
                    close_val = float(close_str)
                except ValueError:
                    raise InputError(
                        f"{path}: line {reader.line_num}: invalid close price '{close_str}'"
                    )

                try:
                    is_finite = math.isfinite(close_val)
                except OverflowError:
                    is_finite = False

                if not is_finite:
                    raise InputError(
                        f"{path}: line {reader.line_num}: non-finite close price '{close_str}'"
                    )

                if close_val <= 0:
                    raise InputError(
                        f"{path}: line {reader.line_num}: close price must be positive, got '{close_str}'"
                    )

                key = (inst, parsed_date)
                if key in seen_entries:
                    prev_line = seen_entries[key]
                    raise InputError(
                        f"{path}: line {reader.line_num}: duplicate entry for instrument '{inst}' on date '{date_str}' (first seen on line {prev_line})"
                    )
                seen_entries[key] = reader.line_num

                if inst not in prices:
                    prices[inst] = []
                prices[inst].append((parsed_date, close_val))

            for inst in prices:
                prices[inst].sort(key=lambda x: x[0])

            return prices
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{path}: error reading file: {e}")


def load_rules(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise InputError(f"{path}: invalid JSON: {e}")
    except OSError as e:
        raise InputError(f"{path}: cannot read file: {e}")

    if not isinstance(data, list):
        raise InputError(f"{path}: top level must be a list, got {type(data).__name__}")

    rules = []
    seen_ids = {}

    for idx, rule in enumerate(data):
        if not isinstance(rule, dict):
            raise InputError(
                f"{path}: rule at index {idx} must be a dictionary, got {type(rule).__name__}"
            )

        if "id" not in rule:
            raise InputError(f"{path}: rule at index {idx} missing required field 'id'")
        rule_id = rule["id"]
        if not isinstance(rule_id, str):
            raise InputError(
                f"{path}: rule at index {idx} 'id' must be a string, got {type(rule_id).__name__}"
            )
        rule_id_clean = rule_id.strip()
        if not rule_id_clean:
            raise InputError(
                f"{path}: rule at index {idx} 'id' cannot be empty or whitespace-only"
            )

        if rule_id_clean in seen_ids:
            prev_idx = seen_ids[rule_id_clean]
            raise InputError(
                f"{path}: duplicate rule id '{rule_id_clean}' at index {idx} (first seen at index {prev_idx})"
            )
        seen_ids[rule_id_clean] = idx

        label = f"rule '{rule_id_clean}' (index {idx})"

        if "instrument" not in rule:
            raise InputError(f"{path}: {label} missing required field 'instrument'")
        inst = rule["instrument"]
        if not isinstance(inst, str):
            raise InputError(
                f"{path}: {label} 'instrument' must be a string, got {type(inst).__name__}"
            )
        inst_clean = inst.strip()
        if not inst_clean:
            raise InputError(
                f"{path}: {label} 'instrument' cannot be empty or whitespace-only"
            )

        if "type" not in rule:
            raise InputError(f"{path}: {label} missing required field 'type'")
        rule_type = rule["type"]
        if rule_type not in ("level", "ma_cross"):
            raise InputError(
                f"{path}: {label} invalid type '{rule_type}' (must be 'level' or 'ma_cross')"
            )

        if "direction" not in rule:
            raise InputError(f"{path}: {label} missing required field 'direction'")
        direction = rule["direction"]
        if direction not in ("above", "below"):
            raise InputError(
                f"{path}: {label} invalid direction '{direction}' (must be 'above' or 'below')"
            )

        cleaned_rule = {
            "id": rule_id_clean,
            "instrument": inst_clean,
            "type": rule_type,
            "direction": direction,
        }

        if rule_type == "level":
            if "level" not in rule:
                raise InputError(f"{path}: {label} missing required field 'level'")
            lvl = rule["level"]
            if isinstance(lvl, bool):
                raise InputError(f"{path}: {label} 'level' cannot be a boolean")
            if not isinstance(lvl, (int, float)):
                raise InputError(
                    f"{path}: {label} 'level' must be a number, got {type(lvl).__name__}"
                )
            try:
                is_finite = math.isfinite(lvl)
            except OverflowError:
                raise InputError(f"{path}: {label} 'level' is too large (overflow)")
            if not is_finite:
                raise InputError(f"{path}: {label} 'level' must be finite, got {lvl}")
            if lvl <= 0:
                raise InputError(
                    f"{path}: {label} 'level' must be positive, got {lvl}"
                )
            cleaned_rule["level"] = lvl

        elif rule_type == "ma_cross":
            for param in ("short", "long"):
                if param not in rule:
                    raise InputError(
                        f"{path}: {label} missing required field '{param}'"
                    )
                val = rule[param]
                if isinstance(val, bool):
                    raise InputError(f"{path}: {label} '{param}' cannot be a boolean")
                if type(val) is not int:
                    raise InputError(
                        f"{path}: {label} '{param}' must be an integer, got {type(val).__name__} ({val})"
                    )
                if val <= 0:
                    raise InputError(
                        f"{path}: {label} '{param}' must be positive, got {val}"
                    )
                cleaned_rule[param] = val

            if cleaned_rule["short"] >= cleaned_rule["long"]:
                raise InputError(
                    f"{path}: {label} 'short' ({cleaned_rule['short']}) must be strictly less than 'long' ({cleaned_rule['long']})"
                )

        rules.append(cleaned_rule)

    return rules
