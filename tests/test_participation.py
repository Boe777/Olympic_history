"""Female participation analysis."""

import pandas as pd
import pytest

from olympics.participation import (
    first_female_year_by_sport,
    participation_by_year,
    top_countries_by_female_athletes,
)


def athletes(**columns):
    return pd.DataFrame(columns)


class TestParticipationByYear:
    def test_counts_distinct_athletes_not_rows(self):
        """One athlete entered in three events is one participant."""
        frame = athletes(
            ID=[1, 1, 1, 2],
            Sex=["F", "F", "F", "M"],
            Year=[2000] * 4,
            NOC=["USA"] * 4,
            Sport=["Swimming"] * 4,
        )
        assert participation_by_year(frame).loc[2000, "female"] == 1

    def test_percentage_is_computed_correctly(self):
        frame = athletes(
            ID=[1, 2, 3, 4],
            Sex=["F", "F", "M", "M"],
            Year=[2000] * 4,
            NOC=["USA"] * 4,
            Sport=["Swimming"] * 4,
        )
        assert participation_by_year(frame).loc[2000, "female_pct"] == 50.0

    def test_a_year_with_no_women_reports_zero_not_an_error(self):
        frame = athletes(
            ID=[1, 2], Sex=["M", "M"], Year=[1896] * 2, NOC=["GRE"] * 2, Sport=["Athletics"] * 2
        )
        assert participation_by_year(frame).loc[1896, "female_pct"] == 0.0

    def test_a_year_with_only_women_reports_one_hundred(self):
        frame = athletes(
            ID=[1, 2], Sex=["F", "F"], Year=[2000] * 2, NOC=["USA"] * 2, Sport=["Swimming"] * 2
        )
        assert participation_by_year(frame).loc[2000, "female_pct"] == 100.0

    def test_total_always_equals_female_plus_male(self, summer):
        result = participation_by_year(summer)
        assert (result["total"] == result["female"] + result["male"]).all()

    @pytest.mark.parametrize("column", ["female", "male", "total"])
    def test_counts_are_never_negative(self, summer, column):
        assert (participation_by_year(summer)[column] >= 0).all()

    def test_percentage_stays_within_bounds(self, summer):
        pct = participation_by_year(summer)["female_pct"]
        assert pct.between(0, 100).all()

    def test_results_are_ordered_by_year(self, summer):
        assert participation_by_year(summer).index.is_monotonic_increasing

    def test_female_share_grew_over_the_century(self, summer):
        """A directional sanity check on the headline finding."""
        result = participation_by_year(summer)
        assert result["female_pct"].iloc[-1] > result["female_pct"].iloc[0]


class TestFirstFemaleYear:
    def test_returns_the_earliest_year_per_sport(self):
        frame = athletes(
            ID=[1, 2, 3],
            Sex=["F", "F", "M"],
            Year=[1928, 1900, 1896],
            Sport=["Athletics", "Athletics", "Athletics"],
            NOC=["USA"] * 3,
        )
        assert first_female_year_by_sport(frame)["Athletics"] == 1900

    def test_sports_with_no_female_entrants_are_absent(self):
        frame = athletes(
            ID=[1, 2],
            Sex=["M", "F"],
            Year=[1896, 1900],
            Sport=["Wrestling", "Tennis"],
            NOC=["USA"] * 2,
        )
        result = first_female_year_by_sport(frame)
        assert "Wrestling" not in result.index
        assert "Tennis" in result.index

    def test_the_result_is_sorted_earliest_first(self, summer):
        assert first_female_year_by_sport(summer).is_monotonic_increasing


class TestTopCountries:
    def test_returns_at_most_the_requested_number(self, summer):
        assert len(top_countries_by_female_athletes(summer, top_n=5)) <= 5

    def test_ordered_by_descending_count(self, summer):
        assert top_countries_by_female_athletes(summer, top_n=10).is_monotonic_decreasing

    def test_male_athletes_are_excluded(self):
        frame = athletes(
            ID=[1, 2, 3],
            Sex=["M", "M", "F"],
            Year=[2000] * 3,
            NOC=["GBR", "GBR", "USA"],
            Sport=["Rowing"] * 3,
        )
        result = top_countries_by_female_athletes(frame)
        assert "GBR" not in result.index
        assert result["USA"] == 1
