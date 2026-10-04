"""Cost attribution must include rejects without double counting candidate IDs."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path


def test_report_keeps_round_identity_and_allocates_all_source_cost(tmp_path):
    script = Path(__file__).parents[1] / "scripts/model_lab/report.py"
    spec = importlib.util.spec_from_file_location("private_lab_report", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = tmp_path / "B/runs/fixture"
    delivery = run / "production/delivery"
    delivery.mkdir(parents=True)
    clips = []
    for label in ("round-1", "round-2"):
        media = run / "renders" / label / "candidate-00.mp4"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"fixture media")
        clips.append(
            {
                "path": str(media),
                "duration_seconds": 22,
                "candidate": {"candidate_id": 0, "title": "Fixture", "excerpt": "Une fin."},
                "judge": {"reasons": []},
            }
        )
    (delivery / "fixture.json").write_text(
        json.dumps({"source": {"id": "fixture"}, "clips": clips})
    )
    requests = [
        {"source": "fixture", "charged_or_reserved_usd": amount, "candidate_key": key}
        for amount, key in (
            ("0.10", "round-1/00"),
            ("0.20", "round-2/00"),
            ("0.30", "round-1/07"),
            ("0.40", None),
        )
    ]
    (run / "cost_ledger.json").write_text(
        json.dumps({"charged_or_reserved_usd": "1.00", "requests": requests})
    )
    module.export(tmp_path)
    report = json.loads((tmp_path / "COMPARISON.json").read_text())
    assert not report["complete"]
    assert [Decimal(c["direct_api_usd"]) for c in report["clips"]] == [
        Decimal("0.10"),
        Decimal("0.20"),
    ]
    assert sum(Decimal(c["allocated_api_usd"]) for c in report["clips"]) == Decimal("1.00")

    c_run = tmp_path / "C/runs/fixture"
    c_delivery = c_run / "production/delivery"
    c_delivery.mkdir(parents=True)
    c_clips = [
        {**clips[0], "premium_qualified": True},
        {**clips[1], "premium_qualified": False, "diagnostic": True},
    ]
    (c_delivery / "fixture.json").write_text(
        json.dumps({"source": {"id": "fixture"}, "clips": c_clips})
    )
    (c_run / "cost_ledger.json").write_text(
        json.dumps(
            {
                "cap_usd": "2.00",
                "charged_or_reserved_usd": "0.50",
                "requests": [
                    {
                        "source": "fixture",
                        "charged_or_reserved_usd": "0.50",
                        "candidate_key": None,
                        "accounting": "provider_reported",
                    }
                ],
            }
        )
    )
    module.export(tmp_path)
    report = json.loads((tmp_path / "COMPARISON.json").read_text())
    assert report["costs_usd"]["B"] == "1.00"
    assert report["costs_usd"]["C"] == "0.50"
    assert report["total_charged_or_reserved_usd"] == "1.50"
    assert report["editorial_qualified"] == {"B": 0, "C": 1}
    assert len([c for c in report["clips"] if c["method"] == "C"]) == 2
    assert sum(
        Decimal(c["allocated_api_usd"]) for c in report["clips"] if c["method"] == "C"
    ) == Decimal("0.50")
