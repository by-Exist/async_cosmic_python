from datetime import date
from typing import TypeVar

import pytest
from allocation import bootstrap
from allocation.adapter import email_sender, unit_of_work
from allocation.domain.messages import commands
from allocation.domain.messages.base import Message
from allocation.service import views
from allocation.service.message_bus import Handler, MessageBus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import clear_mappers

today = date.today()


M = TypeVar("M", bound=Message)


async def exc_hook(message: M, handler: Handler[M], exception: Exception):
    print("Exception : ", message, handler.__name__, exception)


async def post_hook(message: M, handler: Handler[M]):
    print("Handled : ", message, handler.__name__)


@pytest.fixture
def message_bus(uow_class: type[unit_of_work.SQLAlchemyUnitOfWork]):
    bus = bootstrap.bootstrap(
        start_orm_mapping=True,
        uow_class=uow_class,
        email_sender=email_sender.EmailSender(),
        post_hook=post_hook,
        exception_hook=exc_hook,
    )
    yield bus
    clear_mappers()


async def test_allocations_view(
    message_bus: MessageBus, database_session: AsyncSession
):
    await message_bus.handle(
        commands.CreateBatch(ref="sku1batch", sku="sku1", qty=50, eta=None)
    )
    await message_bus.handle(
        commands.CreateBatch(ref="sku2batch", sku="sku2", qty=50, eta=today)
    )
    await message_bus.handle(commands.Allocate(order_id="order1", sku="sku1", qty=20))
    await message_bus.handle(commands.Allocate(order_id="order1", sku="sku2", qty=20))
    await message_bus.handle(
        commands.CreateBatch(ref="sku1batch-later", sku="sku1", qty=50, eta=today)
    )
    await message_bus.handle(
        commands.Allocate(order_id="otherorder", sku="sku1", qty=30)
    )
    await message_bus.handle(
        commands.Allocate(order_id="otherorder", sku="sku2", qty=10)
    )

    assert await views.allocations("order1", database_session) == [
        {"sku": "sku1", "batchref": "sku1batch"},
        {"sku": "sku2", "batchref": "sku2batch"},
    ]


async def test_deallocation(message_bus: MessageBus, database_session: AsyncSession):
    await message_bus.handle(
        commands.CreateBatch(ref="b1", sku="sku1", qty=50, eta=None)
    )
    await message_bus.handle(
        commands.CreateBatch(ref="b2", sku="sku1", qty=50, eta=today)
    )
    await message_bus.handle(commands.Allocate(order_id="o1", sku="sku1", qty=40))

    [allocation] = await views.allocations("o1", database_session)
    assert allocation == {"sku": "sku1", "batchref": "b1"}

    await message_bus.handle(commands.ChangeBatchQuantity(ref="b1", qty=10))

    [allocation] = await views.allocations("o1", database_session)
    assert allocation == {"sku": "sku1", "batchref": "b2"}
