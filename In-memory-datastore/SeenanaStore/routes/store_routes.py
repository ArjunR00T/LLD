
from fastapi import APIRouter, Request
from services.store_handler import StoreHandler

storerouter = APIRouter()
store_handler = StoreHandler()

@storerouter.get("/store/{key}")
async def get_value(key: str, request: Request):
    return store_handler.get_value(request.app.state.store, key)

@storerouter.post("/store/{key}")
async def set_value(
    key: str,
    request: Request,
    value: str,
    expiry: int | None = None,
):
    store_handler.put_value(request.app.state.store, key, value, expiry)
    return {"status": "stored"}

@storerouter.delete("/store/{key}")
async def delete_value(key: str, request: Request):
    store_handler.delete_value(request.app.state.store, key)
    return {"status": "deleted"}
