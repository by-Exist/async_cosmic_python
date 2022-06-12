from allocation.domain.models import Batch, OrderLine, Product
from sqlalchemy import Column, Date, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import registry, relationship

from .outbox import Envelope

mapper_registry = registry()


event_outbox_table = Table(
    "events",
    mapper_registry.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("type", String(255), nullable=False),
    Column("payload", JSONB, nullable=False),
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
    Column("version_number", Integer, nullable=False),
)

batches = Table(
    "batches",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("reference", String(255)),
    Column("sku", ForeignKey("products.sku")),
    Column("purchased_quantity", Integer, nullable=False),
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
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", String(255)),
    Column("sku", String(255)),
    Column("batchref", String(255)),
)


def start_mappers():
    mapper_registry.map_imperatively(OrderLine, order_lines)
    mapper_registry.map_imperatively(
        Batch,
        batches,
        properties={
            "_allocations": relationship(
                OrderLine, secondary=allocations, collection_class=set, lazy="joined"
            )
        },
    )
    mapper_registry.map_imperatively(
        Product,
        products,
        properties={
            "batches": relationship(Batch, lazy="joined"),
        },
        version_id_col=products.c.version_number,
        version_id_generator=False,
    )
    mapper_registry.map_imperatively(Envelope, event_outbox_table)  # type: ignore
