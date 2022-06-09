from json import loads

import requests
from allocation.config import settings
from loguru import logger
from tenacity import retry, stop, wait

max_tries = 10
wait_seconds = 6


@retry(
    stop=stop.stop_after_attempt(max_tries),
    wait=wait.wait_fixed(wait_seconds),
)
def init():

    response = requests.post(
        url=f"http://{settings.KAFKA_CONNECT_HOST}:{settings.KAFKA_CONNECT_PORT}/connectors",
        json=loads(settings.KAFKA_CONNECTER_CONFIGURATION),
    )
    assert response.status_code == 201 or response.status_code == 409

    print(loads(response.content))

    match response.status_code:
        case 201:
            return "Created connecter."
        case 409:
            return "Connector already exist."


def main() -> None:
    logger.info("Create outbox connecter...")
    description = init()
    logger.info(f"{description}")


if __name__ == "__main__":
    main()
