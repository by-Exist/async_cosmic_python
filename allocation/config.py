from pydantic import BaseSettings as _BaseSettings


class _Settings(_BaseSettings):

    DEBUG: bool

    API_VERSION: str

    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USERNAME: str
    DATABASE_PASSWORD: str

    EMAIL_HOST: str
    EMAIL_PORT: int


settings = _Settings()  # type: ignore
