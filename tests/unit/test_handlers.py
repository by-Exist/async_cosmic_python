from contextvars import ContextVar
from datetime import date
from email.message import EmailMessage
from types import TracebackType
from typing import Optional

import pytest
from allocation import bootstrap, port
from allocation.domain.messages import commands
from allocation.domain.models import Product
from allocation.service import exceptions


class FakeRepository(port.repository.ProductRepository):
    def __init__(self, products: set[Product]):
        self._products = products

    async def add(self, product: Product):
        self._products.add(product)

    async def get(self, sku: str):
        return next((product for product in self._products if product.sku == sku), None)

    async def delete(self, product: Product):
        ...

    async def get_by_batchref(self, batchref: str):
        return next(
            (
                product
                for product in self._products
                for batch in product.batches
                if batch.reference == batchref
            ),
            None,
        )


products_context_var: ContextVar[set[Product]] = ContextVar("products")


@pytest.fixture(autouse=True)
def set_products_context_var():
    token = products_context_var.set(set())
    yield
    products_context_var.reset(token)


@pytest.fixture(autouse=True)
def set_uows_context_var():
    token = uows_context_var.set(list())
    yield
    uows_context_var.reset(token)


class FakeUnitOfWork(port.unit_of_work.UnitOfWork):
    def __init__(self):
        self.products = FakeRepository(products_context_var.get())
        self._outbox = None  # type: ignore
        self.committed = False
        uows_context_var.get().append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        return await super().__aexit__(exc_type, exc_value, traceback)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


uows_context_var: ContextVar[list[FakeUnitOfWork]] = ContextVar("uows")


class FakeEmailSender(port.email_sender.EmailSender):

    HOST: str = "fake"
    PORT: int = 0000

    def __init__(self):
        self.sent = set[EmailMessage]()

    async def send(self, message: EmailMessage):
        self.sent.add(message)


def bootstrap_test_app():

    return bootstrap.bootstrap(
        start_orm_mapping=False,
        uow_class=FakeUnitOfWork,
        email_sender=FakeEmailSender(),
    )


class TestAddBatch:
    async def test_for_new_product(self):
        bus = bootstrap_test_app()
        await bus.handle(
            commands.CreateBatch(ref="b1", sku="CRUNCHY-ARMCHAIR", qty=100, eta=None)
        )
        assert uows_context_var.get()[0].committed
        async with FakeUnitOfWork() as uow:
            assert await uow.products.get("CRUNCHY-ARMCHAIR") is not None

    async def test_for_existing_product(self):
        bus = bootstrap_test_app()
        await bus.handle(
            commands.CreateBatch(ref="b1", sku="GARISH-RUG", qty=100, eta=None)
        )
        await bus.handle(
            commands.CreateBatch(ref="b2", sku="GARISH-RUG", qty=99, eta=None)
        )
        async with FakeUnitOfWork() as uow:
            product = await uow.products.get("GARISH-RUG")
            assert product
            batchrefs = [b.reference for b in product.batches]
            assert "b1" in batchrefs and "b2" in batchrefs


class TestAllocate:
    async def test_allocates(self):
        bus = bootstrap_test_app()
        await bus.handle(
            commands.CreateBatch(
                ref="batch1", sku="COMPLICATED-LAMP", qty=100, eta=None
            )
        )
        await bus.handle(
            commands.Allocate(order_id="o1", sku="COMPLICATED-LAMP", qty=10)
        )
        async with FakeUnitOfWork() as uow:
            product = await uow.products.get("COMPLICATED-LAMP")
            assert product
            assert product.batches[0].available_quantity == 90

    async def test_errors_for_invalid_sku(self):
        bus = bootstrap_test_app()
        await bus.handle(commands.CreateBatch(ref="b1", sku="AREALSKU", qty=100))
        with pytest.raises(exceptions.InvalidSku):
            await bus.handle(
                commands.Allocate(order_id="o1", sku="NONEXISTENTSKU", qty=10)
            )

    async def test_commits(self):
        bus = bootstrap_test_app()
        await bus.handle(
            commands.CreateBatch(ref="b1", sku="OMINOUS-MIRROR", qty=100, eta=None)
        )
        await bus.handle(commands.Allocate(order_id="o1", sku="OMINOUS-MIRROR", qty=10))
        uow = uows_context_var.get()[0]
        assert uow.committed

    async def test_sends_email_on_out_of_stock_error(self):
        fake_email_sender = FakeEmailSender()
        bus = bootstrap.bootstrap(
            start_orm_mapping=False,
            uow_class=FakeUnitOfWork,
            email_sender=fake_email_sender,
        )
        await bus.handle(
            commands.CreateBatch(ref="b1", sku="POPULAR-CURTAINS", qty=9, eta=None)
        )
        await bus.handle(
            commands.Allocate(order_id="o1", sku="POPULAR-CURTAINS", qty=10)
        )
        assert fake_email_sender.sent.pop() is not None


class TestChangeBatchQuantity:
    async def test_changes_available_quantity(self):
        bus = bootstrap_test_app()
        await bus.handle(
            commands.CreateBatch(ref="batch1", sku="ADORABLE-SETTEE", qty=100, eta=None)
        )
        async with FakeUnitOfWork() as uow:
            [batch] = (
                product.batches
                if (product := (await uow.products.get(sku="ADORABLE-SETTEE")))
                else []
            )
            assert batch.available_quantity == 100
            await bus.handle(commands.ChangeBatchQuantity(ref="batch1", qty=50))
            assert batch.available_quantity == 50

    async def test_reallocates_if_necessary(self):
        bus = bootstrap_test_app()
        history = [
            commands.CreateBatch(
                ref="batch1", sku="INDIFFERENT-TABLE", qty=50, eta=None
            ),
            commands.CreateBatch(
                ref="batch2", sku="INDIFFERENT-TABLE", qty=50, eta=date.today()
            ),
            commands.Allocate(order_id="order1", sku="INDIFFERENT-TABLE", qty=20),
            commands.Allocate(order_id="order2", sku="INDIFFERENT-TABLE", qty=20),
        ]
        for msg in history:
            await bus.handle(msg)

        async with FakeUnitOfWork() as uow:
            product = await uow.products.get(sku="INDIFFERENT-TABLE")
            assert product
            [batch1, batch2] = product.batches
            assert batch1.available_quantity == 10
            assert batch2.available_quantity == 50

        await bus.handle(commands.ChangeBatchQuantity(ref="batch1", qty=25))
        assert batch1.available_quantity == 5
        assert batch2.available_quantity == 30
