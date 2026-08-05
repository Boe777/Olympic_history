"""Data quality checks.

An analysis is only as trustworthy as its input. These treat the dataset the
way a QA engineer treats a form submission: as untrusted until asserted. They
catch the silent failures that would otherwise surface as a wrong chart rather
than an error message.
"""

import numpy as np
import pandas as pd
import pytest

from olympics.loading import (
    EVENT_COLUMNS,
    FIRST_YEAR,
    LAST_YEAR,
    MEDALS,
    SEASONS,
    DatasetError,
    clean_events,
    load_events,
    load_noc,
    medal_rows,
)


class TestSchema:
    def test_all_expected_columns_are_present(self, raw_events):
        assert set(EVENT_COLUMNS) <= set(raw_events.columns)

    def test_noc_file_has_its_key_columns(self, noc):
        assert {"NOC", "region"} <= set(noc.columns)

    def test_missing_columns_raise_rather_than_pass_silently(self, tmp_path):
        broken = tmp_path / "broken.csv"
        broken.write_text("ID,Name\n1,Someone\n")
        with pytest.raises(DatasetError, match="missing columns"):
            load_events(broken)

    def test_missing_noc_columns_raise(self, tmp_path):
        broken = tmp_path / "broken.csv"
        broken.write_text("NOC,notes\nUSA,x\n")
        with pytest.raises(DatasetError, match="missing columns"):
            load_noc(broken)


class TestValueDomains:
    def test_sex_has_only_the_two_documented_values(self, summer):
        assert set(summer["Sex"].dropna().unique()) <= {"M", "F"}

    def test_season_column_holds_only_known_seasons(self, raw_events):
        assert set(raw_events["Season"].unique()) <= set(SEASONS)

    def test_medal_column_holds_only_the_three_medals_or_null(self, summer):
        assert set(summer["Medal"].dropna().unique()) <= set(MEDALS)

    def test_years_fall_inside_the_documented_coverage(self, raw_events):
        assert raw_events["Year"].min() >= FIRST_YEAR
        assert raw_events["Year"].max() <= LAST_YEAR

    def test_noc_codes_are_three_uppercase_letters(self, summer):
        codes = summer["NOC"].dropna().unique()
        assert all(len(c) == 3 and c.isupper() for c in codes)

    def test_ages_are_plausible(self, raw_events):
        ages = raw_events["Age"].dropna()
        assert ages.min() >= 5
        assert ages.max() <= 100


class TestCompleteness:
    @pytest.mark.parametrize("column", ["ID", "Name", "Sex", "NOC", "Year", "Season", "Event"])
    def test_columns_that_must_never_be_null(self, raw_events, column):
        assert raw_events[column].notna().all()

    def test_medal_is_expected_to_be_mostly_null(self, raw_events):
        """Most entries do not win a medal; a low null rate would signal a bug."""
        assert raw_events["Medal"].isna().mean() > 0.5

    def test_every_noc_in_the_events_can_be_resolved_to_a_region(self, summer, noc):
        known = set(noc["NOC"])
        unknown = set(summer["NOC"].dropna()) - known
        assert not unknown, f"NOC codes with no region mapping: {sorted(unknown)}"


class TestCleaning:
    def test_duplicate_rows_are_removed(self, raw_events):
        cleaned = clean_events(raw_events, season=None)
        assert not cleaned.duplicated().any()

    def test_season_filter_keeps_only_that_season(self, summer):
        assert set(summer["Season"].unique()) == {"Summer"}

    def test_season_none_keeps_every_season(self, raw_events):
        both = clean_events(raw_events, season=None)
        assert set(both["Season"].unique()) == set(raw_events["Season"].unique())

    def test_unknown_season_is_rejected(self, raw_events):
        with pytest.raises(DatasetError, match="season must be"):
            clean_events(raw_events, season="Autumn")

    def test_text_columns_are_stripped(self, raw_events):
        cleaned = clean_events(raw_events, season=None)
        for column in ("Team", "NOC", "Sport", "Event"):
            values = cleaned[column].dropna()
            assert (values == values.str.strip()).all()

    def test_unexpected_medal_values_become_null(self):
        frame = pd.DataFrame(
            {column: ["x"] for column in EVENT_COLUMNS} | {"Year": [2000], "Season": ["Summer"]}
        )
        frame["Medal"] = ["Platinum"]
        assert clean_events(frame, season="Summer")["Medal"].isna().all()

    def test_medal_case_is_normalised(self):
        frame = pd.DataFrame(
            {column: ["x"] for column in EVENT_COLUMNS} | {"Year": [2000], "Season": ["Summer"]}
        )
        frame["Medal"] = ["gOLD"]
        assert clean_events(frame, season="Summer")["Medal"].iloc[0] == "Gold"

    def test_cleaning_never_adds_rows(self, raw_events):
        assert len(clean_events(raw_events, season=None)) <= len(raw_events)

    def test_medal_rows_returns_only_medallists(self, summer):
        assert medal_rows(summer)["Medal"].notna().all()


class TestNumericIntegrity:
    def test_no_infinite_values_in_numeric_columns(self, raw_events):
        numeric = raw_events.select_dtypes(include=[np.number])
        assert not np.isinf(numeric.to_numpy(dtype="float64", na_value=0.0)).any()

    def test_athlete_ids_are_integers(self, raw_events):
        assert pd.api.types.is_integer_dtype(raw_events["ID"])

    def test_years_are_integers(self, raw_events):
        assert pd.api.types.is_integer_dtype(raw_events["Year"])

    def test_the_same_athlete_id_maps_to_one_name(self, raw_events):
        names_per_id = raw_events.groupby("ID")["Name"].nunique()
        assert (names_per_id == 1).all()
