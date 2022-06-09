from types import TracebackType
from typing import Optional, Protocol

from allocation.domain.messages.events import Event
from typing_extensions import Self

from . import outbox, repository


class UnitOfWork(Protocol):

    products: repository.ProductRepository
    _outbox: outbox.Outbox[Event]

    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
