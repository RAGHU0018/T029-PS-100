
import pytest

from src.models.item import Item, ItemClass


def test_valid_item_creation():
    item = Item(
        "I001",
        "Drinking Water",
        "litre",
        3.0,
        365,
        ItemClass.LIFE_SAVING
    )

    assert item.item_id == "I001"
    assert item.item_class == ItemClass.LIFE_SAVING


def test_valid_item_classes():
    assert ItemClass.LIFE_SAVING.value == "LIFE_SAVING"
    assert ItemClass.FOOD.value == "FOOD"
    assert ItemClass.SHELTER.value == "SHELTER"


def test_empty_item_name():
    with pytest.raises(ValueError):
        Item("I001", "", "litre", 3.0, 365, ItemClass.FOOD)


def test_invalid_daily_norm():
    with pytest.raises(ValueError):
        Item("I001", "Water", "litre", 0, 365, ItemClass.FOOD)


def test_invalid_shelf_life():
    with pytest.raises(ValueError):
        Item("I001", "Water", "litre", 3.0, 0, ItemClass.FOOD)


def test_invalid_item_class():
    with pytest.raises(ValueError):
        Item("I001", "Water", "litre", 3.0, 365, "FOOD")


def test_medicine_flag():
    medicine = Item(
        "I002",
        "Emergency Medicine",
        "tablet",
        1.0,
        730,
        ItemClass.LIFE_SAVING,
        is_medicine=True
    )

    assert medicine.is_medicine is True
