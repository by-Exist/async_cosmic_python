from typing import Protocol
from pydamain import port  # type: ignore

from ..domain.messages.base import Event


class OutboxProtocol(port.Outbox[Event], Protocol):
    ...
