from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..domain.messages import commands
from ..service import exceptions, views

from ..bootstrap import bootstrap
from ..config import settings


app = FastAPI(debug=settings.DEBUG, version=settings.API_VERSION)
bus = bootstrap()


class AddBatchRequest(BaseModel):
    ref: str
    sku: str
    qty: int
    eta: Optional[datetime]


@app.post("/add_batch")
async def add_batch(req: AddBatchRequest):
    await bus.dispatch(
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
        await bus.dispatch(
            commands.Allocate(order_id=req.order_id, sku=req.sku, qty=req.qty)
        )
    except exceptions.InvalidSku as e:
        return JSONResponse(
            content={"message": str(e)}, status_code=status.HTTP_400_BAD_REQUEST
        )
    return JSONResponse(content={"message": "OK"}, status_code=status.HTTP_201_CREATED)


@app.get("/allocations/{order_id}")
async def list_allocation(order_id: str):
    result = await views.allocations(
        order_id=order_id, uow_factory=bus._deps["uow_factory"]  # type: ignore
    )
    if not result:
        return JSONResponse(
            content={"message": "not found"}, status_code=status.HTTP_404_NOT_FOUND
        )
    return JSONResponse(
        content=jsonable_encoder(result), status_code=status.HTTP_200_OK
    )
