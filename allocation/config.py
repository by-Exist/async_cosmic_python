from typing import Literal

from pydantic import BaseSettings as _BaseSettings


class _Settings(_BaseSettings):

    DEPLOYMENT_ENVIRONMENT: Literal["local", "dev", "prod"]

    API_VERSION: str

    DATABASE_URL: str

    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HTTP_PORT: int

    KAFKA_CONNECT_HOST: str
    KAFKA_CONNECT_PORT: str
    KAFKA_CONNECTER_CONFIGURATION: str


settings = _Settings()  # type: ignore
