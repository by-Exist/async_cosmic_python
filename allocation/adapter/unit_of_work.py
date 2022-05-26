from dataclasses import dataclass, field
from types import TracebackType
from typing import Callable, Optional
from typing_extensions import Self

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from pydamain.service import get_issued_messages  # type: ignore

from ..adapter.repository import ProductRepository
from ..adapter.outbox import Outbox
from ..config import settings
from ..port.unit_of_work import UnitOfWorkProtocol


engine = create_async_engine(
    f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/test",
    echo=settings.DEBUG,
)


@dataclass
class UnitOfWork(UnitOfWorkProtocol):

    SESSION_FACTORY: Callable[[], AsyncSession] = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)  # type: ignore

    _session: AsyncSession = field(init=False)
    products: ProductRepository = field(init=False)
    _outbox: Outbox = field(init=False)

    async def __aenter__(self) -> Self:
        self._session = self.SESSION_FACTORY()
        self.products = ProductRepository(self._session)
        self._outbox = Outbox(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.rollback()

    async def commit(self) -> None:
        issued_messages = get_issued_messages()
        for msg in issued_messages:
            await self._outbox.put(msg)
        await self._session.commit()
        for msg in issued_messages:
            await self._outbox.delete(msg)
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
