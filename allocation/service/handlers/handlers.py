from __future__ import annotations
from typing import Any
from allocation.domain.messages import commands, events
from allocation.domain import models


from ...adapter.unit_of_work import UnitOfWork
from ...adapter.email_sender import build_email_message
from ...port.unit_of_work import UnitOfWorkProtocol
from ...port.email_sender import EmailSender

from .. import exceptions


async def add_batch(
    cmd: commands.CreateBatch, uow_factory: type[UnitOfWorkProtocol], **_: Any
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
                _purchased_quantity=cmd.qty,
                _allocations=set(),
            )
        )
        await uow.commit()


async def allocate(
    cmd: commands.Allocate, uow_factory: type[UnitOfWorkProtocol], **_: Any
):
    line = models.OrderLine(order_id=cmd.order_id, sku=cmd.sku, qty=cmd.qty)
    async with uow_factory() as uow:
        product = await uow.products.get(sku=line.sku)
        if product is None:
            raise exceptions.InvalidSku(f"Invalid sku {line.sku}")
        product.allocate(line)
        await uow.commit()


async def reallocate(
    evt: events.Deallocated, uow_factory: type[UnitOfWorkProtocol], **_: Any
):
    await allocate(
        commands.Allocate(order_id=evt.order_id, sku=evt.sku, qty=evt.qty),
        uow_factory=uow_factory,
    )


async def change_batch_quantity(
    cmd: commands.ChangeBatchQuantity, uow_factory: type[UnitOfWorkProtocol], **_: Any
):
    async with uow_factory() as uow:
        product = await uow.products.get_by_batchref(batchref=cmd.ref)
        if not product:
            raise exceptions.ProductNotFound(f"Product not found (batchref={cmd.ref})")
        product.change_batch_quantity(ref=cmd.ref, qty=cmd.qty)
        await uow.commit()


async def send_out_of_stock_notification(
    evt: events.OutOfStock, email_sender: EmailSender, **_: Any
):
    message = build_email_message(
        from_="from@example.com",
        to="to@example.com",
        subject=f"Out of stock for {evt.sku}",
        text_version=f"Out of stock for {evt.sku}",
    )
    await email_sender.send(message)


async def add_allocation_to_read_model(
    evt: events.Allocated, uow_factory: type[UnitOfWork], **_: Any
):
    async with uow_factory() as uow:
        await uow._session.execute(  # type: ignore
            "INSERT INTO allocations_view (orderid, sku, batchref) VALUES (:orderid, :sku, :batchref)",  # type: ignore
            dict(orderid=evt.order_id, sku=evt.sku, batchref=evt.batchref),
        )
        await uow.commit()


async def remove_allocation_from_read_model(
    evt: events.Deallocated, uow_factory: type[UnitOfWork], **_: Any
):
    async with uow_factory() as uow:
        await uow._session.execute(  # type: ignore
            "DELETE FROM allocations_view WHERE orderid = :orderid AND sku = :sku",  # type: ignore
            dict(orderid=evt.order_id, sku=evt.sku),
        )
        await uow.commit()
