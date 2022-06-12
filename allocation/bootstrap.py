from typing import Any, Awaitable, Callable, Optional, TypeVar

from loguru import logger

from allocation import port
from allocation.adapter.orm import start_mappers
from allocation.domain.messages import commands, events
from allocation.domain.messages.base import Message
from allocation.service import handlers
from allocation.service.message_bus import Handler, MessageBus


M = TypeVar("M", bound=Message)


async def pre_hook(msg: M, handler: Handler[M]):
    ...


async def post_hook(msg: M, handler: Handler[M]):
    logger.debug(f"[Handled {handler.__name__} {type(msg).__name__}] {msg}")


async def exception_hook(msg: M, handler: Handler[M], exc: Exception):
    logger.exception(
        f"[Exception {type(exc)} {handler.__name__} {type(msg).__name__}] {exc} "
    )


def bootstrap(
    *,
    start_orm_mapping: bool,
    uow_class: type[port.unit_of_work.UnitOfWork],
    email_sender: port.email_sender.EmailSender,
    pre_hook: Optional[Callable[[Message, Handler[Any]], Awaitable[None]]] = pre_hook,
    post_hook: Optional[Callable[[Message, Handler[Any]], Awaitable[None]]] = post_hook,
    exception_hook: Optional[
        Callable[[Message, Handler[Any], Exception], Awaitable[None]]
    ] = exception_hook,
) -> MessageBus:

    if start_orm_mapping:
        start_mappers()

    message_bus = MessageBus(
        deps={
            "uow_factory": uow_class,
            "email_sender": email_sender,
        },
        pre_hook=pre_hook,
        post_hook=post_hook,
        exception_hook=exception_hook,
    )

    # Commands
    message_bus.register_handler(commands.Allocate, handlers.allocate)
    message_bus.register_handler(
        commands.ChangeBatchQuantity, handlers.change_batch_quantity
    )
    message_bus.register_handler(commands.CreateBatch, handlers.add_batch)

    # Events
    message_bus.register_handlers(
        events.Allocated, [handlers.add_allocation_to_read_model]
    )
    message_bus.register_handlers(
        events.Deallocated,
        [handlers.remove_allocation_from_read_model, handlers.reallocate],
    )
    message_bus.register_handlers(
        events.OutOfStock, [handlers.send_out_of_stock_notification]
    )

    return message_bus
