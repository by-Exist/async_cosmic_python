from dataclasses import dataclass
from typing import ClassVar, Iterable
from uuid import UUID

from allocation import port
from allocation.domain.messages import events
from allocation.domain.messages.events import Event
from cattrs.preconf.json import make_converter  # type: ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

converter = make_converter()

converter.register_unstructure_hook(UUID, lambda uuid: uuid.hex)  # type: ignore
converter.register_structure_hook(UUID, lambda hex, _: UUID(hex))


@dataclass
class Envelope:
    id: UUID
    aggregate_type: str
    aggregate_id: str
    type: str
    payload: str


@dataclass
class Outbox(port.outbox.Outbox[Event]):

    EVENT_MAP: ClassVar[dict[str, type[Event]]] = {
        event_type.__name__: event_type
        for event_type in (
            events.Allocated,
            events.Deallocated,
            events.OutOfStock,
        )
    }

    _session: AsyncSession

    async def all(self) -> Iterable[Event]:
        envelope_scalars = await self._session.scalars(select(Envelope))
        envelopes: list[Envelope] = envelope_scalars.all()
        events = (
            converter.loads(envelope.payload, self.EVENT_MAP[envelope.type])  # type: ignore
            for envelope in envelopes
        )
        return events

    async def put(self, event: Event) -> None:
        assert type(event).__name__ in self.EVENT_MAP
        envelope = Envelope(
            id=event.uid,
            aggregate_type=event.AGGREGATE_TYPE,
            aggregate_id=event.aggregate_id,
            type=type(event).__name__,
            payload=converter.dumps(event),  # type: ignore
        )
        self._session.add(envelope)

    async def delete(self, event: Event) -> None:
        envelope = await self._session.get(Envelope, event.uid)
        await self._session.delete(envelope)
