-- Extensions required by the project
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Schema for raw scraping data (never leaves VPS)
CREATE SCHEMA IF NOT EXISTS raw;

-- Schema for cleaned/deduplicated data
CREATE SCHEMA IF NOT EXISTS clean;

-- Schema for export tracking
CREATE SCHEMA IF NOT EXISTS export;
