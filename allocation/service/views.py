from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def allocations(order_id: str, session: AsyncSession):
    async with session.begin():
        results = await session.execute(
            text(
                "SELECT sku, batchref FROM allocations_view WHERE order_id = :order_id"
            ),
            {"order_id": order_id},
        )
    return [row._mapping for row in results.all()]
