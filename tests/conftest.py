import time
from pathlib import Path
from typing import Callable

import pytest
import requests
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker, clear_mappers
from tenacity import retry, stop
from allocation.adapter import unit_of_work

from allocation.adapter.orm import start_mapping, mapper_registry
from allocation.config import settings


# ORM Mapping
@pytest.fixture
def orm_mapping():
    start_mapping()
    yield
    clear_mappers()


# Database Engine
@pytest.fixture
async def database_engine():
    engine = create_async_engine(
        settings.DATABASE_URL, future=True, isolation_level="REPEATABLE READ"
    )
    async with engine.begin() as conn:
        await conn.run_sync(mapper_registry.metadata.drop_all)
        await conn.run_sync(mapper_registry.metadata.create_all)
    return engine


# Database Session
AsyncSessionFactory = Callable[[], AsyncSession]


@pytest.fixture
def database_session_factory(database_engine: AsyncEngine) -> AsyncSessionFactory:
    return sessionmaker(bind=database_engine, class_=AsyncSession)  # type: ignore


@pytest.fixture
async def database_session(database_session_factory: AsyncSessionFactory):
    async with database_session_factory() as session:
        yield session


# UnitOfWork
@pytest.fixture
def uow_class(database_session_factory: AsyncSessionFactory):
    class UOW(unit_of_work.SQLAlchemyUnitOfWork):
        SESSION_FACTORY = database_session_factory

    return UOW


# Waiting
@retry(stop=stop.stop_after_delay(10))
async def wait_for_database_come_up(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(engine.connect)


@retry(stop=stop.stop_after_delay(10))
def wait_for_mailhog_to_come_up():
    requests.get(f"http://{settings.EMAIL_HOST}:{settings.EMAIL_HTTP_PORT}")


@retry(stop=stop.stop_after_delay(10))
def wait_for_webapplication_to_come_up():
    requests.get("http://localhost:8000")


@retry(stop=stop.stop_after_delay(10))
def wait_for_kafka_connect_to_come_up():
    requests.get(f"http://{settings.KAFKA_CONNECT_HOST}:{settings.KAFKA_CONNECT_PORT}")


# API
@pytest.fixture
def restart_api():
    (Path(__file__).parent / "../src/allocation/entrypoint/fastapi_.py").touch()
    time.sleep(0.5)
    wait_for_webapplication_to_come_up()
