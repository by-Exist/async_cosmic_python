from datetime import date
from allocation.domain.models import Batch, OrderLine


def test_allocating_to_a_batch_reduces_the_available_quantity():
    batch = Batch(
        reference="batch-001",
        sku="SMALL-TABLE",
        purchased_quantity=20,
        eta=date.today(),
    )
    line = OrderLine(order_id="order-ref", sku="SMALL-TABLE", qty=2)

    batch.allocate(line)

    assert batch.available_quantity == 18


def make_batch_and_line(sku: str, batch_qty: int, line_qty: int):
    return (
        Batch(
            reference="batch-001",
            sku=sku,
            purchased_quantity=batch_qty,
            eta=date.today(),
        ),
        OrderLine(order_id="order-123", sku=sku, qty=line_qty),
    )


def test_can_allocate_if_available_greater_than_required():
    large_batch, small_line = make_batch_and_line("ELEGANT-LAMP", 20, 2)
    assert large_batch.can_allocate(small_line)


def test_cannot_allocate_if_available_smaller_than_required():
    small_batch, large_line = make_batch_and_line("ELEGANT-LAMP", 2, 20)
    assert small_batch.can_allocate(large_line) is False


def test_can_allocate_if_available_equal_to_required():
    batch, line = make_batch_and_line("ELEGANT-LAMP", 2, 2)
    assert batch.can_allocate(line)


def test_cannot_allocate_if_skus_do_not_match():
    batch = Batch(
        reference="batch-001",
        sku="UNCOMFORTABLE-CHAIR",
        purchased_quantity=100,
        eta=None,
    )
    different_sku_line = OrderLine(
        order_id="order-123", sku="EXPENSIVE-TOASTER", qty=10
    )
    assert batch.can_allocate(different_sku_line) is False


def test_allocation_is_idempotent():
    batch, line = make_batch_and_line("ANGULAR-DESK", 20, 2)
    batch.allocate(line)
    batch.allocate(line)
    assert batch.available_quantity == 18
