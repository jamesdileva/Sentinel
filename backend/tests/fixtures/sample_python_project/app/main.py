"""Sample FastAPI app — fixture for parser and indexer tests."""

from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.services import Service

app = FastAPI(title="Sample API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/items")
def create_item(name: str, price: float) -> JSONResponse:
    item = Service().create(name=name, price=price)
    return JSONResponse(content={"id": item.id, "name": item.name})


@app.get("/items/{item_id}")
async def get_item(item_id: int, include_details: Optional[bool] = False) -> dict:
    return {"item_id": item_id, "include_details": include_details}
