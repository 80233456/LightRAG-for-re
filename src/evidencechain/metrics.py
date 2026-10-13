"""Fixed, public metric code. No gold labels are used in inference decisions."""
import re
from collections import Counter


def tokens(text: str) -> list[str]:
    """Simple English/Chinese tokenizer: document language and normalization in report."""
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower().strip())


def answer_em(prediction: str, gold: str) -> float:
    return float(tokens(prediction) == tokens(gold))


def answer_f1(prediction: str, gold: str) -> float:
    a, b = Counter(tokens(prediction)), Counter(tokens(gold))
    common = sum((a & b).values())
    if not a and not b:
        return 1.0
    if not a or not b or not common:
        return 0.0
    precision, recall = common / sum(a.values()), common / sum(b.values())
    return 2 * precision * recall / (precision + recall)


def binary_metrics(actual: list[bool], predicted: list[bool]) -> dict:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("expected nonempty equal-sized inputs")
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    return {"n": len(actual), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "accuracy": (tp + tn) / len(actual), "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / max(1e-10, prec + rec),
            "false_accept_rate": fp / max(1, fp + tn)}


def fact_recall(evidence_texts: list[str], gold_facts: list[str]) -> float | None:
    """Strict string inclusion after whitespace removal (proxy, not semantic recall)."""
    if not gold_facts:
        return None
    normalize = lambda s: re.sub(r"\s+", "", s).lower()
    retrieved = [normalize(x) for x in evidence_texts]
    return sum(any(normalize(f) in chunk for chunk in retrieved) for f in gold_facts) / len(gold_facts)
