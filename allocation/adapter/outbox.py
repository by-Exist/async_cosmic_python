from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore

from cattrs.preconf.json import make_converter  # type: ignore

from ..domain.messages.base import Event
from ..port.outbox import OutboxProtocol


converter = make_converter()


@dataclass
class Envelope:
    id: UUID
    aggregate_type: str
    aggregate_id: str
    type: str
    payload: str
    timestamp: datetime


@dataclass
class Outbox(OutboxProtocol):

    _session: AsyncSession

    async def put(self, event: Event) -> None:
        envelope = Envelope(
            id=event.uid,
            aggregate_type=event.AGGREGATE_TYPE,
            aggregate_id=event.aggregate_id,
            type=type(event).__name__,
            payload=converter.dumps(event),  # type: ignore
            timestamp=event.create_time,
        )
        self._session.add(envelope)

    async def delete(self, event: Event) -> None:
        await self._session.delete(event)
