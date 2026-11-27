"""Начальная схема: журнал операций обёртки.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=32), nullable=True),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("response_snippet", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("operation_logs")
