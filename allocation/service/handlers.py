from __future__ import annotations

from typing import Any

from allocation import port
from allocation.adapter.email_sender import build_email_message
from allocation.adapter.unit_of_work import SQLAlchemyUnitOfWork
from allocation.domain import models
from allocation.domain.messages import commands, events
from sqlalchemy import text

from . import exceptions


async def add_batch(
    cmd: commands.CreateBatch, uow_factory: type[port.unit_of_work.UnitOfWork], **_: Any
):
    async with uow_factory() as uow:
        product = await uow.products.get(sku=cmd.sku)
        if product is None:
            product = models.Product(sku=cmd.sku, batches=[])
            await uow.products.add(product)
        product.batches.append(
            models.Batch(
                reference=cmd.ref,
                sku=cmd.sku,
                eta=cmd.eta,
                purchased_quantity=cmd.qty,
                _allocations=set(),
            )
        )
        await uow.commit()


async def allocate(
    cmd: commands.Allocate, uow_factory: type[port.unit_of_work.UnitOfWork], **_: Any
):
    line = models.OrderLine(order_id=cmd.order_id, sku=cmd.sku, qty=cmd.qty)
    async with uow_factory() as uow:
        product = await uow.products.get(sku=line.sku)
        if product is None:
            raise exceptions.InvalidSku(f"Invalid sku {line.sku}")
        product.allocate(line)
        await uow.commit()


async def reallocate(
    evt: events.Deallocated, uow_factory: type[port.unit_of_work.UnitOfWork], **_: Any
):
    await allocate(
        commands.Allocate(order_id=evt.order_id, sku=evt.sku, qty=evt.qty),
        uow_factory=uow_factory,
    )


async def change_batch_quantity(
    cmd: commands.ChangeBatchQuantity,
    uow_factory: type[port.unit_of_work.UnitOfWork],
    **_: Any,
):
    async with uow_factory() as uow:
        product = await uow.products.get_by_batchref(batchref=cmd.ref)
        if not product:
            raise exceptions.ProductNotFound(f"Product not found (batchref={cmd.ref})")
        product.change_batch_quantity(ref=cmd.ref, qty=cmd.qty)
        await uow.commit()


async def send_out_of_stock_notification(
    evt: events.OutOfStock, email_sender: port.email_sender.EmailSender, **_: Any
):
    message = build_email_message(
        from_="from@example.com",
        to="to@example.com",
        subject=f"Out of stock for {evt.sku}",
        text_version=f"Out of stock for {evt.sku}",
    )
    await email_sender.send(message)


async def add_allocation_to_read_model(
    evt: events.Allocated, uow_factory: type[SQLAlchemyUnitOfWork], **_: Any
):
    async with uow_factory() as uow:
        await uow._session.execute(  # type: ignore
            text(
                "INSERT INTO allocations_view (order_id, sku, batchref) VALUES (:order_id, :sku, :batchref)"
            ),
            dict(order_id=evt.order_id, sku=evt.sku, batchref=evt.batchref),
        )
        await uow.commit()


async def remove_allocation_from_read_model(
    evt: events.Deallocated, uow_factory: type[SQLAlchemyUnitOfWork], **_: Any
):
    async with uow_factory() as uow:
        await uow._session.execute(  # type: ignore
            text(
                "DELETE FROM allocations_view WHERE order_id = :order_id AND sku = :sku"
            ),
            dict(order_id=evt.order_id, sku=evt.sku),
        )
        await uow.commit()
