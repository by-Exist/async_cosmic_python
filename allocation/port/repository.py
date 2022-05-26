from typing import Optional, Protocol
from pydamain import port  # type: ignore

from ..domain.models import Product


class ProductRepositoryProtocol(
    port.CollectionOrientedRepository[Product, str], Protocol
):
    async def get(self, sku: str) -> Optional[Product]:
        ...

    async def get_by_batchref(self, batchref: str) -> Optional[Product]:
        ...
