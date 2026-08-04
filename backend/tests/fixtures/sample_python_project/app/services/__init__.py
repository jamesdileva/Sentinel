"""Sample service module — fixture for parser tests."""

import logging

logger = logging.getLogger(__name__)


class Item:
    """A simple item model."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
        self.id = hash((name, price))


class Service:
    """Business logic for the sample app."""

    def create(self, name: str, price: float) -> Item:
        logger.info("Creating item %s", name)
        if price <= 0:
            raise ValueError("price must be positive")
        return Item(name=name, price=price)

    async def list_items(self) -> list[Item]:
        return []
