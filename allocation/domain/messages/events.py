from .base import Event


class Allocated(Event):

    AGGREGATE_TYPE = "Product"

    order_id: str
    sku: str
    qty: int
    batchref: str


class Deallocated(Event):

    AGGREGATE_TYPE = "Product"

    order_id: str
    sku: str
    qty: int


class OutOfStock(Event):

    AGGREGATE_TYPE = "Product"

    sku: str
