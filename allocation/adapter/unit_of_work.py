from dataclasses import dataclass, field
from types import TracebackType
from typing import Callable, ClassVar, Optional

from allocation import port
from allocation.config import settings
from allocation.domain.messages.events import Event
from allocation.service.message_bus import get_issued_messages
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing_extensions import Self

from .outbox import Outbox
from .repository import ProductRepository

engine = create_async_engine(
    settings.DATABASE_URL, future=True, isolation_level="REPEATABLE READ"
)


@dataclass
class UnitOfWork(port.unit_of_work.UnitOfWork):

    SESSION_FACTORY: ClassVar[Callable[[], AsyncSession]] = sessionmaker(  # type: ignore
        bind=engine, class_=AsyncSession  # type: ignore
    )

    products: ProductRepository = field(init=False)
    _session: AsyncSession = field(init=False)
    _outbox: Outbox = field(init=False)

    async def __aenter__(self) -> Self:
        self._session = await self.SESSION_FACTORY().__aenter__()
        self.products = ProductRepository(self._session)
        self._outbox = Outbox(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self._session.__aexit__(exc_type, exc_value, traceback)

    async def commit(self) -> None:
        issued_messages = get_issued_messages()
        issued_events = (
            message for message in issued_messages if isinstance(message, Event)
        )
        for msg in issued_events:
            await self._outbox.put(msg)
        await self._session.commit()
        for msg in issued_events:
            await self._outbox.delete(msg)
        await self._session.commit()

    async def rollback(self) -> None:
        ...
