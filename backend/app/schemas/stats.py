"""Learning-history statistics (B-59).

Two count shapes, not one with both keys optional: a memory histogram is keyed
by account, a booking histogram by source, and the UI should not have to guess.
"""

from __future__ import annotations

from pydantic import BaseModel


class AccountCount(BaseModel):
    account: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class LearningStatsResponse(BaseModel):
    memory_count: int
    correction_count: int
    booking_count: int
    memory_distribution: list[AccountCount]
    correction_distribution: list[AccountCount]
    source_distribution: list[SourceCount]
