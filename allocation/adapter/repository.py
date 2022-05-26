from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.models import Product, Batch
from ..port.repository import ProductRepositoryProtocol


@dataclass
class ProductRepository(ProductRepositoryProtocol):

    _session: AsyncSession

    async def add(self, product: Product) -> None:
        self._session.add(product)  # type: ignore

    async def get(self, sku: str) -> Optional[Product]:
        stmt = select(Product).filter(Batch.sku == sku)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_batchref(self, batchref: str) -> Optional[Product]:
        stmt = select(Product).join(Product.batches).filter(Batch.reference == batchref)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def delete(self, product: Product) -> None:
        await self._session.delete(product)  # type: ignore
