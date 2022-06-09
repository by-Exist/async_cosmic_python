import asyncio
from contextvars import ContextVar, Token
from dataclasses import field
from types import TracebackType
from typing import (
    Any,
    Awaitable,
    Callable,
    ContextManager,
    Iterable,
    Literal,
    Optional,
    Protocol,
    TypeVar,
    overload,
)

from allocation.domain.messages.base import Message
from typing_extensions import Self

# Handler
M_contra = TypeVar("M_contra", bound=Message, contravariant=True)


class _Handler(Protocol[M_contra]):

    __name__: str

    async def __call__(self, _msg: M_contra, **_: Any) -> None:
        ...


Handler = _Handler


# Message Catch Context
_messages_context_var: ContextVar[set[Message]] = ContextVar("messages")


class MessageCatcher(ContextManager["MessageCatcher"]):

    _token: Token[set[Message]] = field(init=False)
    issued_messages: set[Message] = field(init=False)

    def __enter__(self) -> Self:
        self._token = _messages_context_var.set(set())
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.issued_messages = _messages_context_var.get()
        _messages_context_var.reset(self._token)


def issue(message: Message):
    _messages_context_var.get().add(message)


def get_issued_messages():
    return _messages_context_var.get()


# Handle methods
M = TypeVar("M", bound=Message)


async def handle(
    message: M,
    handler: Handler[M],
    deps: dict[str, Any],
    pre_hook: Optional[Callable[[Message, Handler[M]], Awaitable[None]]] = None,
    post_hook: Optional[Callable[[Message, Handler[M]], Awaitable[None]]] = None,
    exception_hook: Optional[
        Callable[[Message, Handler[M], Exception], Awaitable[None]]
    ] = None,
):
    try:
        if pre_hook:
            await pre_hook(message, handler)
        await handler(message, **deps)
        if post_hook:
            await post_hook(message, handler)
        return
    except Exception as e:
        if exception_hook:
            await exception_hook(message, handler, e)
        raise e


async def handle_parallel(
    message: M,
    handlers: Iterable[Handler[M]],
    deps: dict[str, Any],
    pre_hook: Optional[Callable[[Message, Handler[M]], Awaitable[None]]] = None,
    post_hook: Optional[Callable[[Message, Handler[M]], Awaitable[None]]] = None,
    exception_hook: Optional[
        Callable[[Message, Handler[M], Exception], Awaitable[None]]
    ] = None,
):
    coros = (
        handle(message, handler, deps, pre_hook, post_hook, exception_hook)
        for handler in handlers
    )
    return await asyncio.gather(*coros, return_exceptions=True)


# Message Bus
class MessageBus:
    def __init__(
        self,
        *,
        deps: dict[str, Any],
        pre_hook: Optional[
            Callable[[Message, Handler[Message]], Awaitable[None]]
        ] = None,
        post_hook: Optional[
            Callable[[Message, Handler[Message]], Awaitable[None]]
        ] = None,
        exception_hook: Optional[
            Callable[[Message, Handler[Message], Exception], Awaitable[None]]
        ] = None,
    ) -> None:
        self._deps: dict[str, Any] = deps
        self._handler_map: dict[type[Message], Handler[Any]] = {}
        self._handlers_map: dict[type[Message], Iterable[Handler[Any]]] = {}
        self._pre_hook = pre_hook
        self._post_hook = post_hook
        self._exception_hook = exception_hook

    def register_handler(
        self,
        message_type: type[M],
        handler: Handler[M],
    ):
        self._handler_map[message_type] = handler

    def register_handlers(
        self,
        message_type: type[Message],
        handlers: Iterable[Handler[M]],
    ):
        self._handlers_map[message_type] = handlers

    @overload
    async def handle(self, message: Message):
        ...

    @overload
    async def handle(
        self, message: Message, return_hooked_task: Literal[True] = True
    ) -> asyncio.Future[list[Any]]:
        ...

    async def handle(self, message: Message, return_hooked_task: bool = False):
        hooked = await asyncio.create_task(self._handle_once(message))
        coros = (self.handle(msg) for msg in hooked)
        hooked_task = asyncio.gather(*coros, return_exceptions=True)
        if return_hooked_task:
            return hooked_task
        await hooked_task

    async def _handle_once(self, message: Message):
        with MessageCatcher() as message_catcher:
            if handler := self._handler_map.get(type(message), None):
                await handle(
                    message,
                    handler,
                    self._deps,
                    self._pre_hook,
                    self._post_hook,
                    self._exception_hook,
                )
            elif handlers := self._handlers_map.get(type(message), None):
                await handle_parallel(
                    message,
                    handlers,
                    self._deps,
                    self._pre_hook,
                    self._post_hook,
                    self._exception_hook,
                ),
            else:
                raise RuntimeError(f"{str(type(message))} is not registed.")
        return message_catcher.issued_messages
