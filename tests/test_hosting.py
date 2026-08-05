"""Host-nation advantage.

Two things are guarded here that this rewrite corrected: hosts are derived from
the data rather than hardcoded, and the baseline excludes the hosting year.
"""

import pandas as pd
import pytest

from olympics.hosting import (
    CITY_TO_COUNTRY,
    SPLIT_GAMES,
    UnknownHostCityError,
    compare_seasons,
    host_advantage_test,
    host_country_by_games,
    host_vs_baseline,
    medals_by_year_and_country,
)


def games(rows):
    return pd.DataFrame(rows, columns=["Year", "Season", "City"])


def counts_frame(rows):
    """Build a year/country/medals frame with host flags already resolved."""
    frame = pd.DataFrame(rows, columns=["Year", "country", "medals", "is_host"])
    frame["Season"] = "Summer"
    return frame


def synthetic_hosts(medals, baseline, n=12):
    """n distinct hosting countries, each with two non-hosting Games."""
    rows = []
    for i, country in enumerate(
        [
            "Greece",
            "France",
            "USA",
            "Great Britain",
            "Sweden",
            "Belgium",
            "Netherlands",
            "Germany",
            "Finland",
            "Australia",
            "Italy",
            "Japan",
        ][:n]
    ):
        year = 1900 + i * 4
        rows.append((year, country, medals, True))
        rows.append((year + 100, country, baseline, False))
        rows.append((year + 200, country, baseline, False))
    return rows


class TestHostsAreDerivedFromTheData:
    """The correction: hosts come from the City column, not a hardcoded table."""

    def test_every_city_in_the_data_has_a_mapping(self, raw_events):
        """A dataset extended to Tokyo 2020 must fail loudly, not silently."""
        unmapped = set(raw_events["City"].unique()) - set(CITY_TO_COUNTRY)
        assert not unmapped, f"unmapped host cities: {sorted(unmapped)}"

    def test_an_unmapped_city_raises(self):
        with pytest.raises(UnknownHostCityError, match="no country mapping"):
            host_country_by_games(games([(2028, "Summer", "Atlantis")]))

    def test_one_host_per_games(self, raw_events):
        resolved = host_country_by_games(raw_events)
        assert not resolved.duplicated(subset=["Year", "Season"]).any()

    def test_winter_games_are_resolved_too(self, raw_events):
        """The hardcoded table only covered Summer, so Lillehammer was invisible."""
        resolved = host_country_by_games(raw_events)
        winter = resolved[resolved["Season"] == "Winter"]
        assert len(winter) > 15
        row = winter[winter["Year"] == 1994]
        assert row["host_country"].iloc[0] == "Norway"

    def test_a_known_summer_host_resolves(self, raw_events):
        resolved = host_country_by_games(raw_events)
        row = resolved[(resolved["Year"] == 2008) & (resolved["Season"] == "Summer")]
        assert row["host_country"].iloc[0] == "China"

    def test_the_split_1956_games_resolve_to_one_host(self, raw_events):
        """Equestrian events were held in Stockholm; Melbourne is the host."""
        resolved = host_country_by_games(raw_events)
        row = resolved[(resolved["Year"] == 1956) & (resolved["Season"] == "Summer")]
        assert len(row) == 1
        assert row["host_country"].iloc[0] == "Australia"

    def test_an_unhandled_split_games_raises(self):
        with pytest.raises(UnknownHostCityError, match="more than one host city"):
            host_country_by_games(games([(2020, "Summer", "Tokyo"), (2020, "Summer", "Sapporo")]))

    def test_split_games_entries_name_a_city_present_in_the_mapping(self):
        for city in SPLIT_GAMES.values():
            assert city in CITY_TO_COUNTRY

    def test_historical_states_are_named_not_mapped_to_successors(self):
        assert CITY_TO_COUNTRY["Moskva"] == "Soviet Union"
        assert CITY_TO_COUNTRY["Munich"] == "West Germany"
        assert CITY_TO_COUNTRY["Sarajevo"] == "Yugoslavia"

    def test_every_mapped_country_exists_in_the_noc_regions(self, noc):
        regions = set(noc["region"].dropna())
        missing = set(CITY_TO_COUNTRY.values()) - regions
        assert not missing, f"host countries with no NOC region: {sorted(missing)}"


class TestBaselineExcludesHostYears:
    """The other correction at the centre of this rewrite."""

    def test_baseline_ignores_the_hosting_year(self):
        frame = counts_frame(
            [(2008, "China", 100, True), (2004, "China", 40, False), (2012, "China", 40, False)]
        )
        assert host_vs_baseline(frame)["baseline_medals"].iloc[0] == 40.0

    def test_including_the_host_year_would_give_a_different_answer(self):
        """Guards against a regression to the original method."""
        frame = counts_frame(
            [(2008, "China", 100, True), (2004, "China", 40, False), (2012, "China", 40, False)]
        )
        assert host_vs_baseline(frame)["baseline_medals"].iloc[0] != frame["medals"].mean()

    def test_difference_is_host_minus_baseline(self):
        frame = counts_frame(
            [(2008, "China", 100, True), (2004, "China", 40, False), (2012, "China", 40, False)]
        )
        assert host_vs_baseline(frame)["difference"].iloc[0] == 60.0

    def test_ratio_is_host_over_baseline(self):
        frame = counts_frame(
            [(2008, "China", 100, True), (2004, "China", 40, False), (2012, "China", 40, False)]
        )
        assert host_vs_baseline(frame)["ratio"].iloc[0] == pytest.approx(2.5)

    def test_a_country_with_no_other_games_is_dropped(self):
        assert host_vs_baseline(counts_frame([(2008, "China", 100, True)])).empty

    def test_output_is_ordered_by_year(self):
        frame = counts_frame(
            [
                (1932, "USA", 150, True),
                (1904, "USA", 200, True),
                (1900, "USA", 50, False),
                (1908, "USA", 50, False),
            ]
        )
        assert host_vs_baseline(frame)["Year"].is_monotonic_increasing


class TestMedalCounts:
    def test_host_flag_is_set_for_a_known_pairing(self, deduplicated, noc, resolved_hosts):
        counts = medals_by_year_and_country(deduplicated, noc, resolved_hosts)
        row = counts[(counts["Year"] == 2008) & (counts["country"] == "China")]
        if not row.empty:
            assert bool(row["is_host"].iloc[0])

    def test_a_non_host_country_is_not_flagged(self, deduplicated, noc, resolved_hosts):
        counts = medals_by_year_and_country(deduplicated, noc, resolved_hosts)
        row = counts[(counts["Year"] == 2008) & (counts["country"] == "France")]
        if not row.empty:
            assert not bool(row["is_host"].iloc[0])

    def test_at_most_one_host_country_per_games(self, deduplicated, noc, resolved_hosts):
        counts = medals_by_year_and_country(deduplicated, noc, resolved_hosts)
        per_games = counts[counts["is_host"]].groupby(["Year", "Season"]).size()
        assert (per_games <= 1).all()


class TestStatistics:
    def test_the_test_needs_at_least_two_pairs(self):
        frame = counts_frame([(2008, "China", 100, True), (2004, "China", 40, False)])
        with pytest.raises(ValueError, match="at least two"):
            host_advantage_test(host_vs_baseline(frame))

    def test_result_reports_every_documented_field(self, deduplicated, noc, resolved_hosts):
        result = host_advantage_test(
            host_vs_baseline(medals_by_year_and_country(deduplicated, noc, resolved_hosts))
        )
        for key in (
            "n_pairs",
            "n_repeat_host_countries",
            "median_difference",
            "mean_difference",
            "median_ratio",
            "statistic",
            "p_value",
        ):
            assert key in result

    def test_p_value_is_a_probability(self, deduplicated, noc, resolved_hosts):
        result = host_advantage_test(
            host_vs_baseline(medals_by_year_and_country(deduplicated, noc, resolved_hosts))
        )
        assert 0.0 <= result["p_value"] <= 1.0

    def test_identical_pairs_yield_no_significance(self):
        """SciPy raises on all-zero differences in some versions; we must not."""
        result = host_advantage_test(host_vs_baseline(counts_frame(synthetic_hosts(50, 50))))
        assert result["median_difference"] == 0.0
        assert result["p_value"] == 1.0
        assert result["statistic"] == 0.0

    def test_a_negative_effect_is_reported_as_negative(self):
        """The function must not assume hosting helps."""
        result = host_advantage_test(host_vs_baseline(counts_frame(synthetic_hosts(10, 50))))
        assert result["median_difference"] < 0
        assert result["median_ratio"] < 1

    def test_a_positive_effect_is_reported_as_positive(self):
        result = host_advantage_test(host_vs_baseline(counts_frame(synthetic_hosts(90, 50))))
        assert result["median_difference"] > 0
        assert result["median_ratio"] > 1


class TestSeasonComparison:
    def test_both_seasons_are_reported(self, both_seasons_dedup, noc, resolved_hosts):
        table = compare_seasons(both_seasons_dedup, noc, resolved_hosts)
        assert set(table.index) == {"Summer", "Winter"}

    def test_each_season_carries_the_full_result(self, both_seasons_dedup, noc, resolved_hosts):
        table = compare_seasons(both_seasons_dedup, noc, resolved_hosts)
        assert "median_ratio" in table.columns
        assert "p_value" in table.columns

    def test_seasons_are_analysed_independently(self, both_seasons_dedup, noc, resolved_hosts):
        """A Summer host must not be counted as a host in the Winter analysis."""
        winter = both_seasons_dedup[both_seasons_dedup["Season"] == "Winter"]
        counts = medals_by_year_and_country(winter, noc, resolved_hosts)
        assert not counts[(counts["Year"] == 2016) & counts["is_host"]].shape[0]
