from allocation.domain.messages import events
from allocation.service.message_bus import issue

from .bases import Aggregate, field
from .batch import Batch
from .order_line import OrderLine


class Product(Aggregate):

    sku: str
    version_number: int = field(default=0)
    batches: list[Batch]

    def allocate(self, line: OrderLine):
        try:
            batch = next(
                batch for batch in sorted(self.batches) if batch.can_allocate(line)
            )
            batch.allocate(line)
            self.version_number += 1
            issue(
                events.Allocated(
                    aggregate_id=self.sku,
                    order_id=line.order_id,
                    sku=line.sku,
                    qty=line.qty,
                    batchref=batch.reference,
                )
            )
            return batch.reference
        except StopIteration:
            issue(events.OutOfStock(aggregate_id=self.sku, sku=line.sku))

    def change_batch_quantity(self, ref: str, qty: int):
        batch = next(batch for batch in self.batches if batch.reference == ref)
        batch.purchased_quantity = qty
        while batch.available_quantity < 0:
            line = batch.deallocate_one()
            self.version_number += 1
            issue(
                events.Deallocated(
                    aggregate_id=self.sku,
                    order_id=line.order_id,
                    sku=line.sku,
                    qty=line.qty,
                )
            )
