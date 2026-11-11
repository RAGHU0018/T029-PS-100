
import pytest

from src.models.depot import Depot


def test_valid_depot():
    depot = Depot("D001", "Central Depot", "Bengaluru")

    assert depot.depot_id == "D001"


def test_add_stock_batch():
    depot = Depot("D001", "Central Depot", "Bengaluru")

    depot.add_stock_batch("B001")

    assert "B001" in depot.stock_batch_ids


def test_duplicate_stock_batch():
    depot = Depot("D001", "Central Depot", "Bengaluru")

    depot.add_stock_batch("B001")

    with pytest.raises(ValueError):
        depot.add_stock_batch("B001")


def test_add_vehicle():
    depot = Depot("D001", "Central Depot", "Bengaluru")

    depot.add_vehicle("V001")

    assert "V001" in depot.vehicle_ids


def test_duplicate_vehicle():
    depot = Depot("D001", "Central Depot", "Bengaluru")

    depot.add_vehicle("V001")

    with pytest.raises(ValueError):
        depot.add_vehicle("V001")


def test_empty_depot_name():
    with pytest.raises(ValueError):
        Depot("D001", "", "Bengaluru")
