
import pytest

from src.models.zone import Zone, RoadStatus


def test_valid_zone_creation():
    zone = Zone(
        zone_id="Z001",
        population=5000,
        severity_level=5,
        road_status=RoadStatus.OPEN
    )

    assert zone.zone_id == "Z001"
    assert zone.population == 5000


def test_invalid_severity():
    with pytest.raises(ValueError):
        Zone(
            zone_id="Z001",
            population=5000,
            severity_level=6,
            road_status=RoadStatus.OPEN
        )


def test_negative_population():
    with pytest.raises(ValueError):
        Zone(
            zone_id="Z001",
            population=-100,
            severity_level=3,
            road_status=RoadStatus.OPEN
        )


def test_negative_depot_distance():
    with pytest.raises(ValueError):
        Zone(
            zone_id="Z001",
            population=1000,
            severity_level=3,
            road_status=RoadStatus.OPEN,
            depot_distances={"D001": -10}
        )
