from typing import Any, Awaitable, Callable, Optional
from pydamain.service import MessageBus  # type: ignore

from .adapter.email_sender import EmailSender
from .adapter.unit_of_work import UnitOfWork
from .adapter.orm import start_mapping
from .domain.messages import commands, events
from .service.handlers import handlers

from . import port


def bootstrap(
    start_orm_mapping: bool = True,
    uow_factory: type[port.UnitOfWorkProtocol] = UnitOfWork,
    email_sender: port.EmailSender = EmailSender(),
    pre_hook: Optional[Callable[[Any, Any], Awaitable[None]]] = None,
    post_hook: Optional[Callable[[Any, Any], Awaitable[None]]] = None,
) -> MessageBus:

    if start_orm_mapping:
        start_mapping()

    message_bus = MessageBus(
        deps={
            "email_sender": email_sender,
            "uow_factory": uow_factory,
        },
        pre_hook=pre_hook,
        post_hook=post_hook,
    )
    # commands
    message_bus.register(commands.Allocate, handlers.allocate)
    message_bus.register(commands.ChangeBatchQuantity, handlers.change_batch_quantity)
    message_bus.register(commands.CreateBatch, handlers.add_batch)
    # events
    message_bus.register(events.Allocated, (handlers.add_allocation_to_read_model))
    message_bus.register(
        events.Deallocated,
        (handlers.remove_allocation_from_read_model, handlers.reallocate),
    )
    message_bus.register(events.OutOfStock, (handlers.send_out_of_stock_notification))

    return message_bus
