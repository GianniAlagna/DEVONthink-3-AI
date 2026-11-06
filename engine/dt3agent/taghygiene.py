"""J-5 tag hygiene (SPEC §4.21 D4): find near-duplicate tags and propose adding the kept tag.

Near-duplicate: same tag up to case, diacritics or a plural ending, or an edit distance of at most 2 for tags of
6 or more letters. Digits must match exactly (years and numbers are different tags). The kept tag is the one in
the vocabulary, else the more frequent one, else the shorter. The result is "add tag" proposals per record; no
tag is ever removed by the engine (the user can remove the variant in DT3).
"""
import unicodedata
from collections import Counter

MAX_PROPOSALS = 50
PLURAL = ("en", "es", "n", "e", "s", "x", "i")


def _plain(tag: str) -> str:
    decomposed = unicodedata.normalize("NFKD", tag.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip()


def _stem(word: str) -> str:
    for end in PLURAL:
        if len(word) > len(end) + 3 and word.endswith(end):
            return word[: -len(end)]
    return word


def _distance(a: str, b: str, limit: int = 2) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similar(a: str, b: str) -> bool:
    if a == b:
        return False
    pa, pb = _plain(a), _plain(b)
    if [c for c in pa if c.isdigit()] != [c for c in pb if c.isdigit()]:
        return False
    if pa == pb or _stem(pa) == _stem(pb):
        return True
    return min(len(pa), len(pb)) >= 6 and _distance(pa, pb) <= 2


def proposals(seen: list[tuple[str, list[str]]], vocabulary: list[str]) -> list[tuple[str, str, str]]:
    """(uuid, kept tag, variant it has) for records that carry a variant but not the kept tag."""
    counts = Counter(t for _, tags in seen for t in set(tags))
    vocab = set(vocabulary)
    tags = sorted(set(counts) | vocab)
    kept_for = {}
    for t in counts:
        group = [o for o in tags if o == t or similar(t, o)]
        if len(group) < 2:
            continue
        kept_for[t] = sorted(group, key=lambda o: (o not in vocab, -counts.get(o, 0), len(o), o))[0]
    out = []
    for uuid, rec_tags in seen:
        for t in rec_tags:
            kept = kept_for.get(t)
            if kept and kept != t and kept not in rec_tags and (uuid, kept, t) not in out:
                out.append((uuid, kept, t))
                if len(out) == MAX_PROPOSALS:
                    return out
    return out
