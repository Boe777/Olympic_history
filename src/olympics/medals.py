"""Medal counting.

The source data has one row per athlete per event, so a team of eleven that
wins one gold produces eleven gold rows. Counting those rows directly inflates
team sports enormously. These functions collapse each team result to a single
medal, the way official medal tables do.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .loading import MEDALS

logger = logging.getLogger(__name__)

MIXED_TEAM_CODE = "ZZX"


def assign_final_noc(medals: pd.DataFrame, noc: pd.DataFrame) -> pd.DataFrame:
    """Attach a NOC_final column, bucketing mixed teams under ZZX.

    A row is treated as a mixed team unless either the team name matches the
    NOC's region, or the team name is only ever associated with this one NOC.
    Mixed teams (athletes competing under a combined banner) cannot be credited
    to a single country, so they get their own bucket rather than being
    attributed arbitrarily.
    """
    frame = medals.copy()
    region_by_noc = noc[["NOC", "region"]].dropna().drop_duplicates().set_index("NOC")["region"]

    team_lower = frame["Team"].fillna("").str.strip().str.lower()
    region_lower = frame["NOC"].map(region_by_noc).fillna("").str.strip().str.lower()

    per_team = (
        frame.groupby("Team", dropna=False)["NOC"]
        .agg(noc_count="nunique", first_noc="first")
        .reset_index()
    )
    per_team["single_noc"] = np.where(per_team["noc_count"] == 1, per_team["first_noc"], None)
    frame = frame.merge(per_team[["Team", "noc_count", "single_noc"]], on="Team", how="left")

    # Comparisons on nullable string columns yield pd.NA rather than False, and
    # NA in a boolean mask makes the later np.where ambiguous. Fill first.
    name_matches_region = (
        ((team_lower != "") & (team_lower == region_lower)).fillna(False).to_numpy(bool)
    )
    only_one_noc = (
        ((frame["noc_count"] == 1) & (frame["single_noc"] == frame["NOC"]))
        .fillna(False)
        .to_numpy(bool)
    )

    frame["is_mixed"] = ~(name_matches_region | only_one_noc)
    frame["NOC_final"] = np.where(frame["is_mixed"], MIXED_TEAM_CODE, frame["NOC"])

    logger.info("Flagged %d rows as mixed-team entries", int(frame["is_mixed"].sum()))
    return frame


def one_medal_per_event(medals: pd.DataFrame) -> pd.DataFrame:
    """Collapse each team result to a single medal.

    Deduplicates on Games, Event, NOC_final and Medal, so a rowing eight that
    wins gold counts once rather than eight times.
    """
    return medals.drop_duplicates(subset=["Games", "Event", "NOC_final", "Medal"])


def medal_table(deduplicated: pd.DataFrame, include_mixed: bool = False) -> pd.DataFrame:
    """Build a Gold/Silver/Bronze/Total table indexed by NOC.

    Mixed-team entries are excluded by default: ZZX is not a country, and
    leaving it in the table puts a non-country near the top of a country
    ranking.
    """
    frame = deduplicated
    if not include_mixed:
        frame = frame[frame["NOC_final"] != MIXED_TEAM_CODE]

    table = frame.groupby(["NOC_final", "Medal"]).size().unstack(fill_value=0)

    for medal in MEDALS:
        if medal not in table.columns:
            table[medal] = 0

    table = table[list(MEDALS)]
    table["Total"] = table.sum(axis=1)
    return table.sort_values(by=list(MEDALS), ascending=False)


def medals_by_country_and_sport(deduplicated: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Return a sport-by-NOC medal matrix for the leading medal winners."""
    leaders = medal_table(deduplicated).head(top_n).index
    subset = deduplicated[deduplicated["NOC_final"].isin(leaders)]
    return subset.groupby(["NOC_final", "Sport"]).size().unstack(fill_value=0).reindex(leaders)
