# Alembic Migrations

This directory is the migration home for the target FastAPI modular monolith.

Phase 1 intentionally creates the Alembic foundation only. Java-owned tables are
not redefined here yet; ORM models and migrations should be added when each
domain is migrated from Spring Boot to FastAPI.
