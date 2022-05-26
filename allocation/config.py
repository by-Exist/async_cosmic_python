from pydantic import BaseSettings as _BaseSettings


class _Settings(_BaseSettings):

    DEBUG: bool

    API_VERSION: str

    DATABASE_PROTOCOL: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USERNAME: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str

    EMAIL_HOST: str
    EMAIL_PORT: int

    @property
    def DATABASE_URI(self):
        return f"{self.DATABASE_PROTOCOL}://{self.DATABASE_USERNAME}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


settings = _Settings()  # type: ignore
