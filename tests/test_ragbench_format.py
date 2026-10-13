import importlib.util
from pathlib import Path


def test_ragbench_parser():
    file = Path(__file__).resolve().parents[1] / "scripts" / "eval_ragbench.py"
    spec = importlib.util.spec_from_file_location("eval_ragbench_test", file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    claims, ev = mod.prepare_record({"id": "abc", "response": "Alice visited Paris.",
                                    "documents": ["Alice visited Paris in 2020."]}, max_docs=2)
    assert claims == ["Alice visited Paris."]
    assert ev[0].source.startswith("ragbench:abc")
