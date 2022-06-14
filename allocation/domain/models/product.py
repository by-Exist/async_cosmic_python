from .bases import Aggregate, field
from .batch import Batch
from .order_line import OrderLine


class OutOfStockException(Exception):
    ...


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
            return batch.reference
        except StopIteration:
            raise OutOfStockException()

    def change_batch_quantity(self, ref: str, qty: int):
        batch = next(batch for batch in self.batches if batch.reference == ref)
        batch.purchased_quantity = qty
        deallocated_lines: list[OrderLine] = []
        while batch.available_quantity < 0:
            line = batch.deallocate_one()
            deallocated_lines.append(line)
        self.version_number += 1
        return deallocated_lines
