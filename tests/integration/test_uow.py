import asyncio
from datetime import date

import pytest
from allocation.adapter import unit_of_work
from allocation.domain import models
from allocation.service.message_bus import MessageCatcher
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..random_refs import random_batchref, random_order_id, random_sku

pytestmark = pytest.mark.usefixtures("orm_mapping")


async def insert_batch(
    session: AsyncSession,
    ref: str,
    sku: str,
    qty: int,
    eta: date | None,
    product_version: int = 1,
):
    await session.execute(
        text("INSERT INTO products (sku, version_number) VALUES (:sku, :version)"),
        dict(sku=sku, version=product_version),
    )
    await session.execute(
        text(
            "INSERT INTO batches (reference, sku, _purchased_quantity, eta) VALUES (:ref, :sku, :qty, :eta)"
        ),
        dict(ref=ref, sku=sku, qty=qty, eta=eta),
    )


async def get_allocated_batch_ref(session: AsyncSession, order_id: str, sku: str):
    [[orderlineid]] = await session.execute(
        text("SELECT id FROM order_lines WHERE order_id=:order_id AND sku=:sku"),
        dict(order_id=order_id, sku=sku),
    )
    [[batchref]] = await session.execute(
        text(
            "SELECT b.reference FROM allocations JOIN batches AS b ON batch_id = b.id WHERE orderline_id=:orderlineid"
        ),
        dict(orderlineid=orderlineid),
    )
    return batchref


async def test_uow_can_retrieve_a_batch_and_allocate_to_it(
    database_session: AsyncSession,
    uow_class: type[unit_of_work.SQLAlchemyUnitOfWork],
):
    await insert_batch(database_session, "batch1", "HIPSTER-WORKBENCH", 100, None)
    await database_session.commit()

    with MessageCatcher():
        async with uow_class() as uow:
            product = await uow.products.get(sku="HIPSTER-WORKBENCH")
            assert product
            line = models.OrderLine(order_id="o1", sku="HIPSTER-WORKBENCH", qty=10)
            product.allocate(line)
            await uow.commit()

    batchref = await get_allocated_batch_ref(
        database_session, "o1", "HIPSTER-WORKBENCH"
    )
    assert batchref == "batch1"


async def test_rolls_back_uncommitted_work_by_default(
    database_session: AsyncSession,
    uow_class: type[unit_of_work.SQLAlchemyUnitOfWork],
):
    async with uow_class() as uow:
        await insert_batch(uow._session, "batch1", "MEDIUM-PLINTH", 100, None)  # type: ignore

    rows = list(await database_session.execute(text('SELECT * FROM "batches"')))
    assert rows == []


async def test_rolls_back_on_error(
    database_session: AsyncSession, uow_class: type[unit_of_work.SQLAlchemyUnitOfWork]
):
    class MyException(Exception):
        pass

    with pytest.raises(MyException):
        async with uow_class() as uow:
            await insert_batch(uow._session, "batch1", "LARGE-FORK", 100, None)  # type: ignore
            raise MyException()

    rows = list(await database_session.execute(text('SELECT * FROM "batches"')))
    assert rows == []


async def try_to_allocate(
    order_id: str,
    sku: str,
    exceptions: list[Exception],
    uow_class: type[unit_of_work.SQLAlchemyUnitOfWork],
):
    line = models.OrderLine(order_id=order_id, sku=sku, qty=10)
    try:
        with MessageCatcher():
            async with uow_class() as uow:
                product = await uow.products.get(sku=sku)
                assert product
                product.allocate(line)
                await asyncio.sleep(0.2)
                await uow.commit()
    except Exception as e:
        exceptions.append(e)


async def test_concurrent_updates_to_version_are_not_allowed(
    database_session: AsyncSession, uow_class: type[unit_of_work.SQLAlchemyUnitOfWork]
):
    sku, batch = random_sku(), random_batchref()
    await insert_batch(database_session, batch, sku, 100, eta=None, product_version=1)
    await database_session.commit()

    order1, order2 = random_order_id(1), random_order_id(2)
    exceptions: list[Exception] = []
    await asyncio.gather(
        try_to_allocate(order1, sku, exceptions, uow_class),
        try_to_allocate(order2, sku, exceptions, uow_class),
    )

    [[version]] = await database_session.execute(
        text("SELECT version_number FROM products WHERE sku=:sku"),
        dict(sku=sku),
    )
    assert version == 2
    [exception] = exceptions
    assert "could not serialize access due to concurrent update" in str(exception)

    orders = await database_session.execute(
        text(
            "SELECT order_id FROM allocations"
            " JOIN batches ON allocations.batch_id = batches.id"
            " JOIN order_lines ON allocations.orderline_id = order_lines.id"
            " WHERE order_lines.sku=:sku"
        ),
        dict(sku=sku),
    )
    assert len(orders.all()) == 1
