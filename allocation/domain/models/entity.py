from datetime import date
from typing import Any, Optional

from .bases import Entity, field
from .value_object import OrderLine


class Batch(Entity):
    reference: str
    sku: str
    eta: Optional[date]
    _purchased_quantity: int
    _allocations: set[OrderLine] = field(default_factory=set)

    def __repr__(self):
        return f"<Batch {self.reference}>"

    def __eq__(self, other: Any):
        if not isinstance(other, Batch):
            return False
        return other.reference == self.reference

    def __hash__(self):
        return hash(self.reference)

    def __gt__(self, other: Any):
        if not isinstance(other, type(self)):
            raise TypeError(f"{other} is not {type(self).__name__} instance")
        if self.eta is None:
            return False
        if other.eta is None:
            return True
        return self.eta > other.eta

    def allocate(self, line: OrderLine):
        if self.can_allocate(line):
            self._allocations.add(line)

    def deallocate_one(self) -> OrderLine:
        return self._allocations.pop()

    @property
    def allocated_quantity(self) -> int:
        return sum(line.qty for line in self._allocations)

    @property
    def available_quantity(self) -> int:
        return self._purchased_quantity - self.allocated_quantity

    def can_allocate(self, line: OrderLine) -> bool:
        return self.sku == line.sku and self.available_quantity >= line.qty
