import pytest
from sqlalchemy.ext.asyncio.session import AsyncSession
from allocation.adapter import repository
from allocation.domain import models

pytestmark = pytest.mark.usefixtures("orm_mapping", "initialize_database")


async def test_get_by_batchref(database_session: AsyncSession):
    repo = repository.ProductRepository(database_session)
    b1 = models.Batch(reference="b1", sku="sku1", purchased_quantity=100, eta=None)
    b2 = models.Batch(reference="b2", sku="sku1", purchased_quantity=100, eta=None)
    b3 = models.Batch(reference="b3", sku="sku2", purchased_quantity=100, eta=None)
    p1 = models.Product(sku="sku1", batches=[b1, b2])
    p2 = models.Product(sku="sku2", batches=[b3])
    await repo.add(p1)
    await repo.add(p2)
    assert await repo.get_by_batchref("b2") == p1
    assert await repo.get_by_batchref("b3") == p2
