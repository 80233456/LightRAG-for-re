from dataclasses import dataclass, asdict
import re
from typing import Any


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    content: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_claims(text: str, limit: int = 5) -> list[str]:
    """Fallback splitter; research runs should audit extraction errors separately."""
    parts = re.split(r"(?<=[。！？!?；;])\s*|(?<=[.!?])\s+(?=[A-Z\"'])", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 2][:limit]


def words(text: str) -> set[str]:
    """Lightweight bilingual tokens; not a multilingual semantic evaluator."""
    return set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower()))


def overlap(query: str, context: str) -> float:
    q = words(query)
    return len(q & words(context)) / max(1, len(q))
