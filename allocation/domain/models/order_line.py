from .bases import ValueObject


class OrderLine(ValueObject):
    order_id: str
    sku: str
    qty: int