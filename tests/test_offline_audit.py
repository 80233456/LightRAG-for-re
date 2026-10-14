"""Offline replay tests (no real NLI, LLM, CUDA or corpus downloads)."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from offline_audit_archive import _metrics, audit_archive


def test_recorded_metrics_do_not_count_null_queries_as_answerable():
    records = [
        {"question_type": "inference_query", "em": 1,
         "output": {"answer": "Paris", "retrieval": {"calls": 2}}},
        {"question_type": "comparison_query", "em": 0,
         "output": {"answer": "", "retrieval": {"calls": 1}}},
        {"question_type": "null_query", "em": 1,
         "output": {"answer": "", "retrieval": {"calls": 1}}}
    ]
    result = _metrics(records, "question_type")
    assert result["recorded_em"] == 0.666667
    assert result["answerable_n"] == 2
    assert result["recorded_answerable_em"] == 0.5
    assert result["recorded_answer_coverage"] == 0.333333
    assert result["recorded_mean_retrieval_calls"] == 1.333333


def test_archive_replay_keeps_metrics_historical(tmp_path):
    archive = tmp_path / "historic.zip"
    onsite = []
    multi = []
    for i in range(45):
        for variant in ("baseline", "adaptive", "verify", "full"):
            onsite.append({"split": "test", "answerable": i < 27,
                           "variant": variant, "em": 0.0,
                           "output": {"answer": "", "retrieval": {"calls": 1}}})
    for i in range(20):
        for variant in ("baseline", "adaptive", "verify", "full"):
            multi.append({"index": i, "query": "Where is the station?",
                          "question_type": "null_query" if i >= 15 else "inference_query",
                          "variant": variant, "em": 0.0, "output": {
                              "answer": "", "retrieval": {"calls": 1},
                              "evidence": [{"content": "The station is here."}]}})
    with ZipFile(archive, "w") as z:
        root = "evidencechain_experiment/results"
        z.writestr(f"{root}/onsite/records.jsonl",
                   "\n".join(json.dumps(x) for x in onsite))
        z.writestr(f"{root}/multihop_dev20/records.jsonl",
                   "\n".join(json.dumps(x) for x in multi))
    out = audit_archive(archive)
    assert out["kind"] == "historical_diagnostic_only"
    assert out["onsite_old_test"]["baseline"]["n"] == 45
    assert out["multihop_old_dev20"]["baseline"]["answerable_n"] == 15
    assert out["current_controller_trigger_probe_on_old_baseline_evidence"]["n"] == 20


def test_missing_archive_records_raise(tmp_path):
    path = tmp_path / "empty.zip"
    with ZipFile(path, "w") as z:
        z.writestr("README", "no records")
    with pytest.raises(KeyError):
        audit_archive(path)
