"""Add completed status to applications

Revision ID: adcf846f984c
Revises: 756e668c8911
Create Date: 2025-01-18 22:02:37.871973

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'adcf846f984c'
down_revision = '756e668c8911'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.drop_column('completed_at')
        batch_op.drop_column('completed')

    # ### end Alembic commands ###