"""empty message

Revision ID: 23f9adef79ea
Revises: 161cc8ae4819
Create Date: 2017-07-01 22:01:53.727194

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '23f9adef79ea'
down_revision = '161cc8ae4819'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('dataset', sa.Column('meta_latitude', sa.Float(), nullable=True))
    op.add_column('dataset', sa.Column('meta_longitude', sa.Float(), nullable=True))
    op.alter_column('user', 'admin',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('user', 'admin',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=True)
    op.drop_column('dataset', 'meta_longitude')
    op.drop_column('dataset', 'meta_latitude')
    # ### end Alembic commands ###
