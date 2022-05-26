from typing import Protocol
from pydamain import port  # type: ignore


class EmailSender(port.EmailSender, Protocol):

    HOST: str
    PORT: int
