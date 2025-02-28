from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `krun_api` MODIFY COLUMN `method` VARCHAR(7) NOT NULL  COMMENT 'API方式';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `krun_api` MODIFY COLUMN `method` VARCHAR(7) NOT NULL  COMMENT 'API请求方式';"""
