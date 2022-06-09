from typing import Optional, Protocol, TypeVar

from allocation.domain.models import Product

A = TypeVar("A")
I_contra = TypeVar("I_contra", contravariant=True)


class CollectionOrientedRepository(Protocol[A, I_contra]):
    async def add(self, _aggregate: A) -> None:
        ...

    async def get(self, _id: I_contra) -> Optional[A]:
        ...

    async def delete(self, _aggregate: A) -> None:
        ...


class PersistenceOrientedRepository(Protocol[A, I_contra]):
    async def save(self, _aggregate: A) -> None:
        ...

    async def get(self, _id: I_contra) -> Optional[A]:
        ...

    async def delete(self, _aggregate: A) -> None:
        ...


class ProductRepository(CollectionOrientedRepository[Product, str], Protocol):
    async def get(self, sku: str) -> Optional[Product]:
        ...

    async def get_by_batchref(self, batchref: str) -> Optional[Product]:
        ...
