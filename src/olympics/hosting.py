"""Host-nation advantage.

The host of every Games is derived from the dataset's own `City` column rather
than from a hardcoded year-to-country table. Only the city-to-country mapping is
external knowledge, and a test asserts that every city present in the data has an
entry, so a dataset extended to Tokyo 2020 or Paris 2024 fails loudly instead of
silently dropping a host.

The comparison itself pairs each hosting year with that country's mean across its
non-hosting Games. Including the hosting year in its own baseline would let the
observation contaminate its own control.
"""

from __future__ import annotations

import logging

import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Country names here must match the `region` column of noc_regions.csv after the
# historical overrides in loading.NOC_REGION_OVERRIDES have been applied.
CITY_TO_COUNTRY: dict[str, str] = {
    # Summer
    "Athina": "Greece",
    "Paris": "France",
    "St. Louis": "USA",
    "London": "Great Britain",
    "Stockholm": "Sweden",
    "Antwerpen": "Belgium",
    "Amsterdam": "Netherlands",
    "Los Angeles": "USA",
    "Berlin": "Germany",
    "Helsinki": "Finland",
    "Melbourne": "Australia",
    "Roma": "Italy",
    "Tokyo": "Japan",
    "Mexico City": "Mexico",
    "Munich": "West Germany",
    "Montreal": "Canada",
    "Moskva": "Soviet Union",
    "Seoul": "South Korea",
    "Barcelona": "Spain",
    "Atlanta": "USA",
    "Sydney": "Australia",
    "Beijing": "China",
    "Rio de Janeiro": "Brazil",
    # Winter
    "Chamonix": "France",
    "Sankt Moritz": "Switzerland",
    "Lake Placid": "USA",
    "Garmisch-Partenkirchen": "Germany",
    "Oslo": "Norway",
    "Cortina d'Ampezzo": "Italy",
    "Squaw Valley": "USA",
    "Innsbruck": "Austria",
    "Grenoble": "France",
    "Sapporo": "Japan",
    "Sarajevo": "Yugoslavia",
    "Calgary": "Canada",
    "Albertville": "France",
    "Lillehammer": "Norway",
    "Nagano": "Japan",
    "Salt Lake City": "USA",
    "Torino": "Italy",
    "Vancouver": "Canada",
    "Sochi": "Russia",
}

# The 1956 Summer Games appear under two cities. Australian quarantine law barred
# the horses from entering the country, so the equestrian events were held in
# Stockholm. Melbourne hosted the other eighteen sports and is treated as the
# host; Stockholm's 298 rows cover a single sport.
SPLIT_GAMES: dict[tuple[int, str], str] = {(1956, "Summer"): "Melbourne"}


class UnknownHostCityError(KeyError):
    """Raised when the data contains a Games whose city has no mapping."""


def host_country_by_games(events: pd.DataFrame) -> pd.DataFrame:
    """Return one row per Games with its host country, derived from the data.

    Raises rather than skipping when a city is unmapped, so extending the dataset
    cannot silently produce an analysis with missing hosts.
    """
    games = events[["Year", "Season", "City"]].drop_duplicates()

    for (year, season), city in SPLIT_GAMES.items():
        mask = (games["Year"] == year) & (games["Season"] == season)
        games = games[~mask | (games["City"] == city)]

    unknown = sorted(set(games["City"]) - set(CITY_TO_COUNTRY))
    if unknown:
        raise UnknownHostCityError(
            f"no country mapping for host cities: {unknown}. Add them to CITY_TO_COUNTRY."
        )

    games = games.copy()
    games["host_country"] = games["City"].map(CITY_TO_COUNTRY)

    duplicated = games.duplicated(subset=["Year", "Season"]).sum()
    if duplicated:
        raise UnknownHostCityError(
            f"{duplicated} Games resolve to more than one host city. Add them to SPLIT_GAMES."
        )

    logger.info("Resolved hosts for %d Games", len(games))
    return games[["Year", "Season", "City", "host_country"]].sort_values(["Season", "Year"])


def medals_by_year_and_country(
    deduplicated: pd.DataFrame, noc: pd.DataFrame, hosts: pd.DataFrame
) -> pd.DataFrame:
    """Return one row per country per Games with its medal count and host flag."""
    region_by_noc = noc.set_index("NOC")["region"].to_dict()

    counts = deduplicated.groupby(["Year", "Season", "NOC_final"]).size().reset_index(name="medals")
    counts["country"] = counts["NOC_final"].map(region_by_noc)

    counts = counts.merge(
        hosts[["Year", "Season", "host_country"]], on=["Year", "Season"], how="left"
    )
    counts["is_host"] = counts["country"] == counts["host_country"]
    return counts.drop(columns=["host_country"])


def host_vs_baseline(counts: pd.DataFrame) -> pd.DataFrame:
    """Pair each hosting year with the country's mean across its NON-hosting Games.

    Countries that hosted but have no non-hosting Games in the data are dropped,
    since no baseline can be formed for them.
    """
    non_host_mean = (
        counts[~counts["is_host"]].groupby("country")["medals"].mean().rename("baseline_medals")
    )

    hosts = counts[counts["is_host"]].merge(non_host_mean, on="country", how="left")
    dropped = int(hosts["baseline_medals"].isna().sum())
    if dropped:
        logger.info("Dropped %d hosting years with no non-hosting baseline", dropped)

    hosts = hosts.dropna(subset=["baseline_medals"]).copy()
    hosts["difference"] = hosts["medals"] - hosts["baseline_medals"]
    hosts["ratio"] = hosts["medals"] / hosts["baseline_medals"]
    return hosts.sort_values("Year").reset_index(drop=True)


def host_advantage_test(hosts: pd.DataFrame) -> dict[str, float]:
    """Run a Wilcoxon signed-rank test on hosting year versus baseline.

    A paired non-parametric test is used because medal counts are skewed and the
    two values in each pair describe the same country.

    Caveat, reported alongside the result: several countries hosted more than
    once, so the pairs are not fully independent. The p-value is therefore
    optimistic and should be read as indicative rather than exact.
    """
    if len(hosts) < 2:
        raise ValueError("need at least two hosting years to run the test")

    differences = hosts["medals"] - hosts["baseline_medals"]

    if (differences == 0).all():
        # Every pair is identical, so there is no evidence of any difference.
        # SciPy's behaviour here varies by version: some raise, some warn.
        # Handling it explicitly keeps this function deterministic.
        logger.info("All hosting years match their baseline exactly")
        statistic, p_value = 0.0, 1.0
    else:
        statistic, p_value = stats.wilcoxon(hosts["medals"], hosts["baseline_medals"])

    return {
        "n_pairs": len(hosts),
        "n_repeat_host_countries": int((hosts["country"].value_counts() > 1).sum()),
        "median_difference": float(hosts["difference"].median()),
        "mean_difference": float(hosts["difference"].mean()),
        "median_ratio": float(hosts["ratio"].median()),
        "statistic": float(statistic),
        "p_value": float(p_value),
    }


def compare_seasons(
    deduplicated: pd.DataFrame, noc: pd.DataFrame, hosts: pd.DataFrame
) -> pd.DataFrame:
    """Run the host-advantage test separately for each season and tabulate both.

    Winter medals are concentrated in far fewer nations, so hosting cannot open
    the same breadth of new events that it can in Summer. Splitting the analysis
    tests whether the advantage differs in size between the two.
    """
    rows = {}
    for season in sorted(deduplicated["Season"].unique()):
        subset = deduplicated[deduplicated["Season"] == season]
        paired = host_vs_baseline(medals_by_year_and_country(subset, noc, hosts))
        rows[season] = host_advantage_test(paired)
    return pd.DataFrame(rows).T
