from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `krun_user` ALTER COLUMN `state` SET DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `krun_user` ALTER COLUMN `state` SET DEFAULT 2;"""
