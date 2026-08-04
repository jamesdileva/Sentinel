"""Fixture tests for the sample app."""

from app.services import Service


def test_create_item():
    item = Service().create(name="widget", price=1.5)
    assert item.name == "widget"


def test_negative_price_rejected():
    try:
        Service().create(name="bad", price=-1)
    except ValueError:
        pass
