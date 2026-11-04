"""Keyword hints: document type and urgent letters (brief A3, B6; SPEC §4.10). Pure function, no AI.

Lists come from the user's config (`keywords.doc_types`, `keywords.urgent`) and replace the defaults.
Whole words only, case-insensitive; a German compound such as "Mietvertrag" is not split, so it gives no
"Vertrag" hint unless the user lists it. Hints feed the pipeline; they never decide alone (urgent → review).
"""
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hit:
    word: str
    start: int
    end: int


@dataclass
class Hits:
    doc_types: dict[str, list[Hit]] = field(default_factory=dict)
    urgent: list[Hit] = field(default_factory=list)

    def doc_type(self) -> str | None:
        """The type with the most hits; on a tie the one named first (the title is usually at the top)."""
        found = {t: h for t, h in self.doc_types.items() if h}
        if not found:
            return None
        return min(found, key=lambda t: (-len(found[t]), found[t][0].start))


def _find(text: str, words: list[str]) -> list[Hit]:
    hits = []
    for w in words:
        pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, w.split())) + r"(?!\w)"
        hits += [Hit(w, m.start(), m.end()) for m in re.finditer(pattern, text, re.IGNORECASE)]
    return sorted(hits, key=lambda h: h.start)


def scan(text: str, lists: dict) -> Hits:
    return Hits({t: _find(text, words) for t, words in lists.get("doc_types", {}).items()},
                _find(text, lists.get("urgent", [])))
