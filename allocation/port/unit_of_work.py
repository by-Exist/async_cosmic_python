from typing import Protocol

from pydamain import port  # type: ignore

from .repository import ProductRepositoryProtocol
from .outbox import OutboxProtocol


class UnitOfWorkProtocol(port.UnitOfWork, Protocol):

    products: ProductRepositoryProtocol
    _outbox: OutboxProtocol
