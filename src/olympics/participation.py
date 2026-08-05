"""Female participation over time, by sport and by country.

Counts are of distinct athletes, not of rows: an athlete entered in four events
is one participant, not four.
"""

from __future__ import annotations

import pandas as pd


def participation_by_year(events: pd.DataFrame) -> pd.DataFrame:
    """Return distinct athlete counts per year and the female share.

    female_pct is expressed as a percentage of all athletes that year.
    """
    counts = (
        events.groupby(["Year", "Sex"])["ID"]
        .nunique()
        .unstack(fill_value=0)
        .rename(columns={"F": "female", "M": "male"})
    )

    for column in ("female", "male"):
        if column not in counts.columns:
            counts[column] = 0

    counts["total"] = counts["female"] + counts["male"]
    counts["female_pct"] = (counts["female"] / counts["total"] * 100).where(
        counts["total"] > 0, 0.0
    )
    return counts[["female", "male", "total", "female_pct"]].sort_index()


def first_female_year_by_sport(events: pd.DataFrame) -> pd.Series:
    """Return the first year each sport recorded a female entrant.

    Sports that have never had a female entrant are absent from the result
    rather than present with a null.
    """
    female = events[events["Sex"] == "F"]
    return female.groupby("Sport")["Year"].min().sort_values()


def top_countries_by_female_athletes(events: pd.DataFrame, top_n: int = 10) -> pd.Series:
    """Return the countries with the most distinct female athletes."""
    female = events[events["Sex"] == "F"]
    return female.groupby("NOC")["ID"].nunique().sort_values(ascending=False).head(top_n)
