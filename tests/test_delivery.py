
import pytest
from datetime import datetime, timezone

from src.models.delivery import Delivery


DISPATCH_TIME = datetime(
    2026, 11, 11, 10, 0, tzinfo=timezone.utc
)

DELIVERED_TIME = datetime(
    2026, 11, 11, 12, 0, tzinfo=timezone.utc
)


def create_delivery(**overrides):
    data = {
        "delivery_id": "DL001",
        "request_id": "R001",
        "vehicle_id": "V001",
        "depot_id": "D001",
        "camp_id": "C001",
        "item_id": "I001",
        "batch_id": "B001",
        "dispatched_quantity": 100,
        "delivered_quantity": 100,
        "returned_quantity": 0,
        "dispatch_time": DISPATCH_TIME,
        "delivered_at": DELIVERED_TIME
    }

    data.update(overrides)
    return Delivery(**data)


def test_valid_delivery():
    delivery = create_delivery()

    assert delivery.dispatched_quantity == 100


def test_shortfall_calculation():
    delivery = create_delivery(delivered_quantity=95)

    assert delivery.shortfall_quantity == 5


def test_exactly_two_percent():
    delivery = create_delivery(delivered_quantity=98)

    assert delivery.discrepancy_percentage == 2.0
    assert delivery.has_discrepancy is False


def test_above_two_percent():
    delivery = create_delivery(delivered_quantity=97)

    assert delivery.has_discrepancy is True


def test_returned_quantity():
    delivery = create_delivery(
        delivered_quantity=90,
        returned_quantity=10
    )

    assert delivery.returned_quantity == 10
    assert delivery.shortfall_quantity == 0


def test_invalid_quantity():
    with pytest.raises(ValueError):
        create_delivery(delivered_quantity=110)


def test_delivery_before_dispatch():
    with pytest.raises(ValueError):
        create_delivery(
            delivered_at=datetime(
                2026, 11, 11, 9, 0, tzinfo=timezone.utc
            )
        )


def test_incomplete_delivery():
    delivery = create_delivery(delivered_at=None)

    assert delivery.discrepancy_percentage is None
    assert delivery.has_discrepancy is False
