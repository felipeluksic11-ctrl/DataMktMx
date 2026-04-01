"""Widen varchar columns to handle long values from different portals.

Revision ID: 003
Revises: 002
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Propiedades.com puts full addresses in street_and_number and municipality
    op.alter_column("raw_listings", "municipality", type_=sa.String(255), schema="raw")
    op.alter_column("raw_listings", "neighborhood", type_=sa.String(255), schema="raw")
    op.alter_column("raw_listings", "city", type_=sa.String(255), schema="raw")
    op.alter_column("raw_listings", "state", type_=sa.String(255), schema="raw")
    op.alter_column("raw_listings", "country", type_=sa.String(100), schema="raw")
    op.alter_column("raw_listings", "internal_code", type_=sa.String(255), schema="raw")
    op.alter_column("raw_listings", "availability", type_=sa.String(255), schema="raw")


def downgrade() -> None:
    op.alter_column("raw_listings", "municipality", type_=sa.String(100), schema="raw")
    op.alter_column("raw_listings", "neighborhood", type_=sa.String(200), schema="raw")
    op.alter_column("raw_listings", "city", type_=sa.String(100), schema="raw")
    op.alter_column("raw_listings", "state", type_=sa.String(100), schema="raw")
    op.alter_column("raw_listings", "country", type_=sa.String(50), schema="raw")
    op.alter_column("raw_listings", "internal_code", type_=sa.String(100), schema="raw")
    op.alter_column("raw_listings", "availability", type_=sa.String(100), schema="raw")
