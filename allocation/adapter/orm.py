from sqlalchemy import ForeignKey, Table, Column, Integer, String, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import registry, relationship

from .outbox import Envelope

from ..domain.models import OrderLine, Batch, Product


mapper_registry = registry()


event_outbox_table = Table(
    "envelopes",
    mapper_registry.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("type", String(255), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("timestamp", TIMESTAMP, nullable=False),
    Column("aggregate_id", String(255), nullable=False),
    Column("aggregate_type", String(255), nullable=False),
)


order_lines = Table(
    "order_lines",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", String(255)),
    Column("sku", String(255)),
    Column("qty", Integer, nullable=False),
)


products = Table(
    "products",
    mapper_registry.metadata,
    Column("sku", String(255), primary_key=True),
    Column("version_number", Integer, nullable=False, server_default="0"),
)

batches = Table(
    "batches",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("reference", String(255)),
    Column("sku", ForeignKey("products.sku")),
    Column("_purchased_quantity", Integer, nullable=False),
    Column("eta", Date, nullable=True),
)

allocations = Table(
    "allocations",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("orderline_id", ForeignKey("order_lines.id")),
    Column("batch_id", ForeignKey("batches.id")),
)

allocations_view = Table(
    "allocations_view",
    mapper_registry.metadata,
    Column("order_id", String(255)),
    Column("sku", String(255)),
    Column("batchref", String(255)),
)


def start_mapping():
    mapper_registry.map_imperatively(OrderLine, order_lines)  # type: ignore
    mapper_registry.map_imperatively(Batch, batches, properties={"_allocations": relationship(OrderLine, secondary=allocations, collection_class=set)})  # type: ignore
    mapper_registry.map_imperatively(Product, products, properties={"batches": relationship(Batch)})  # type: ignore
    mapper_registry.map_imperatively(Envelope, event_outbox_table)  # type: ignore
