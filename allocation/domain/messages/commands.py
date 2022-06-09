from datetime import date
from typing import Optional

from .base import Command


class Allocate(Command):
    order_id: str
    sku: str
    qty: int


class CreateBatch(Command):
    ref: str
    sku: str
    qty: int
    eta: Optional[date] = None


class ChangeBatchQuantity(Command):
    ref: str
    qty: int
