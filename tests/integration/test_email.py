import pytest
import requests

from sqlalchemy.orm import clear_mappers

from allocation import bootstrap
from allocation.adapter import email_sender, unit_of_work
from allocation.config import settings
from allocation.domain.messages import commands
from allocation.service.message_bus import MessageBus

from ..conftest import AsyncSessionFactory
from ..random_refs import random_sku


@pytest.fixture
def bus(database_session_factory: AsyncSessionFactory):
    class UOW(unit_of_work.SQLAlchemyUnitOfWork):
        SESSION_FACTORY = database_session_factory

    bus = bootstrap.bootstrap(
        start_orm_mapping=True,
        uow_class=UOW,
        email_sender=email_sender.EmailSender(),
    )
    yield bus
    clear_mappers()


def get_email_from_mailhog(sku: str):
    all_emails = requests.get(
        f"http://{settings.EMAIL_HOST}:{settings.EMAIL_HTTP_PORT}/api/v2/messages"
    ).json()
    return next(m for m in all_emails["items"] if sku in str(m))


async def test_out_of_stock_email(bus: MessageBus):
    sku = random_sku()
    await bus.handle(commands.CreateBatch(ref="batch1", sku=sku, qty=9, eta=None))
    await bus.handle(commands.Allocate(order_id="order1", sku=sku, qty=10))
    email = get_email_from_mailhog(sku)
    assert email["Raw"]["From"] == "from@example.com"
    assert email["Raw"]["To"] == ["to@example.com"]
    assert f"Out of stock for {sku}" in email["Raw"]["Data"]
