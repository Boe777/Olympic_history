# Olympic History

An analysis of the *120 years of Olympic history: athletes and results* dataset,
covering 271,116 athlete-event records from Athens 1896 to Rio 2016.

![CI](https://github.com/Boe777/Olympic_history/actions/workflows/ci.yml/badge.svg)

## What changed and why

This repository previously held a single notebook that carried the entire
analysis. The rewrite moved every calculation into an importable, tested package
and corrected two methodological errors that changed the results.

| | Before | After |
|---|---|---|
| Analysis code | Inline in the notebook | `src/olympics/`, importable and tested |
| Seasons | Pooled, but the host table covered Summer only | Pooled, with 2.3 reported separately per season |
| Host lookup | Hardcoded year-to-country table | Derived from the data's City column |
| Host-year baseline | Included the hosting year | Excludes it |
| Independence caveat | Not stated | Reported with the result |
| Tests | 0 | 92 (100% coverage) |
| Dataset in the repository | 40 MB committed | Downloaded; 1.4 MB fixture for tests |
| CI | None | Lint, tests on two Python versions, dependency audit |

Full reasoning in [docs/DECISIONS.md](docs/DECISIONS.md).

## The two corrections

**Seasons were being mixed.** 14.3% of medal rows come from the Winter Games,
but the host-country table only listed Summer hosts. Norway hosting Lillehammer
in 1994 was never counted, while 1932 merged Los Angeles and Lake Placid into a
single United States figure. Summer and Winter have different participating
nations and different medal distributions; combining them describes neither.
The analysis is now scoped to the Summer Games, and `season` is a parameter, so
the Winter equivalent is a one-line change rather than a rewrite.

**The host-year baseline contained the host year.** Host performance was
compared against a country's mean across *all* its Games, including the year
being tested, so each observation contaminated its own control. The variable was
even named `avg_medals_other`. Excluding hosting years from the baseline moves
the mean difference from 38.8 to 42.2 medals.

## Findings

**Female participation** rose from 0% of athletes in 1896 to 45% in 2016.
Growth was near-flat until 1928, then rose steadily, with the sharpest gains
after 1976. Croquet, equestrianism, golf, sailing and tennis admitted women
first, between 1900 and 1912.

**Medal totals**, counted the way official tables do (one medal per team result, not
one per athlete), put the United States far ahead with 2,814 medals, followed by the
Soviet Union with 1,196 and Germany with 1,002.

**Hosting is associated with a large advantage in Summer, and none in Winter.**

| | Hosting years | Median ratio | Median difference | p |
|---|---|---|---|---|
| Summer | 29 | 2.47x | +20.8 medals | 1.9e-08 |
| Winter | 22 | 1.08x | +1.1 medals | 0.148 |

Winter is not distinguishable from no effect, and half its hosts finished below
their own baseline. The likely reason is structural: Winter medals are concentrated
in far fewer nations, so hosting cannot open the same breadth of new events.

Both p-values are optimistic and the code says so: several countries hosted more
than once, so the pairs are not fully independent. This is association, not a causal
estimate: hosts also field larger teams, enter more events, and invest in the years
beforehand.

## Test approach

The dataset is treated as untrusted input, the way a submitted form would be.
92 tests run in about a second against a committed fixture, so they need no
download and no network.

**Data quality.** Schema presence, value domains (`Sex` in {M, F}, `Medal` in
{Gold, Silver, Bronze} or null, `Season` in {Summer, Winter}), year coverage,
NOC code format, plausible ages, null contracts per column, referential
integrity between event NOCs and the region lookup, and one name per athlete id.

**Transformation contracts.** A rowing eight winning gold counts once, not eight
times. Individual results are not collapsed. Team names shared across NOCs are
bucketed as mixed rather than credited arbitrarily. Deduplication never adds
rows. `Total` always equals Gold plus Silver plus Bronze.

**Statistical correctness.** One test asserts the baseline excludes the hosting
year; a second asserts that including it would produce a different number, so a
regression to the original method fails the suite. Countries with no non-hosting
Games are dropped rather than compared against nothing.

**Host resolution.** A test asserts every host city present in the data has a country
mapping, so a dataset extended to Tokyo 2020 fails the suite rather than silently
dropping a host. Another asserts the 1956 Games, which appear under two cities,
resolve to exactly one host, and that an unhandled split raises.

**Edge cases.** A year with no women reports 0%, not a division error. A year
with only women reports 100%. Sports that never admitted women are absent rather
than null. A malformed CSV raises rather than producing a silently wrong chart.

## Layout

```
src/olympics/
├── loading.py         schema validation, cleaning, season filter
├── medals.py          mixed-team detection, per-event deduplication, tables
├── participation.py   distinct-athlete counts by year, sport and country
└── hosting.py         host mapping, baseline construction, significance test

tests/                 92 tests, 100% coverage of src/
notebooks/             narrative and charts; imports src, contains no logic
docs/DECISIONS.md      thirteen architecture decision records
data/README.md         how to obtain the dataset
```

The notebook is now narrative only. Every calculation it displays comes from a
function that is tested independently.

## Running it

```bash
git clone https://github.com/Boe777/Olympic_history.git
cd Olympic_history
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

# Download the dataset into data/ as described in data/README.md
jupyter notebook notebooks/olympic_history.ipynb
```

## Running the tests

```bash
pytest
```

No download required; the suite uses the committed fixture.

## Known limitations

- Repeated hosts break the independence assumption of the paired test.
- The host advantage is an association, not a causal estimate.
- Political boundaries shift across 120 years. The Soviet Union, East and West
  Germany and the Unified Team are treated as distinct entities rather than
  mapped to successor states.
- Mixed-nationality teams are bucketed as ZZX and excluded from country
  rankings; they are not attributed to any nation.
- Questions 1.1 to 2.2 pool both seasons. `clean_events` takes a `season` parameter,
  so any of them can be narrowed without touching its analysis.
- The dataset ends at Rio 2016.

## Data

*120 years of Olympic history: athletes and results*, compiled by rgriffin from
Sports Reference, published on Kaggle. See [data/README.md](data/README.md).
