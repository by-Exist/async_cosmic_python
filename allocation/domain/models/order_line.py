from typing import Any
from .bases import ValueObject


class OrderLine(ValueObject):
    order_id: str
    sku: str
    qty: int


origin_setattr = OrderLine.__setattr__


def new_setattr(self: Any, name: str, value: Any):
    if name == "_sa_instance_state":
        object.__setattr__(self, name, value)
    else:
        origin_setattr(self, name, value)


OrderLine.__setattr__ = new_setattr
