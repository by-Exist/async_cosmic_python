from typing import Optional

from pydamain.service import issue  # type: ignore

from .bases import Aggregate
from .entity import Batch
from .value_object import OrderLine

from ..messages.events import Allocated, Deallocated, OutOfStock


class Product(Aggregate):

    sku: str
    batches: list[Batch]

    def allocate(self, line: OrderLine) -> Optional[str]:
        try:
            batch = next(
                batch for batch in sorted(self.batches) if batch.can_allocate(line)
            )
            batch.allocate(line)
            self.version_number += 1
            issue(
                Allocated(
                    aggregate_id=self.sku,
                    order_id=line.order_id,
                    sku=line.sku,
                    qty=line.qty,
                    batchref=batch.reference,
                )
            )
            return batch.reference
        except StopIteration:
            issue(OutOfStock(aggregate_id=self.sku, sku=line.sku))

    def change_batch_quantity(self, ref: str, qty: int):
        batch = next(batch for batch in self.batches if batch.reference == ref)
        batch._purchased_quantity = qty  # type: ignore
        while batch.available_quantity < 0:
            line = batch.deallocate_one()
            issue(
                Deallocated(
                    aggregate_id=self.sku,
                    order_id=line.order_id,
                    sku=line.sku,
                    qty=line.qty,
                )
            )
