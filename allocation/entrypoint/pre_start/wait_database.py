import asyncio

from allocation.config import settings
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from tenacity import retry, stop, wait

max_tries = 10
wait_seconds = 6


@retry(
    stop=stop.stop_after_attempt(max_tries),
    wait=wait.wait_fixed(wait_seconds),
)
async def init() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        await conn.execute(select(1))


async def main() -> None:
    logger.info("Wait database...")
    await init()
    logger.info("Database is running.")


if __name__ == "__main__":
    asyncio.run(main())
