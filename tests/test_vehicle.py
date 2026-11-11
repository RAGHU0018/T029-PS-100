
import pytest

from src.models.vehicle import Vehicle, VehicleType


def create_truck(**overrides):
    data = {
        "vehicle_id": "V001",
        "depot_id": "D001",
        "vehicle_type": VehicleType.TRUCK,
        "capacity_tonnes": 5.0,
        "speed_kmph": 30.0
    }

    data.update(overrides)
    return Vehicle(**data)


def test_valid_truck():
    truck = create_truck()

    assert truck.capacity_tonnes == 5.0
    assert truck.speed_kmph == 30.0


def test_valid_boat():
    boat = Vehicle(
        "V002", "D001", VehicleType.BOAT, 1.0, 20.0
    )

    assert boat.capacity_tonnes == 1.0


def test_valid_helicopter():
    helicopter = Vehicle(
        "V003", "D001", VehicleType.HELICOPTER, 2.0, None
    )

    assert helicopter.has_sorties_available is True


def test_invalid_truck_capacity():
    with pytest.raises(ValueError):
        create_truck(capacity_tonnes=10.0)


def test_driver_duty_limit():
    with pytest.raises(ValueError):
        create_truck(duty_hours_today=13.0)


def test_trip_exceeds_duty_limit():
    truck = create_truck(duty_hours_today=11.0)

    assert truck.can_complete_trip(1.5) is False


def test_trip_exactly_12_hours():
    truck = create_truck(duty_hours_today=11.0)

    assert truck.can_complete_trip(1.0) is True


def test_helicopter_sortie_limit():
    helicopter = Vehicle(
        "V003", "D001", VehicleType.HELICOPTER, 2.0, None,
        sorties_today=4
    )

    assert helicopter.has_sorties_available is False

    with pytest.raises(ValueError):
        helicopter.record_sortie()


def test_vehicle_grounded_after_three_discrepancies():
    truck = create_truck()

    truck.record_discrepancy()
    truck.record_discrepancy()

    assert truck.is_grounded is False

    truck.record_discrepancy()

    assert truck.is_grounded is True
