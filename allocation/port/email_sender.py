from email.message import EmailMessage
from typing import Protocol


class EmailSender(Protocol):
    async def send(self, _message: EmailMessage):
        ...
