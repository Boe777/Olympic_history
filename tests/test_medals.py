"""Medal counting logic, including the team deduplication that official tables apply."""

import pandas as pd
import pytest

from olympics.loading import MEDALS
from olympics.medals import (
    MIXED_TEAM_CODE,
    assign_final_noc,
    medal_table,
    medals_by_country_and_sport,
    one_medal_per_event,
)


def team_event(noc, team, medal, event="Rowing Eight", games="2000 Summer", n=8):
    """Build n athlete rows representing one team result."""
    return pd.DataFrame(
        {
            "Team": [team] * n,
            "NOC": [noc] * n,
            "Games": [games] * n,
            "Event": [event] * n,
            "Sport": ["Rowing"] * n,
            "Medal": [medal] * n,
            "Year": [2000] * n,
        }
    )


@pytest.fixture
def noc_lookup():
    return pd.DataFrame(
        {"NOC": ["USA", "GBR", "FRA"], "region": ["USA", "Great Britain", "France"]}
    )


class TestTeamDeduplication:
    def test_an_eight_person_crew_counts_as_one_medal(self, noc_lookup):
        rows = team_event("USA", "USA", "Gold")
        table = medal_table(one_medal_per_event(assign_final_noc(rows, noc_lookup)))
        assert table.loc["USA", "Gold"] == 1

    def test_individual_results_are_not_collapsed(self, noc_lookup):
        rows = pd.concat(
            [
                team_event("USA", "USA", "Gold", event="100m", n=1),
                team_event("USA", "USA", "Gold", event="200m", n=1),
            ]
        )
        table = medal_table(one_medal_per_event(assign_final_noc(rows, noc_lookup)))
        assert table.loc["USA", "Gold"] == 2

    def test_two_countries_in_one_event_each_keep_their_medal(self, noc_lookup):
        rows = pd.concat(
            [team_event("USA", "USA", "Gold"), team_event("GBR", "Great Britain", "Silver")]
        )
        table = medal_table(one_medal_per_event(assign_final_noc(rows, noc_lookup)))
        assert table.loc["USA", "Gold"] == 1
        assert table.loc["GBR", "Silver"] == 1


class TestMixedTeams:
    def test_a_team_name_matching_its_region_is_not_mixed(self, noc_lookup):
        result = assign_final_noc(team_event("USA", "USA", "Gold"), noc_lookup)
        assert (result["NOC_final"] == "USA").all()

    def test_a_club_name_used_by_one_noc_only_is_not_mixed(self, noc_lookup):
        result = assign_final_noc(team_event("USA", "Yale University", "Gold"), noc_lookup)
        assert (result["NOC_final"] == "USA").all()

    def test_a_team_name_shared_across_nocs_is_mixed(self, noc_lookup):
        rows = pd.concat(
            [
                team_event("USA", "Mixed Crew", "Gold", n=2),
                team_event("GBR", "Mixed Crew", "Gold", n=2),
            ]
        )
        assert (assign_final_noc(rows, noc_lookup)["NOC_final"] == MIXED_TEAM_CODE).all()

    def test_mixed_teams_are_excluded_from_the_country_table(self, noc_lookup):
        rows = pd.concat(
            [
                team_event("USA", "Mixed Crew", "Gold", n=2),
                team_event("GBR", "Mixed Crew", "Gold", n=2),
                team_event("FRA", "France", "Silver", n=2),
            ]
        )
        table = medal_table(one_medal_per_event(assign_final_noc(rows, noc_lookup)))
        assert MIXED_TEAM_CODE not in table.index

    def test_mixed_teams_can_be_included_on_request(self, noc_lookup):
        rows = pd.concat(
            [
                team_event("USA", "Mixed Crew", "Gold", n=2),
                team_event("GBR", "Mixed Crew", "Gold", n=2),
            ]
        )
        table = medal_table(
            one_medal_per_event(assign_final_noc(rows, noc_lookup)), include_mixed=True
        )
        assert MIXED_TEAM_CODE in table.index


class TestMedalTableShape:
    def test_all_three_medal_columns_exist_even_when_absent_from_the_data(self, noc_lookup):
        rows = team_event("USA", "USA", "Gold")
        table = medal_table(one_medal_per_event(assign_final_noc(rows, noc_lookup)))
        assert list(table.columns) == [*MEDALS, "Total"]

    def test_total_equals_the_sum_of_the_three_medals(self, deduplicated):
        table = medal_table(deduplicated)
        assert (table["Total"] == table[list(MEDALS)].sum(axis=1)).all()

    def test_counts_are_never_negative(self, deduplicated):
        assert (medal_table(deduplicated) >= 0).all().all()

    def test_the_table_is_sorted_by_gold_first(self, deduplicated):
        golds = medal_table(deduplicated)["Gold"]
        assert golds.is_monotonic_decreasing

    def test_deduplication_never_increases_the_row_count(self, summer, noc):
        from olympics.loading import medal_rows

        assigned = assign_final_noc(medal_rows(summer), noc)
        assert len(one_medal_per_event(assigned)) <= len(assigned)


class TestSportBreakdown:
    def test_the_matrix_covers_the_requested_number_of_countries(self, deduplicated):
        assert len(medals_by_country_and_sport(deduplicated, top_n=5)) <= 5

    def test_row_totals_match_the_medal_table(self, deduplicated):
        matrix = medals_by_country_and_sport(deduplicated, top_n=5)
        table = medal_table(deduplicated).head(5)
        for country in matrix.index:
            assert matrix.loc[country].sum() == table.loc[country, "Total"]
