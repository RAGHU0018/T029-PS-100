
import pytest
from pathlib import Path

from src.services.data_loader import (
    CSVDataLoader,
    DataLoaderError
)


INPUT_DIR = Path("data/input")


def test_load_all_csv_files():
    loader = CSVDataLoader(INPUT_DIR)

    data = loader.load_all()

    assert len(data) == 10


def test_official_sample_row_counts():
    loader = CSVDataLoader(INPUT_DIR)

    data = loader.load_all()

    expected_counts = {
        "depots": 3,
        "zones": 8,
        "camps": 15,
        "distances": 150,
        "items": 12,
        "vehicles": 10,
        "stock_batches": 27,
        "stock_receipts": 13,
        "requests": 180,
        "deliveries": 88,
    }

    for filename, expected_count in expected_counts.items():
        assert len(data[filename]) == expected_count


def test_load_commands():
    loader = CSVDataLoader(INPUT_DIR)

    commands = loader.load_commands()

    assert len(commands) == 316


def test_commands_preserve_file_order():
    loader = CSVDataLoader(INPUT_DIR)

    commands = loader.load_commands()

    assert commands[0].startswith("REQUEST|")
    assert commands[-1].startswith("PRINT_")


def test_missing_input_directory():
    with pytest.raises(DataLoaderError):
        CSVDataLoader("data/nonexistent")


def test_missing_csv_file(tmp_path):
    loader = CSVDataLoader(tmp_path)

    with pytest.raises(DataLoaderError):
        loader.load_csv("depots.csv")


def test_unsupported_csv_file():
    loader = CSVDataLoader(INPUT_DIR)

    with pytest.raises(DataLoaderError):
        loader.load_csv("unknown.csv")
