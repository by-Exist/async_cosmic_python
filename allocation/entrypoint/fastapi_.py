from datetime import datetime
from typing import Any, Callable, Optional

from allocation.adapter.email_sender import EmailSender
from allocation.adapter.unit_of_work import SQLAlchemyUnitOfWork
from allocation.bootstrap import bootstrap
from allocation.config import settings
from allocation.domain.messages import commands
from allocation.service import exceptions, views
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

app = FastAPI(debug=False, version=settings.API_VERSION)


class UnitOfWork(SQLAlchemyUnitOfWork):
    SESSION_FACTORY: Callable[[], AsyncSession] = sessionmaker(  # type: ignore
        create_async_engine(
            settings.DATABASE_URL,
            isolation_level="REPEATABLE READ",
            future=True,
        ),
        class_=AsyncSession,  # type: ignore
    )


match settings.DEPLOYMENT_ENVIRONMENT:
    case "local":
        conf = {
            "start_orm_mapping": True,
            "uow_class": UnitOfWork,
            "email_sender": EmailSender(),
        }
    case "dev":
        conf = {
            "start_orm_mapping": True,
            "uow_class": UnitOfWork,
            "email_sender": EmailSender(),
        }
    case "prod":
        conf = {
            "start_orm_mapping": True,
            "uow_class": UnitOfWork,
            "email_sender": EmailSender(),
        }

bus = bootstrap(**conf)  # type: ignore


class AddBatchRequest(BaseModel):
    ref: str
    sku: str
    qty: int
    eta: Optional[datetime]


@app.post("/add_batch")
async def add_batch(req: AddBatchRequest):
    await bus.handle(
        commands.CreateBatch(ref=req.ref, sku=req.sku, qty=req.qty, eta=req.eta)
    )
    return "OK"


class AllocateRequest(BaseModel):
    order_id: str
    sku: str
    qty: int


@app.post(
    "/allocate",
    responses={
        400: {"message": "Invalid sku ..."},
        200: {"message": "OK"},
    },
)
async def allocate(req: AllocateRequest):
    try:
        await bus.handle(
            commands.Allocate(order_id=req.order_id, sku=req.sku, qty=req.qty)
        )
    except exceptions.InvalidSku as e:
        return JSONResponse(
            content={"message": str(e)}, status_code=status.HTTP_400_BAD_REQUEST
        )
    return JSONResponse(content={"message": "OK"}, status_code=status.HTTP_201_CREATED)


@app.get("/allocations/{order_id}")
async def list_allocation(order_id: str):
    result: list[dict[str, Any]] = await views.allocations(
        order_id=order_id, uow_factory=bus._deps["uow_factory"]  # type: ignore
    )
    if not result:
        return JSONResponse(
            content={"message": "not found"}, status_code=status.HTTP_404_NOT_FOUND
        )
    return JSONResponse(
        content=jsonable_encoder(result), status_code=status.HTTP_200_OK
    )
