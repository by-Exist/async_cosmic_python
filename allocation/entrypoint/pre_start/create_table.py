import asyncio

from allocation.adapter.orm import mapper_registry
from allocation.config import settings
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from tenacity import retry, stop, wait

max_tries = 10
wait_seconds = 6


@retry(
    stop=stop.stop_after_attempt(max_tries),
    wait=wait.wait_fixed(wait_seconds),
)
async def init() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.connect() as conn:
        await conn.run_sync(mapper_registry.metadata.create_all)
        await conn.commit()


async def main() -> None:
    logger.info("Create database table...")
    await init()
    logger.info("Database table created.")


if __name__ == "__main__":
    asyncio.run(main())
