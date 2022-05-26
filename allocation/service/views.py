from ..adapter.unit_of_work import UnitOfWork


async def allocations(order_id: str, uow_factory: type[UnitOfWork]):
    async with uow_factory() as uow:
        results = await uow._session.execute(  # type: ignore
            "SELECT sku, batchref FROM allocations_view WHERE orderid = :orderid",  # type: ignore
            dict(order_id=order_id),
        )
    return [dict(result) for result in results]
