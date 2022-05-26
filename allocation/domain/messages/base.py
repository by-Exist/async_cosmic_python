from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydamain.domain.messages import Message as PydamainMessage, field  # type: ignore


class Message(PydamainMessage):
    uid: UUID = field(default_factory=uuid4)
    create_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Command(Message):
    ...


class Event(Message):
    AGGREGATE_TYPE: str = field(init=False)
    aggregate_id: str