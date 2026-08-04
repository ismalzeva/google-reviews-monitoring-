"""add setup fields to business

Revision ID: 6953bba7ffac
Revises: 373f72bb0e40
Create Date: 2026-08-04 11:19:58.130381

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6953bba7ffac'
down_revision = '373f72bb0e40'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('businesses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('setup_complete', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('setup_progress', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('setup_started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('wow_moment_reached_at', sa.DateTime(timezone=True), nullable=True))

    # Set existing rows to setup_complete=True (they predate trial activation)
    op.execute("UPDATE businesses SET setup_complete = TRUE WHERE setup_complete IS NULL")

    with op.batch_alter_table('businesses', schema=None) as batch_op:
        batch_op.alter_column('setup_complete', nullable=False)


def downgrade():
    with op.batch_alter_table('businesses', schema=None) as batch_op:
        batch_op.drop_column('wow_moment_reached_at')
        batch_op.drop_column('setup_started_at')
        batch_op.drop_column('setup_progress')
        batch_op.drop_column('setup_complete')
