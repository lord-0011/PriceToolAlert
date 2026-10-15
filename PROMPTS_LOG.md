# Price Alert Tool - Assumptions & Prompts Log

## Assumptions (Locked Decisions)

| Item | Decision / Behavior | Reason |
|---|---|---|
| **Fire Frequency** | Fires on every day a crossing occurs (transition across boundary). | Alerts notify on state transitions; firing once ever would render rules permanently inactive. |
| **Level Equality (`close == level`)** | Strict inequality only ($P_{prev} > level$ and $P_{curr} < level$, or vice versa). Touching is not crossing. | Crossing means moving from one side strictly to the other; bouncing off doesn't cross. |
| **MA Equality (`short == long`)** | Strict inequality only. Touching or matching does not trigger an alert. | Signifies directional breakout/crossover, not momentary parity. |
| **Previous Day** | Immediately preceding chronological data row for that instrument. | Instrument-agnostic (crypto, forex, equities) cannot assume calendar days or weekdays. |
| **Day 1 / Initial Row** | Cannot fire on day 1 for an instrument. | Requires a previous trading row to establish crossing direction. |
| **MA Warm-up & Crossing Timing** | Requires full window for each MA ($N$). MA cross can only fire on day $L+1$ at the earliest. | Previous day's relationship must also have both MAs defined. |
| **Number Formatting** | Whole numbers printed without decimals (`1500`), decimals preserved only if fractional (`1500.5`). | Exact match with test expectations and spec examples. |
| **Date Parsing & Sorting** | Strict `YYYY-MM-DD` validated via regex then calendar parser; sorted as `datetime.date`. | String sorting fails on non-padded dates; rejects invalid calendar days like Feb 31. |
| **Duplicates** | Duplicate `(date, instrument)` raises `InputError` naming both line numbers. | Ambiguous prices corrupt time series and moving averages. |
| **Bad Rows Strategy** | Fail fast with `InputError` containing filename, line number, and bad value. | Silent skipping conceals corrupted data feeds. |
| **Header Names** | Case-insensitive (`col.strip().lower()`) and must appear exactly once. | Relaxed matching prevents failures on capitalized exports (`Date,Instrument,Close`). |
| **Instrument Names** | Exact case-sensitive match after stripping whitespace. | Ticker symbols are standardized identifiers; exporter whitespace must not break matching. |
| **Close Prices** | Must be positive finite numbers (`> 0`). Reject underscores (`1_520`), `NaN`, `Inf`. | Closes cannot be non-positive or malformed. |
| **Rule IDs** | Unique across file after stripping whitespace; ties broken by lexicographical rule id order. | Output alerts are ordered by date then rule ID. |
| **File Encodings** | `utf-8-sig` for both CSV and JSON (tolerates UTF-8 BOM and CRLF). | Cross-platform compatibility with Windows Notepad and Excel exports. |
| **Decode / CSV Errors** | `UnicodeDecodeError` and `csv.Error` caught and raised as `InputError`. | Unhandled tracebacks must never be exposed to the user. |
| **Huge Numbers** | Overflow during `math.isfinite` caught and raised as `InputError`. | Protects against memory/overflow attacks from arbitrary ints. |

---

## Prompt 1 (Phase 1: spec review & initial loader design)
**Prompt**:
> I'm building a Python 3 command-line price alert tool using only the standard library. DO NOT WRITE ANY CODE yet. Only analyse the spec.
> [Full prompt analyzing ambiguities, messy CSV/JSON inputs, MA edge cases, proposed behaviors, and hidden test conditions]

**What it got right**:
- Flagged fire frequency (every crossing vs once ever).
- Identified strict inequality requirements on level and MA equality.
- Recognized previous trading day = previous row, not calendar day.
- Highlighted MA warm-up timing ($L+1$ days required).
- Identified date sorting with real date objects vs strings.
- Regex plus calendar check on dates (`^\d{4}-\d{2}-\d{2}$` then `fromisoformat`).
- Explicit `bool` rejection (disallowing `True`/`False` as numbers or ints).
- Duplicate row detection naming both current and previous line numbers.
- Rejection of float windows like `5.0` (`type(val) is int`) and validation that `short < long`.
- Identified integer output formatting (`1500` vs `1500.0`).

**What it missed / got wrong**:
- **CSV UTF-8 Decode Errors**: Did not catch `UnicodeDecodeError` during CSV file reading (would produce raw traceback on invalid bytes like `0xFF`).
- **csv.Error Handling**: Did not handle `csv.Error` for broken CSV structures or NUL bytes.
- **JSON BOM**: Only specified BOM handling (`utf-8-sig`) for CSV, not JSON rules file.
- **Huge Integer Overflow**: Did not catch `OverflowError` when checking `math.isfinite()` on huge ints (e.g. `10**400`).
- **Underscore in Close Prices**: Did not reject `_` inside numbers, which `float()` silently accepts (e.g. `"1_520"`).
- **Duplicate Header Columns**: Used `header.index()` which silently took the first match if multiple identical header columns existed.
- **Case-Insensitive Headers**: Originally required exact lowercase headers instead of relaxing to `col.strip().lower()`.

**My decision**:
- All CSV and JSON loading must catch `UnicodeDecodeError`, `csv.Error`, and `OSError` and translate them into `InputError` prefixed with the filename.
- Both CSV and JSON must be opened with `encoding="utf-8-sig"`.
- Reject close prices containing `_`.
- Wrap `math.isfinite()` in `try ... except OverflowError` to reject giant integer levels with `InputError`.
- Ensure stripped `id` and `instrument` are stored and returned in the rule objects.
- Validate that each required header column (`date`, `instrument`, `close`) appears exactly once (`header.count(name) == 1`) after `col.strip().lower()`.

---

## Prompt 2 (Phase 3: pure rule logic)
**Prompt**:
> Create rules.py for a Python 3 price alert tool. Standard library only. Pure functions, no I/O, no printing. Keep it short and easy to explain.
> [level_alerts and ma_cross_alerts with exact crossing definitions and fresh SMA calculations]

**What it got right**:
- Implemented pure functional `level_alerts` with strict boundary crossing ($prev \ge level > curr$ for below, $prev \le level < curr$ for above).
- Index 0 correctly never fires.
- Implemented `ma_cross_alerts` with fresh SMA calculation on each index to prevent accumulated floating point drift.
- Strictly required $L+1$ rows before diff(i) and diff(i-1) both exist.
- Returned dates in chronological order without side effects or external libraries.

**What it missed / got wrong**:
- Assistant used raw float comparison for MA equality. Found via fuzzing against `fractions.Fraction`. Fixed with `round(diff, 9)` to eliminate floating-point division noise on mathematically equal averages.

**My decision**:
- Round MA differences to 9 decimal places (`round(sma(...) - sma(...), 9)`) so that mathematically equal averages compare as strictly equal ($diff == 0$).

---

## Prompt 3 (Phase 4: CLI alerts.py)
**Prompt**:
> Create alerts.py, the entry point for a Python 3 price alert tool. Standard library only. Keep it short.
> [CLI argument handling, warnings for missing instruments, chronological output formatting, whole number formatting]

**What it got right**:
- Strict exit code semantics (exit 2 for usage error, exit 1 for InputError, exit 0 for success).
- Warning on stderr when instrument in rule is missing from prices file (`warning: rule {id}: instrument {inst} not found in prices`) while continuing with other rules.
- Stable tie-breaking sort by `(date, rule_id)`.
- Number formatting preserving JSON representation (`1500`, `1500.5`, avoiding scientific notation like `1.5e+16` for whole floats).
- Output matches the brief's sample lines exactly.

---

## Prompt 4 (Phase 5: Comprehensive Unit & Integration Test Suite)
**Prompt**:
> Write unittest tests for my price alert tool. Standard library only.
> Run with: python -m unittest discover tests
> [test_loader.py, test_level.py, test_ma_cross.py, test_end_to_end.py with exact literal expected values and mutation testing]

**What it got right**:
- Implemented 46 unit and end-to-end tests across 4 dedicated test modules using only standard library `unittest`.
- End-to-end tests execute `alerts.py` in isolated subprocesses, validating exact stdout, stderr warnings, and exit codes (0, 1, 2).
- Covered all spec and edge case requirements:
  - Strict equality transitions, touching/bouncing immunity, initial day immunity, re-crossing behavior.
  - Hand-computed MA cross cases (windows 2 and 3), float noise equality invariance (`round(..., 9)`).
  - Robust loader testing: out-of-order date sorting, BOM stripping, CRLF, trailing blank lines, 0-byte file, duplicate header columns, invalid dates, malformed closes, duplicate row detection with both line numbers, unhandled byte protection.
  - Interleaved instruments, tie-breaking by `(date, rule_id)`, and missing instrument warnings.
- Verified test suite sensitivity via deliberate code mutations (e.g. changing `>=` to `>` in level and MA alerts causes immediate test failures).
- Added `tests/__init__.py` to ensure discoverability from any working directory.

---

## Prompt 5 (Mutation Analysis & README Documentation)
**Prompt**:
> Mutation testing revealed 6 surviving mutants across index boundaries, date formats, whitespace stripping, and sort priority. Add test_gaps.py with 9 targeted tests and complete README.md.

**What it got right**:
- Implemented `test_gaps.py` with 9 targeted tests, bringing test count to 55 tests.
- Successfully closed all 6 mutation gaps (negative index wrap-around, MA early start, compact/week ISO dates, CSV whitespace stripping, float level rendering, and multi-date chronological sort precedence).
- Documented complete project overview, running instructions, assumptions, prompt workflow, and detailed failure analysis in `README.md`.
