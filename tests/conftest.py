from pathlib import Path

import pytest

from olympics.hosting import host_country_by_games
from olympics.loading import clean_events, load_events, load_noc, medal_rows
from olympics.medals import assign_final_noc, one_medal_per_event

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def raw_events():
    return load_events(FIXTURES / "athlete_events_sample.csv")


@pytest.fixture(scope="session")
def noc():
    return load_noc(FIXTURES / "noc_regions.csv")


@pytest.fixture(scope="session")
def summer(raw_events):
    return clean_events(raw_events, season="Summer")


@pytest.fixture(scope="session")
def deduplicated(summer, noc):
    return one_medal_per_event(assign_final_noc(medal_rows(summer), noc))


@pytest.fixture(scope="session")
def resolved_hosts(raw_events):
    return host_country_by_games(raw_events)


@pytest.fixture(scope="session")
def both_seasons_dedup(raw_events, noc):
    both = clean_events(raw_events, season=None)
    return one_medal_per_event(assign_final_noc(medal_rows(both), noc))
