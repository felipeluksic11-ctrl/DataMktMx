"""Initial schema — portals, scrape_jobs, raw_listings, clean_listings, export_batches

Revision ID: 001
Revises: None
Create Date: 2026-03-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.execute("CREATE SCHEMA IF NOT EXISTS clean")
    op.execute("CREATE SCHEMA IF NOT EXISTS export")

    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- portals ---
    op.create_table(
        "portals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("scraper_module", sa.String(100), nullable=False),
        sa.Column("avg_listings", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- scrape_jobs ---
    op.create_table(
        "scrape_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_scraped", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_new", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_updated", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_errors", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- raw.raw_listings ---
    op.create_table(
        "raw_listings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scrape_job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("scrape_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        # Identifiers
        sa.Column("url_listing", sa.Text, nullable=True),
        sa.Column("internal_code", sa.String(100), nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        # Classification
        sa.Column("operation", sa.String(20), nullable=True),  # venta | renta | vacacional
        sa.Column("property_type", sa.String(50), nullable=True),
        # Price
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("maintenance_fee", sa.Float, nullable=True),
        # Location
        sa.Column("street_and_number", sa.Text, nullable=True),
        sa.Column("neighborhood", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("municipality", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("country", sa.String(50), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=True),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=True),
        # Media
        sa.Column("video_url", sa.Text, nullable=True),
        sa.Column("tour_360_url", sa.Text, nullable=True),
        sa.Column("images_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        # Dimensions
        sa.Column("land_m2", sa.Float, nullable=True),
        sa.Column("construction_m2", sa.Float, nullable=True),
        # Age
        sa.Column("antiquity", sa.String(50), nullable=True),
        sa.Column("construction_years", sa.Integer, nullable=True),
        # Rooms
        sa.Column("bedrooms", sa.Integer, nullable=True),
        sa.Column("bathrooms", sa.Integer, nullable=True),
        sa.Column("half_bathrooms", sa.Integer, nullable=True),
        sa.Column("parking_spaces", sa.Integer, nullable=True),
        # Features (JSONB arrays)
        sa.Column("extra_rooms", postgresql.JSONB, nullable=True),
        sa.Column("services", postgresql.JSONB, nullable=True),
        sa.Column("amenities", postgresql.JSONB, nullable=True),
        sa.Column("exteriors", postgresql.JSONB, nullable=True),
        sa.Column("extras", postgresql.JSONB, nullable=True),
        # Condition
        sa.Column("conservation_status", sa.String(30), nullable=True),
        sa.Column("has_balcony", sa.Boolean, nullable=True),
        sa.Column("has_elevator", sa.Boolean, nullable=True),
        sa.Column("has_storage", sa.Boolean, nullable=True),
        sa.Column("built_levels", sa.Integer, nullable=True),
        sa.Column("minimum_stay", sa.Integer, nullable=True),
        sa.Column("availability", sa.String(100), nullable=True),
        # Raw
        sa.Column("raw_json", postgresql.JSONB, nullable=True),
        # Timestamps
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="raw",
    )

    op.create_index("ix_raw_portal_extid", "raw_listings", ["portal_id", "external_id"], unique=True, schema="raw")
    op.create_index("ix_raw_location", "raw_listings", ["state", "city", "municipality", "neighborhood"], schema="raw")
    op.create_index("ix_raw_operation_type", "raw_listings", ["operation", "property_type"], schema="raw")

    # --- clean.clean_listings ---
    op.create_table(
        "clean_listings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("raw_listing_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("raw.raw_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dedup_cluster_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("property_type", sa.String(50), nullable=False),
        sa.Column("listing_type", sa.String(10), nullable=False),
        sa.Column("price_mxn", sa.Float, nullable=True),
        sa.Column("price_usd", sa.Float, nullable=True),
        sa.Column("state_code", sa.String(5), nullable=True),
        sa.Column("state_name", sa.String(100), nullable=True),
        sa.Column("city_norm", sa.String(100), nullable=True),
        sa.Column("colony_norm", sa.String(200), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=True),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("bedrooms", sa.Integer, nullable=True),
        sa.Column("bathrooms", sa.Float, nullable=True),
        sa.Column("parking_spaces", sa.Integer, nullable=True),
        sa.Column("construction_m2", sa.Float, nullable=True),
        sa.Column("land_m2", sa.Float, nullable=True),
        sa.Column("price_per_m2", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("completeness", sa.Float, nullable=True),
        sa.Column("source_count", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("amenities", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="clean",
    )

    op.create_index("ix_clean_location", "clean_listings", ["state_code", "city_norm", "colony_norm"], schema="clean")
    op.create_index("ix_clean_type_price", "clean_listings", ["property_type", "listing_type", "price_mxn"], schema="clean")

    # --- export.export_batches ---
    op.create_table(
        "export_batches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_listings", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("s3_key", sa.Text, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("stats", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="export",
    )

    # Trigger to update last_seen_at on raw_listings
    op.execute("""
        CREATE OR REPLACE FUNCTION raw.update_last_seen()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_seen_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_raw_listings_last_seen
        BEFORE UPDATE ON raw.raw_listings
        FOR EACH ROW
        EXECUTE FUNCTION raw.update_last_seen();
    """)

    # Trigger to update updated_at on portals
    op.execute("""
        CREATE OR REPLACE FUNCTION public.update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_portals_updated_at
        BEFORE UPDATE ON portals
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at();
    """)

    op.execute("""
        CREATE TRIGGER trg_clean_listings_updated_at
        BEFORE UPDATE ON clean.clean_listings
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_clean_listings_updated_at ON clean.clean_listings")
    op.execute("DROP TRIGGER IF EXISTS trg_portals_updated_at ON portals")
    op.execute("DROP TRIGGER IF EXISTS trg_raw_listings_last_seen ON raw.raw_listings")
    op.execute("DROP FUNCTION IF EXISTS public.update_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS raw.update_last_seen()")

    op.drop_table("export_batches", schema="export")
    op.drop_table("clean_listings", schema="clean")
    op.drop_table("raw_listings", schema="raw")
    op.drop_table("scrape_jobs")
    op.drop_table("portals")
