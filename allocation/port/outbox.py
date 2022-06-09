from typing import Iterable, Protocol, TypeVar

E = TypeVar("E")


class Outbox(Protocol[E]):
    async def all(self) -> Iterable[E]:
        ...

    async def put(self, _envelope: E) -> None:
        ...

    async def delete(self, _envelope: E) -> None:
        ...
