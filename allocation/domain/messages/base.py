from abc import ABCMeta
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import UUID, uuid4

from typing_extensions import Self, dataclass_transform


@dataclass_transform(
    eq_default=True,
    order_default=False,
    kw_only_default=True,
    field_descriptors=(field,),
)
class MessageMeta(ABCMeta):
    def __new__(
        cls: type[Self], name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> Self:
        new_cls = super().__new__(cls, name, bases, namespace)
        return dataclass(frozen=True, kw_only=True)(new_cls)  # type: ignore


class _Message(metaclass=MessageMeta):
    uid: UUID = field(default_factory=uuid4)
    create_time: float = field(
        default_factory=lambda: datetime.now(timezone.utc).timestamp()
    )


class Command(_Message):
    ...


class Event(_Message):
    AGGREGATE_TYPE: ClassVar[str]
    aggregate_id: str


Message = Command | Event