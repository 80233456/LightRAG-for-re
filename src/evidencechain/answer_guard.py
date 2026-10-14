"""Conservative short-answer / supported-claim anchoring.

This is a lexical invariant, NOT a semantic entailment model. It rejects a
mismatched answer even when the independent claims are well-grounded. More
complex paraphrases may require a separately evaluated semantic check.
"""
from __future__ import annotations
import re

_PARTS = re.compile(r"[,，、;；\n]+")
_TRIM = " \t\n\r\"'“”‘’。，.！!？?；;：:、()（）[]【】"
_ENGLISH_NEGATION = re.compile(
    r"\b(?:not|never|neither|nor|without|isn't|wasn't|weren't|didn't|doesn't)\b(?:\W+\w+){0,3}\W*$", re.I)
_CHINESE_NEGATION = re.compile(r"(?:不是|并非|而非|非|没有|未在|不在|不含|除外|并不).{0,5}$")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip(_TRIM)).strip()


def _valid_mention(piece: str, claim: str) -> bool:
    if not piece or not claim:
        return False
    if piece.isdigit():
        edge = r"(?<![a-z0-9_])" + re.escape(piece) + r"(?![a-z0-9_])"
    elif re.fullmatch(r"[a-z0-9_ -]+", piece, re.I):
        edge = r"(?<![\w])" + re.escape(piece) + r"(?![\w])"
    else:
        edge = re.escape(piece)
    pattern = re.compile(edge, re.I)
    for found in pattern.finditer(claim):
        prefix = claim[max(0, found.start() - 44):found.start()]
        if not _ENGLISH_NEGATION.search(prefix) and not _CHINESE_NEGATION.search(prefix[-12:]):
            return True
    return False


def answer_anchored_in_claims(answer: str, claims: list[str]) -> bool:
    """Require ALL short answer parts to be affirmed within one claim.

    Deliberately conservative: not proof that the claim answers the question.
    """
    if not isinstance(answer, str) or not answer.strip() or not claims:
        return False
    pieces = [_normalize(x) for x in _PARTS.split(answer) if _normalize(x)]
    if not pieces or len(pieces) > 6:
        return False
    for claim in claims:
        normalized = _normalize(claim)
        if all(_valid_mention(piece, normalized) for piece in pieces):
            return True
    return False
