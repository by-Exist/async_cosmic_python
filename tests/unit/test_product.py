from datetime import date, timedelta
from typing import cast

from allocation.domain.messages import events
from allocation.domain.models import Batch, OrderLine, Product
from allocation.service.message_bus import MessageCatcher

today = date.today()
tomorrow = today + timedelta(days=1)
later = tomorrow + timedelta(days=10)


def test_prefers_warehouse_batches_to_shipments():
    in_stock_batch = Batch(
        reference="in-stock-batch", sku="RETRO-CLOCK", purchased_quantity=100, eta=None
    )
    shipment_batch = Batch(
        reference="shipment-batch",
        sku="RETRO-CLOCK",
        purchased_quantity=100,
        eta=tomorrow,
    )
    product = Product(sku="RETRO-CLOCK", batches=[in_stock_batch, shipment_batch])
    line = OrderLine(order_id="oref", sku="RETRO-CLOCK", qty=10)
    with MessageCatcher():
        product.allocate(line)
    assert in_stock_batch.available_quantity == 90
    assert shipment_batch.available_quantity == 100


def test_prefers_earlier_batches():
    earliest = Batch(
        reference="speedy-batch",
        sku="MINIMALIST-SPOON",
        purchased_quantity=100,
        eta=today,
    )
    medium = Batch(
        reference="normal-batch",
        sku="MINIMALIST-SPOON",
        purchased_quantity=100,
        eta=tomorrow,
    )
    latest = Batch(
        reference="slow-batch",
        sku="MINIMALIST-SPOON",
        purchased_quantity=100,
        eta=later,
    )
    product = Product(sku="MINIMALIST-SPOON", batches=[medium, earliest, latest])
    line = OrderLine(order_id="order1", sku="MINIMALIST-SPOON", qty=10)

    with MessageCatcher():
        product.allocate(line)

    assert earliest.available_quantity == 90
    assert medium.available_quantity == 100
    assert latest.available_quantity == 100


def test_returns_allocated_batch_ref():
    in_stock_batch = Batch(
        reference="in-stock-batch-ref",
        sku="HIGHBROW-POSTER",
        purchased_quantity=100,
        eta=None,
    )
    shipment_batch = Batch(
        reference="shipment-batch-ref",
        sku="HIGHBROW-POSTER",
        purchased_quantity=100,
        eta=tomorrow,
    )
    line = OrderLine(order_id="oref", sku="HIGHBROW-POSTER", qty=10)
    product = Product(sku="HIGHBROW-POSTER", batches=[in_stock_batch, shipment_batch])
    with MessageCatcher():
        allocation = product.allocate(line)
    assert allocation == in_stock_batch.reference


def test_outputs_allocated_event():
    batch = Batch(
        reference="batchref", sku="RETRO-LAMPSHADE", purchased_quantity=100, eta=None
    )
    line = OrderLine(order_id="oref", sku="RETRO-LAMPSHADE", qty=10)
    product = Product(sku="RETRO-LAMPSHADE", batches=[batch])
    with MessageCatcher() as message_catcher:
        product.allocate(line)
    allocated_event = message_catcher.issued_messages.pop()
    allocated_event = cast(events.Allocated, allocated_event)
    assert isinstance(allocated_event, events.Allocated)
    assert allocated_event.aggregate_id == product.sku
    assert allocated_event.order_id == line.order_id
    assert allocated_event.sku == product.sku
    assert allocated_event.qty == line.qty
    assert allocated_event.batchref == batch.reference


def test_records_out_of_stock_event_if_cannot_allocate():
    batch = Batch(
        reference="batch1", sku="SMALL-FORK", purchased_quantity=10, eta=today
    )
    product = Product(sku="SMALL-FORK", batches=[batch])
    with MessageCatcher() as message_catcher:
        product.allocate(OrderLine(order_id="order1", sku="SMALL-FORK", qty=10))
        allocation = product.allocate(
            OrderLine(order_id="order2", sku="SMALL-FORK", qty=1)
        )
    assert allocation is None
    out_of_stock_event = next(
        event
        for event in message_catcher.issued_messages
        if isinstance(event, events.OutOfStock)
    )
    assert out_of_stock_event.sku == "SMALL-FORK"


def test_increments_version_number():
    line = OrderLine(order_id="oref", sku="SCANDI-PEN", qty=10)
    product = Product(
        sku="SCANDI-PEN",
        batches=[
            Batch(reference="b1", sku="SCANDI-PEN", purchased_quantity=100, eta=None)
        ],
    )
    product.version_number = 7
    with MessageCatcher():
        product.allocate(line)
    assert product.version_number == 8
