
import pytest
from datetime import datetime, timezone, timedelta

from src.models.stock_batch import StockBatch


RECEIVED_AT = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)
EXPIRY_DATE = RECEIVED_AT + timedelta(days=30)


def create_batch(**overrides):
    data = {
        "batch_id": "B001",
        "item_id": "I001",
        "depot_id": "D001",
        "quantity": 500,
        "received_at": RECEIVED_AT,
        "expiry_date": EXPIRY_DATE
    }

    data.update(overrides)
    return StockBatch(**data)


def test_valid_batch_creation():
    batch = create_batch()

    assert batch.batch_id == "B001"
    assert batch.quantity == 500


def test_negative_quantity():
    with pytest.raises(ValueError):
        create_batch(quantity=-10)


def test_fractional_quantity():
    with pytest.raises(ValueError):
        create_batch(quantity=10.5)


def test_expired_batch():
    batch = create_batch()

    current_time = EXPIRY_DATE

    assert batch.is_expired(current_time) is True
    assert batch.can_allocate(current_time) is False


def test_non_expired_batch():
    batch = create_batch()

    current_time = RECEIVED_AT + timedelta(days=5)

    assert batch.is_expired(current_time) is False
    assert batch.can_allocate(current_time) is True


def test_donated_medicine_quarantine():
    batch = create_batch(
        is_donation=True,
        requires_verification=True,
        verified=False
    )

    assert batch.is_quarantined is True
    assert batch.can_allocate(RECEIVED_AT) is False


def test_verified_donation():
    batch = create_batch(
        is_donation=True,
        requires_verification=True,
        verified=True
    )

    assert batch.is_quarantined is False
    assert batch.can_allocate(RECEIVED_AT) is True


def test_verification_without_donation():
    with pytest.raises(ValueError):
        create_batch(requires_verification=True)


def test_expiry_before_receipt():
    with pytest.raises(ValueError):
        create_batch(
            expiry_date=RECEIVED_AT - timedelta(days=1)
        )


def test_timezone_required():
    with pytest.raises(ValueError):
        create_batch(
            received_at=datetime(2026, 11, 11, 10, 0)
        )
