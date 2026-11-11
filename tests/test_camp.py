
import pytest

from src.models.camp import Camp


def test_valid_camp_creation():
    camp = Camp("C001", "Z001", 500, 400, 100)

    assert camp.camp_id == "C001"
    assert camp.occupancy_percentage == 80


def test_exactly_120_percent():
    camp = Camp("C001", "Z001", 500, 600, 100)

    assert camp.occupancy_percentage == 120
    assert camp.is_overflow is False


def test_overflow():
    camp = Camp("C001", "Z001", 500, 601, 100)

    assert camp.is_overflow is True


def test_exactly_150_percent():
    camp = Camp("C001", "Z001", 500, 750, 100)

    assert camp.requires_redirection is False


def test_above_150_percent():
    camp = Camp("C001", "Z001", 500, 751, 100)

    assert camp.requires_redirection is True


def test_vulnerable_count_validation():
    with pytest.raises(ValueError):
        Camp("C001", "Z001", 500, 400, 450)
