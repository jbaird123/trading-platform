"""Utilities for tagging DataFrames with instrument session metadata."""

from __future__ import annotations

from typing import cast

from trading_platform.data.instrument import SessionDefinition

SESSION_ATTR = "_session_definition"
ALIGNED_TO_CLOSE_ATTR = "_aligned_to_close"


def annotate_session(df, session: SessionDefinition | None) -> None:
    """Attach session metadata so downstream resampling can reuse it."""
    if session is None:
        df.attrs.pop(SESSION_ATTR, None)
        return
    df.attrs[SESSION_ATTR] = session


def extract_session(df, fallback: SessionDefinition | None = None) -> SessionDefinition:
    """Retrieve the session definition from a DataFrame."""
    session = cast(SessionDefinition | None, df.attrs.get(SESSION_ATTR))
    if session is not None:
        return session
    if fallback is not None:
        return fallback
    raise ValueError(
        "Session metadata missing from DataFrame; ensure data was loaded via "
        "DataHandler or supply a SessionDefinition explicitly."
    )
