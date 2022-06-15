import pytest
import requests

from allocation import bootstrap
from allocation.adapter import email_sender, unit_of_work
from allocation.config import settings
from allocation.domain.messages import commands
from allocation.service.message_bus import MessageBus

from ..random_refs import random_sku


pytestmark = pytest.mark.usefixtures("orm_mapping")


@pytest.fixture
def bus(uow_class: type[unit_of_work.UnitOfWork]):
    bus = bootstrap.bootstrap(
        start_orm_mapping=False,
        uow_class=uow_class,
        email_sender=email_sender.MailhogEmailSender(),
    )
    yield bus


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
