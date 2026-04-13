"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # system_sources
    op.create_table(
        "system_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("collector_type", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_collected_at", sa.DateTime(timezone=True)),
        sa.Column("last_collected_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan", sa.String(20), server_default="free"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True)),
        sa.Column("max_keywords", sa.Integer(), server_default="3"),
        sa.Column("max_custom_sources", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("role", sa.String(20), server_default="member"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("must_change_password", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # bid_notices
    op.create_table(
        "bid_notices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("system_sources.id"), nullable=False),
        sa.Column("bid_no", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("organization", sa.String(), server_default=""),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String(), server_default="ongoing"),
        sa.Column("url", sa.String(), server_default=""),
        sa.Column("detail_url", sa.String(), server_default=""),
        sa.Column("content", sa.Text(), server_default=""),
        sa.Column("budget", sa.BigInteger()),
        sa.Column("region", sa.String(), server_default=""),
        sa.Column("category", sa.String(), server_default=""),
        sa.Column("attachments", postgresql.JSONB()),
        sa.Column("extra", postgresql.JSONB()),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_bid_notices_source_bid_no", "bid_notices", ["source_id", "bid_no"], unique=True)
    op.create_index("ix_bid_notices_dates", "bid_notices", ["start_date", "end_date"])
    op.create_index("ix_bid_notices_status", "bid_notices", ["status"])
    # FTS index
    op.execute(
        "CREATE INDEX ix_bid_notices_fts ON bid_notices "
        "USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))"
    )

    # tenant_keywords
    op.create_table(
        "tenant_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("keyword", sa.String(), nullable=False),
        sa.Column("keyword_group", sa.String()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_tenant_keyword", "tenant_keywords", ["tenant_id", "keyword"], unique=True)

    # tenant_tags
    op.create_table(
        "tenant_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("notice_type", sa.String(), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("tagged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("memo", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_tenant_tag_notice", "tenant_tags", ["tenant_id", "notice_type", "notice_id"], unique=True)

    # scraper_registry
    op.create_table(
        "scraper_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("url_hash", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scraper_config", postgresql.JSONB()),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("analysis_log", sa.Text()),
        sa.Column("subscriber_count", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_collected_at", sa.DateTime(timezone=True)),
        sa.Column("last_collected_count", sa.Integer()),
        sa.Column("created_by_tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tenant_source_subscriptions
    op.create_table(
        "tenant_source_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("scraper_id", sa.Integer(), sa.ForeignKey("scraper_registry.id"), nullable=False),
        sa.Column("custom_name", sa.String()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_tenant_scraper", "tenant_source_subscriptions", ["tenant_id", "scraper_id"], unique=True)

    # scraped_notices
    op.create_table(
        "scraped_notices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scraper_id", sa.Integer(), sa.ForeignKey("scraper_registry.id"), nullable=False),
        sa.Column("bid_no", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("organization", sa.String(), server_default=""),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String()),
        sa.Column("url", sa.String(), server_default=""),
        sa.Column("detail_url", sa.String(), server_default=""),
        sa.Column("content", sa.Text(), server_default=""),
        sa.Column("budget", sa.BigInteger()),
        sa.Column("region", sa.String(), server_default=""),
        sa.Column("attachments", postgresql.JSONB()),
        sa.Column("extra", postgresql.JSONB()),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_scraped_notice", "scraped_notices", ["scraper_id", "bid_no"], unique=True)
    op.create_index("ix_scraped_scraper_date", "scraped_notices", ["scraper_id", "start_date"])
    # FTS index
    op.execute(
        "CREATE INDEX ix_scraped_notices_fts ON scraped_notices "
        "USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))"
    )

    # tenant_profiles
    op.create_table(
        "tenant_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("company_name", sa.String()),
        sa.Column("industry", sa.String()),
        sa.Column("size", sa.String()),
        sa.Column("region", sa.String()),
        sa.Column("business_areas", postgresql.ARRAY(sa.String())),
        sa.Column("competency_keywords", postgresql.ARRAY(sa.String())),
        sa.Column("min_budget", sa.BigInteger()),
        sa.Column("max_budget", sa.BigInteger()),
        sa.Column("preferred_org_types", postgresql.ARRAY(sa.String())),
        sa.Column("detail_profile", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tenant_matches
    op.create_table(
        "tenant_matches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("notice_type", sa.String(), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("match_reason", sa.Text()),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_notified", sa.Boolean(), server_default="false"),
    )
    op.create_index("uq_tenant_match", "tenant_matches", ["tenant_id", "notice_type", "notice_id"], unique=True)

    # subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("billing_key", sa.String()),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # notification_settings
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default="true"),
        sa.Column("kakao_enabled", sa.Boolean(), server_default="false"),
        sa.Column("kakao_phone", sa.String()),
        sa.Column("notify_new_match", sa.Boolean(), server_default="true"),
        sa.Column("notify_new_notices", sa.Boolean(), server_default="true"),
        sa.Column("notify_deadline", sa.Boolean(), server_default="true"),
        sa.Column("quiet_hours_start", sa.Time()),
        sa.Column("quiet_hours_end", sa.Time()),
    )

    # Seed system_sources
    op.execute(
        "INSERT INTO system_sources (name, collector_type) VALUES "
        "('나라장터', 'nara'), "
        "('K-Startup', 'kstartup'), "
        "('기업마당', 'bizinfo'), "
        "('보조금24', 'subsidy24'), "
        "('중소벤처기업부', 'smes')"
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
    op.drop_table("subscriptions")
    op.drop_table("tenant_matches")
    op.drop_table("tenant_profiles")
    op.drop_table("scraped_notices")
    op.drop_table("tenant_source_subscriptions")
    op.drop_table("scraper_registry")
    op.drop_table("tenant_tags")
    op.drop_table("tenant_keywords")
    op.drop_table("bid_notices")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("system_sources")
