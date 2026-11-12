import csv

from src.main import run_application


def test_official_sample_runs_all_cycles_and_writes_reports(tmp_path):
    result = run_application("data/input", tmp_path / "out")
    assert len(result["cycles"]) == 16
    assert set(result["output_files"]) == {
        "allocations.csv", "manifests.csv", "dispatch_refusals.csv",
        "reconciliation.csv", "request_status.csv",
    }
    with open(result["output_files"]["request_status.csv"], newline="", encoding="utf-8") as stream:
        requests = list(csv.DictReader(stream))
    assert len(requests) == 182  # 180 source requests plus two automatic overflow requests.
    assert next(row for row in requests if row["request_id"] == "RQ-012")["status"] == "REJECTED"
    assert not any(error["command"] == "REQUEST|RQ-012" for error in result["command_errors"])
    assert len(result["components"]["delivery"].processed_ids) > 0
