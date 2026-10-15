# Price Alert Tool

Python 3 standard library only, nothing to install. Tested on Python 3.12.4.

    python alerts.py prices.csv rules.json      (Windows: py alerts.py ...)
    python -m unittest discover tests -v        (55 tests)

Exit codes: 0 ok, 1 bad input (message with file and line number on stderr), 2 wrong arguments.

## Assumptions
- A rule fires on every crossing, not once ever. Staying on the new side does not re-fire.
- Level: below fires when prev >= level and curr < level; above when prev <= level and curr > level.
  Touching and bouncing back does not fire; passing through an exact touch does.
- MA cross: same rule on (short MA - long MA) against 0. Needs both days' averages, so the earliest
  alert is row long+1.
- "Previous day" = previous row for that instrument, so weekends, holidays and 24/7 markets work.
- Bad input fails with the line number (bad date/close, wrong field count, duplicate instrument+date,
  zero/negative/NaN/inf close). Rule for an instrument not in the prices: warning on stderr, no output.
- Same-day ties sort by rule id as plain text (r10 before r2). Levels print numerically (1500.0 -> 1500).

## How I used the assistants
- Antigravity wrote the code. Prompts, in brief: (1) analyse the spec and list ambiguities, no code;
  (2) strict loader with line numbers; (3) pure rule functions with my exact semantics;
  (4) CLI with exit codes; (5) tests with hand-computed values.
- I used Claude as a second reviewer: it reviewed each file, ran random-data fuzzing against exact
  fraction arithmetic, and ran 25 injected bugs ("mutations") against my tests. Claude ran these;
  I reviewed the results and re-ran the test suite.

## What the assistant got wrong
1. Level equality used strict > on prev, so 1510 -> 1500 -> 1490 never fired. Fixed to >=.
2. Loader missed: BOM in rules.json, CSV decode errors, csv.Error, huge ints, "1_520", duplicate header columns.
3. MA equality broke on decimal prices: float noise made equal averages differ by ~1e-14.
   Fuzzing against fractions found 766 mismatches in 40,000 comparisons. Fixed with round(diff, 9) in rules.py.
4. My first 46 tests missed 6 of 25 injected bugs (e.g. level loop wrapping to the last row, output sorted
   by id before date, unstripped CSV spaces). Added test_gaps.py; one remaining mutant is harmless.

## Known limits & Notes
- round(diff, 9) is an absolute tolerance, so instruments priced near 1e-7 or below may miss crosses.
- Non-ASCII instrument names may fail on some Windows consoles.
- Blank lines count toward line numbers in error messages (via reader.line_num), matching editor line numbers.
