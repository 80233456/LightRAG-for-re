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


def test_ragbench_uses_actual_adherence_label():
    import importlib.util
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / 'scripts' / 'eval_ragbench.py'
    spec = importlib.util.spec_from_file_location('ragbench_label_test', f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.support_label({'adherence_score': True}) is True
    assert mod.support_label({'adherence_score': False}) is False
    assert mod.support_label({'overall_supported': True}) is True
    assert mod.support_label({'adherence_score': None}) is None


def test_ragbench_rejects_string_label():
    import importlib.util
    from pathlib import Path
    import pytest
    f = Path(__file__).resolve().parents[1] / 'scripts' / 'eval_ragbench.py'
    spec = importlib.util.spec_from_file_location('ragbench_invalid_label_test', f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(ValueError):
        mod.support_label({'adherence_score': 'false'})
