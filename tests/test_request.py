
import pytest
from datetime import datetime, timezone

from src.models.request import Request, Urgency


def create_request(**overrides):
    data = {
        "request_id": "R001",
        "camp_id": "C001",
        "item_id": "I001",
        "quantity": 500,
        "urgency": Urgency.CRITICAL,
        "requested_at": datetime(
            2026, 11, 11, 10, 0, tzinfo=timezone.utc
        )
    }

    data.update(overrides)
    return Request(**data)


def test_valid_request():
    request = create_request()

    assert request.quantity == 500
    assert request.urgency == Urgency.CRITICAL


def test_high_urgency():
    request = create_request(urgency=Urgency.HIGH)

    assert request.urgency == Urgency.HIGH


def test_normal_urgency():
    request = create_request(urgency=Urgency.NORMAL)

    assert request.urgency == Urgency.NORMAL


def test_invalid_urgency():
    with pytest.raises(ValueError):
        create_request(urgency="LOW")


def test_zero_quantity():
    with pytest.raises(ValueError):
        create_request(quantity=0)


def test_empty_camp_id():
    with pytest.raises(ValueError):
        create_request(camp_id="")


def test_naive_datetime():
    with pytest.raises(ValueError):
        create_request(
            requested_at=datetime(2026, 11, 11, 10, 0)
        )
