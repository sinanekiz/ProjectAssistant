from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260311_0005"
down_revision = "20260311_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO app_settings (key, value, created_at, updated_at)
            VALUES
                ('panel_login_username', 'sekiz', NOW(), NOW()),
                ('panel_login_password', 'qasx7865', NOW(), NOW()),
                ('panel_session_secret', 'projectassistant-panel-session-secret-20260311', NOW(), NOW())
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM app_settings
            WHERE key IN ('panel_login_username', 'panel_login_password', 'panel_session_secret')
              AND (
                (key = 'panel_login_username' AND value = 'sekiz') OR
                (key = 'panel_login_password' AND value = 'qasx7865') OR
                (key = 'panel_session_secret' AND value = 'projectassistant-panel-session-secret-20260311')
              )
            """
        )
    )
