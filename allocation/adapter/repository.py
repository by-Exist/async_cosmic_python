from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from allocation import port
from allocation.domain.models import Batch, Product


@dataclass
class ProductRepository(port.repository.ProductRepository):

    _session: AsyncSession

    async def add(self, product: Product) -> None:
        self._session.add(product)  # type: ignore

    async def get(self, sku: str) -> Optional[Product]:
        stmt = select(Product).join(Batch).filter(Batch.sku == sku)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_batchref(self, batchref: str) -> Optional[Product]:
        stmt = select(Product).join(Product.batches).filter(Batch.reference == batchref)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def delete(self, product: Product) -> None:
        await self._session.delete(product)  # type: ignore
