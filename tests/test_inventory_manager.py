from src.models.item import Item, ItemClass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.models.stock_batch import StockBatch, StockSource
from src.services.inventory_manager import (
    InventoryError,
    InventoryManager,
)

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 11, 10, 0, tzinfo=IST)


def make_batch(
    batch_id,
    quantity=100,
    source=StockSource.GOVT,
    verified=True,
    requires_verification=False,
    expiry_days=10,
):
    return StockBatch(
        batch_id=batch_id,
        item_id="ITEM001",
        depot_id="DEPOT001",
        quantity=quantity,
        received_at=NOW - timedelta(days=1),
        expiry_date=NOW + timedelta(days=expiry_days),
        source=source,
        verified=verified,
        requires_verification=requires_verification,
    )


def test_add_batch():
    manager = InventoryManager()
    batch = make_batch("B001")

    manager.add_batch(batch)

    assert manager.batches["B001"] is batch


def test_duplicate_batch_rejected():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001"))

    with pytest.raises(InventoryError):
        manager.add_batch(make_batch("B001"))


def test_available_stock():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001", 100))
    manager.add_batch(make_batch("B002", 50))

    assert manager.get_available_stock(
        "DEPOT001", "ITEM001", NOW
    ) == 150


def test_expired_batch_excluded():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001", expiry_days=0))

    assert manager.get_available_stock(
        "DEPOT001", "ITEM001", NOW
    ) == 0


def test_unverified_donation_excluded():
    manager = InventoryManager()
    manager.add_batch(
        make_batch(
            "B001",
            source=StockSource.DONATION,
            verified=False,
            requires_verification=True,
        )
    )

    assert manager.get_available_stock(
        "DEPOT001", "ITEM001", NOW
    ) == 0


def test_verify_donation():
    manager = InventoryManager()
    manager.add_batch(
        make_batch(
            "B001",
            source=StockSource.DONATION,
            verified=False,
            requires_verification=True,
        )
    )

    manager.verify_batch("B001", NOW)

    assert manager.batches["B001"].verified is True
    assert manager.batches["B001"].requires_verification is False
    assert manager.verification_times["B001"] == NOW


def test_deduct_stock():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001", 100))

    deductions = manager.deduct_stock(
        "DEPOT001", "ITEM001", 30, NOW
    )

    assert deductions == [("B001", 30)]
    assert manager.batches["B001"].quantity == 70


def test_insufficient_stock():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001", 20))

    with pytest.raises(InventoryError):
        manager.deduct_stock(
            "DEPOT001", "ITEM001", 30, NOW
        )


def test_earliest_expiry_used_first():
    manager = InventoryManager()
    manager.add_batch(make_batch("B001", 50, expiry_days=5))
    manager.add_batch(make_batch("B002", 50, expiry_days=10))

    deductions = manager.deduct_stock(
        "DEPOT001", "ITEM001", 60, NOW
    )

    assert deductions == [("B001", 50), ("B002", 10)]
    assert manager.batches["B001"].quantity == 0
    assert manager.batches["B002"].quantity == 40

def test_reject_donation_with_less_than_seven_days():
    manager = InventoryManager()

    item = Item(
        item_id="FOODPKT",
        name="Cooked food packet",
        unit="packet",
        daily_norm=1,
        shelf_life_days=5,
        item_class=ItemClass.FOOD,
    )
    manager.register_item(item)

    receipt = {
        "receipt_id": "RC-05",
        "batch_id": "B-032",
        "depot_id": "D-1",
        "item_id": "FOODPKT",
        "qty": "400",
        "expiry_ts": "2026-08-18 07:59:00",
        "source": "DONATION",
        "received_ts": "2026-08-11 08:00:00",
    }

    result = manager.process_receipt(receipt)

    assert result is None
    assert "B-032" not in manager.batches
    assert manager.rejected_receipts[0]["receipt_id"] == "RC-05"


def test_accept_donation_with_exactly_seven_days():
    manager = InventoryManager()

    manager.register_item(Item(
        item_id="FOODPKT",
        name="Cooked food packet",
        unit="packet",
        daily_norm=1,
        shelf_life_days=5,
        item_class=ItemClass.FOOD,
    ))

    receipt = {
        "receipt_id": "RC-06",
        "batch_id": "B-033",
        "depot_id": "D-2",
        "item_id": "FOODPKT",
        "qty": "300",
        "expiry_ts": "2026-08-18 11:00:00",
        "source": "DONATION",
        "received_ts": "2026-08-11 11:00:00",
    }

    batch = manager.process_receipt(receipt)

    assert batch is not None
    assert batch.quantity == 300
    assert batch.can_allocate(
        batch.received_at
    )


def test_donated_medicine_is_quarantined():
    manager = InventoryManager()

    manager.register_item(Item(
        item_id="MEDKIT",
        name="Medicine kit",
        unit="kit",
        daily_norm=0.02,
        shelf_life_days=365,
        item_class=ItemClass.LIFE_SAVING,
        is_medicine=True,
    ))

    receipt = {
        "receipt_id": "RC-04",
        "batch_id": "B-031",
        "depot_id": "D-1",
        "item_id": "MEDKIT",
        "qty": "30",
        "expiry_ts": "2027-01-31 23:59:59",
        "source": "DONATION",
        "received_ts": "2026-08-11 01:30:00",
    }

    batch = manager.process_receipt(receipt)

    assert batch.is_quarantined
    assert batch.verified is False

    manager.verify_batch(
        "B-031", "2026-08-11 02:00:00"
    )

    assert batch.is_quarantined is False
    assert batch.verified is True


def test_write_off_expired_batch():
    manager = InventoryManager()
    batch = make_batch("B001", quantity=400, expiry_days=0)
    manager.add_batch(batch)

    write_offs = manager.write_off_expired(NOW)

    assert len(write_offs) == 1
    assert write_offs[0]["batch_id"] == "B001"
    assert write_offs[0]["quantity"] == 400
    assert batch.quantity == 0

def test_load_all_official_opening_batches():
    import csv
    from pathlib import Path

    manager = InventoryManager()

    with open(
        "data/input/items.csv",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    for row in rows:
        manager.register_item(Item(
            item_id=row["item_id"],
            name=row["item_name"],
            unit=row["unit"],
            daily_norm=float(row["daily_norm_per_person"]),
            shelf_life_days=int(row["shelf_life_days"]),
            item_class=ItemClass(row["priority_class"]),
            is_medicine=row["medicine"].lower() == "true",
            unit_weight_kg=float(row["unit_weight_kg"]),
        ))

    with open(
        "data/input/stock_batches.csv",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        batches = list(csv.DictReader(file))

    manager.load_opening_batches(batches)

    assert len(manager.batches) == 27
    assert manager.get_available_stock(
        "D-1",
        "WATER",
        datetime(2026, 8, 10, 3, 0, tzinfo=IST)
    ) == 6000
