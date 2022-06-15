from datetime import datetime
from typing import Any, Awaitable

from allocation.adapter.email_sender import MailhogEmailSender
from allocation.adapter.unit_of_work import UnitOfWork
from allocation.bootstrap import bootstrap
from allocation.config import settings
from allocation.domain.messages import commands
from allocation.service import exceptions, views
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

app = FastAPI(debug=False, version=settings.API_VERSION)
bus_default_conf: dict[str, Any] = {
    "start_orm_mapping": True,
    "uow_class": UnitOfWork,
    "email_sender": MailhogEmailSender(),
}
bus = bootstrap(**bus_default_conf)


class AwaitableBackgroundTask(BackgroundTask):
    def __init__(self, awaitable: Awaitable[Any]):
        self.awaitable = awaitable

    async def __call__(self):
        await self.awaitable


class AddBatchRequest(BaseModel):
    ref: str
    sku: str
    qty: int
    eta: datetime | None


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
        201: {"message": "OK"},
    },
)
async def allocate(req: AllocateRequest):
    try:
        task = await bus.handle(
            commands.Allocate(order_id=req.order_id, sku=req.sku, qty=req.qty),
            return_hooked_task=True,
        )
    except exceptions.InvalidSku as e:
        return JSONResponse(
            content={"message": str(e)}, status_code=status.HTTP_400_BAD_REQUEST
        )
    return JSONResponse(
        content={"message": "OK"},
        status_code=status.HTTP_201_CREATED,
        background=AwaitableBackgroundTask(task),
    )


@app.get("/allocations/{order_id}")
async def list_allocation(order_id: str):
    result = await views.allocations(
        order_id=order_id, session=UnitOfWork.SESSION_FACTORY()
    )
    if not result:
        return JSONResponse(
            content={"message": f"order {order_id} not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return JSONResponse(
        content=jsonable_encoder(result), status_code=status.HTTP_200_OK
    )
