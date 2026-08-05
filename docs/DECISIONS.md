# Architecture decision records

## ADR-001: Analyse both seasons, and split only where the split is informative

**Status:** Accepted

**Context.** The dataset contains 221,167 Summer and 48,564 Winter rows. An earlier
draft of this rewrite filtered everything to the Summer Games. That silently changed
every headline number: the United States went from 2,814 medals to 2,535 and from
2,613 female athletes to 2,097, because 279 medals and 522 athletes belong to the
Winter Games.

**Decision.** Keep both seasons throughout. The research questions ask about the
Olympic Games, not about the Summer Olympic Games, so restricting the population
answers a narrower question than the one posed.

**Exception.** Question 2.3 reports the two seasons separately and compares them.
Winter medals are concentrated in far fewer nations, so hosting cannot open the same
breadth of new events that it can in Summer; that makes the seasonal difference a
testable hypothesis rather than a duplicated chart. Everywhere else a season split
would produce a second table saying much the same thing.

**Consequences.** `clean_events` still takes a `season` parameter, so any question
can be narrowed later without touching its analysis. The hosting functions take a
season-filtered frame, which is what makes the 2.3 comparison a two-line change.

---

## ADR-002a: Derive the host of each Games from the data

**Status:** Accepted, replaces a hardcoded year-to-country table

**Context.** Hosts were listed in a dictionary mapping year to country, typed from
outside knowledge and covering the Summer Games only. Nothing checked it against the
data, so Lillehammer 1994 was absent and Norway hosting its own Games never entered
the analysis. A year present in the data but missing from the table was silently
skipped.

**Decision.** Read the host from the dataset's own `City` column and map city to
country. `host_country_by_games` raises `UnknownHostCityError` on an unmapped city
rather than skipping it.

**Consequences.** Winter hosts come for free, which is what makes ADR-011 possible.
A test asserts every city in the data has a mapping, so extending the dataset to
Tokyo 2020 or Paris 2024 fails the suite instead of quietly producing an analysis
with missing hosts. The external knowledge shrinks from a year-country table that
cannot be checked to a city-country table that can.

**Edge case.** The 1956 Summer Games appear under two cities: Australian quarantine
law barred the horses, so the equestrian events were held in Stockholm. Melbourne
hosted the other eighteen sports and is treated as the host; Stockholm covers 298
rows and one sport. `SPLIT_GAMES` records this explicitly, and an unhandled split
raises rather than producing two hosts for one Games.

---

## ADR-002: Exclude hosting years from the host-nation baseline

**Status:** Accepted

**Context.** Host performance was compared against each country's mean across
all its Games, including the hosting year under test. The variable holding it
was named `avg_medals_other`, which is what it should have been but was not.

**Decision.** Build the baseline from non-hosting years only.

**Consequences.** The mean difference moves from 38.8 to 42.2 medals. The
direction of the finding is unchanged; its magnitude was being understated.
Countries whose only appearances were hosting years are dropped, since no
baseline exists for them.

**Guarded by.** `test_baseline_ignores_the_hosting_year` and
`test_including_the_host_year_would_give_a_different_answer`. The second exists
specifically so a regression to the original method fails the suite.

---

## ADR-003: Report the independence caveat with the statistic

**Status:** Accepted

**Context.** The Wilcoxon signed-rank test assumes independent pairs. Five
countries hosted more than once, each compared against the same baseline.

**Decision.** Keep the test, but return `n_repeat_host_countries` alongside the
p-value and state the limitation in the docstring, the README and here.

**Rationale.** A mixed-effects model would handle the dependency properly, but
with 28 pairs the added complexity would not change the conclusion. Publishing
a caveated result is more honest than publishing an uncaveated one or dropping
the analysis.

---

## ADR-004: Move the analysis out of the notebook

**Status:** Accepted

**Context.** Every calculation lived in notebook cells. Nothing could be tested,
reused or reviewed in isolation, and cells depended on execution order.

**Decision.** All logic lives in `src/olympics/` as pure functions taking and
returning dataframes. The notebook imports them and is narrative only.

**Consequences.** The suite runs in about a second without Jupyter. The notebook
is readable as an argument rather than as a program.

---

## ADR-005: Deduplicate team results to one medal per event

**Status:** Accepted

**Context.** The source has one row per athlete per event, so an eight-person
crew winning gold produces eight gold rows. Counting rows directly inflates team
sports enormously and does not match any official medal table.

**Decision.** Deduplicate on Games, Event, NOC and Medal before counting.

**Guarded by.** A test builds an eight-row crew and asserts the table shows one
gold, and a companion test asserts two separate individual events still count as
two.

---

## ADR-006: Bucket mixed-nationality teams rather than attributing them

**Status:** Accepted

**Context.** Some entries are teams whose athletes competed under a combined
banner. Crediting them to any single NOC would be arbitrary.

**Decision.** Flag them as `ZZX` and exclude them from country rankings by
default, with `include_mixed=True` available for inspection.

**Rationale.** ZZX is not a country, and leaving it in a country ranking puts a
non-country near the top of the table.

---

## ADR-007: Do not commit the dataset

**Status:** Accepted

**Context.** `input/athlete_events.csv` is 40 MB and was committed, making the
repository 46 MB to clone. Continuous integration cannot download it either,
because Kaggle requires authentication.

**Decision.** Remove it from the working tree, document the download in
`data/README.md`, and commit a 1.4 MB deterministic sample under
`tests/fixtures/` so the suite and CI run without it.

**Consequences.** CI runs on every push. The file remains in the repository's
history; rewriting three commits to purge it was judged not worth the risk for a
single-author project, and the history is an accurate record of what happened.

---

## ADR-008: Validate the data as untrusted input

**Status:** Accepted

**Context.** An analysis that silently accepts a malformed file produces a wrong
chart rather than an error, and a wrong chart is harder to notice than a
traceback.

**Decision.** `load_events` and `load_noc` raise `DatasetError` on a missing
schema. A dedicated test module asserts value domains, null contracts, year
coverage, numeric types, referential integrity between NOC codes and the region
lookup, and that each athlete id maps to exactly one name.

**Rationale.** These are the same checks a QA engineer applies to a form
submission, applied to a data pipeline. They are cheap to write and they fail
loudly at the point of entry rather than quietly three transformations later.

---

## ADR-009: Handle identical pairs without relying on SciPy

**Status:** Accepted

**Context.** When every hosting year matches its baseline exactly, SciPy's
behaviour depends on the version installed: some releases return a result with
a runtime warning, others raise `ValueError`. The same code passed on one
machine and failed on another.

**Decision.** Detect the all-zero case before calling SciPy and return
`p = 1.0` with a statistic of zero, which is the correct reading: identical
pairs are no evidence of a difference.

**Consequences.** The function behaves the same across SciPy versions. CI now
also runs on Python 3.13, where the discrepancy surfaced, and the SciPy pin was
relaxed to a compatible range rather than an exact version that does not build
on newer interpreters.

---

## ADR-010: Treat UserWarning as a test failure

**Status:** Accepted

**Context.** SciPy reports shaky statistical assumptions through `UserWarning`,
for example that a sample is too small for the normal approximation. A suite
that prints warnings and still reports green trains people to ignore them.

**Decision.** `pytest.ini` promotes `UserWarning` to an error. Deprecation and
future warnings from third-party libraries remain warnings, since they are
noise the project cannot act on directly.

**Consequences.** A test that constructs statistically inadequate data now fails
instead of passing with a note. The synthetic fixtures were enlarged to twelve
pairs so they exercise the statistics rather than the small-sample path.


---

## ADR-011: Report the hosting question separately by season

**Status:** Accepted

**Context.** Once hosts were derived from the data (ADR-002a), the Winter Games became
available to the hosting analysis at no extra cost. A hardcoded Summer-only host table
had previously made Lillehammer 1994 invisible.

**Decision.** Question 2.3 reports Summer and Winter separately and compares them,
with its own chart per season plus a ratio distribution. The other questions pool both
seasons, per ADR-001.

**Rationale.** Winter medals are concentrated in far fewer nations, so hosting cannot
open the same breadth of new events that it can in Summer. That makes the seasonal
difference a testable hypothesis rather than a duplicated chart.

**Result.** The hypothesis holds. Summer shows a median ratio of 2.47 with
p = 1.9e-08; Winter shows 1.08 with p = 0.148, which is not distinguishable from no
effect. Half the Winter hosts finished below their own baseline.

---

## ADR-012: Separate Yugoslavia from Serbia

**Status:** Accepted

**Context.** `noc_regions.csv` maps YUG, SCG and SRB all to "Serbia". Sarajevo 1984
was hosted by Yugoslavia, so the host would have been credited to Serbia and matched
against a baseline built from a different political entity.

**Decision.** Add YUG to `NOC_REGION_OVERRIDES` as "Yugoslavia", consistent with the
existing treatment of the Soviet Union, East Germany and West Germany.

**Consequences.** Historical states are treated as themselves rather than mapped to
successor states, throughout.
