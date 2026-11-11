import pytest
from src.models.vehicle import Vehicle, VehicleType

def truck(**overrides):
    data = dict(vehicle_id="V-01", depot_id="D-1", vehicle_type=VehicleType.TRUCK,
                capacity_kg=5000, speed_kmph=30, driver_name="Test Driver")
    data.update(overrides)
    return Vehicle(**data)

def test_valid_truck():
    v = truck()
    assert v.capacity_kg == 5000 and v.capacity_tonnes == 5

def test_valid_boat():
    v = Vehicle("V-02", "D-1", VehicleType.BOAT, 1000, 20)
    assert v.capacity_kg == 1000

def test_valid_helicopter():
    v = Vehicle("V-03", "D-1", VehicleType.HELICOPTER, 2000, 120)
    assert v.has_sorties_available

def test_invalid_truck_capacity():
    with pytest.raises(ValueError):
        truck(capacity_kg=10000)

def test_driver_duty_limit():
    with pytest.raises(ValueError):
        truck(duty_hours_today=13)

def test_trip_exceeds_duty_limit():
    assert truck(duty_hours_today=11).can_complete_trip(1.5) is False

def test_trip_exactly_12_hours():
    assert truck(duty_hours_today=11).can_complete_trip(1) is True

def test_helicopter_sortie_limit():
    v = Vehicle("V-03", "D-1", VehicleType.HELICOPTER, 2000, 120, sorties_today=4)
    assert not v.has_sorties_available
    with pytest.raises(ValueError):
        v.record_sortie()

def test_vehicle_grounded_after_three_discrepancies():
    v = truck()
    for _ in range(3):
        v.record_discrepancy()
    assert v.is_grounded

def test_csv_driver_and_duty_fields():
    v = truck(driver_name="Ravi", duty_hours_today=4.5)
    assert v.driver_name == "Ravi"
    assert v.remaining_duty_hours == 7.5
