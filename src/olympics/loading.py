"""Loading and cleaning of the 120-years-of-Olympic-history dataset.

Every function is pure: it takes a dataframe and returns a new one, so the
analysis can be tested against a small fixture instead of the full 40 MB file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

EVENT_COLUMNS = (
    "ID",
    "Name",
    "Sex",
    "Age",
    "Height",
    "Weight",
    "Team",
    "NOC",
    "Games",
    "Year",
    "Season",
    "City",
    "Sport",
    "Event",
    "Medal",
)
NOC_COLUMNS = ("NOC", "region", "notes")

STRING_COLUMNS = ("Team", "NOC", "Medal", "Games", "Event", "Sport", "Season", "City")
MEDALS = ("Gold", "Silver", "Bronze")
SEASONS = ("Summer", "Winter")

# The dataset covers the first modern Games through Rio.
FIRST_YEAR = 1896
LAST_YEAR = 2016

# Historical names the source file leaves blank or ambiguous. Needed so host
# countries can be matched by name rather than by code.
NOC_REGION_OVERRIDES = {
    "GBR": "Great Britain",
    "FRG": "West Germany",
    "GDR": "East Germany",
    "URS": "Soviet Union",
    "EUN": "Unified Team",
    "SAA": "Saar",
    "YUG": "Yugoslavia",
}


class DatasetError(ValueError):
    """Raised when the input data does not have the expected shape."""


def load_events(path: str | Path) -> pd.DataFrame:
    """Read athlete_events.csv and validate its schema.

    Fails loudly on a malformed file rather than producing a silently wrong
    analysis further down the pipeline.
    """
    frame = pd.read_csv(path)
    missing = set(EVENT_COLUMNS) - set(frame.columns)
    if missing:
        raise DatasetError(f"athlete_events is missing columns: {sorted(missing)}")
    logger.info("Loaded %d event rows from %s", len(frame), path)
    return frame


def load_noc(path: str | Path) -> pd.DataFrame:
    """Read noc_regions.csv, validate it, and apply historical name overrides."""
    frame = pd.read_csv(path)
    missing = {"NOC", "region"} - set(frame.columns)
    if missing:
        raise DatasetError(f"noc_regions is missing columns: {sorted(missing)}")

    frame = frame.copy()
    for code, region in NOC_REGION_OVERRIDES.items():
        frame.loc[frame["NOC"] == code, "region"] = region
    return frame


def clean_events(frame: pd.DataFrame, season: str | None = "Summer") -> pd.DataFrame:
    """Drop duplicates, normalise text columns and optionally filter by season.

    Season defaults to Summer. Summer and Winter are effectively different
    competitions with different participating nations, so mixing them conflates
    two populations. Pass season=None to analyse both together.
    """
    if season is not None and season not in SEASONS:
        raise DatasetError(f"season must be one of {SEASONS} or None, got {season!r}")

    cleaned = frame.drop_duplicates().copy()

    for column in STRING_COLUMNS:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()

    cleaned["Medal"] = cleaned["Medal"].str.title()
    cleaned.loc[~cleaned["Medal"].isin(MEDALS), "Medal"] = pd.NA

    if season is not None:
        cleaned = cleaned[cleaned["Season"] == season]

    logger.info(
        "Cleaned to %d rows (season=%s, dropped %d duplicates)",
        len(cleaned),
        season,
        len(frame) - len(frame.drop_duplicates()),
    )
    return cleaned.reset_index(drop=True)


def medal_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows that recorded a medal."""
    return frame[frame["Medal"].notna()].copy()
