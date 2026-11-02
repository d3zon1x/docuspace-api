"""Baseline empty schema revision.

Revision ID: 0001_baseline
Revises: None
Create Date: 2026-11-02 00:00:00.000000
"""

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Baseline upgrade (domain tables will be added in the next phase)."""


def downgrade() -> None:
    """Baseline downgrade."""
