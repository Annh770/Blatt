"""Lightweight pre-AI guard rails for Blatt searches.

The original implementation hard-coded railway specific keywords and
looked for must-have terms such as "testing" or "validation" inside the
user description. That coupling made the guard unusable for other
domains and often filtered out good candidates before the AI analyzer
could score them.

The current version keeps the interface compatible but introduces three
principles:

1. **Dynamic concepts** – use user-provided keywords (or explicitly
   supplied concept dictionaries) to decide what should be matched.
2. **Optional scenario tags** – description keywords such as
   "testing" or "validation" are captured to help downstream
   classification, but they never gate the result.
3. **Gentle filtering** – only the absence of most concepts or explicit
   "avoid" terms will stop a paper from continuing to the AI scoring
   stage.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Iterable, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

ConceptInput = Union[str, Sequence[str], dict]


class HardRequirementsChecker:
    """Lightweight helper that guards the AI scoring stage.

    The checker now focuses on two things only:
    * does the paper roughly cover the concepts the user asked for?
    * does it contain any explicit "avoid" terms?

    Scenario keywords extracted from the description are returned as part
    of the reason string so that the UI can display tags, but they no
    longer influence gating.
    """

    def __init__(self, min_match_ratio: float = 0.6):
        # 60% coverage by default – this leaves room for the AI analyzer
        # to recover borderline cases while still removing obvious noise.
        self.min_match_ratio = max(0.0, min(1.0, min_match_ratio))
        self.scenario_keywords = {
            "training": ["training", "learning"],
            "testing": ["testing", "test", "benchmark"],
            "validation": ["validation", "verify", "evaluation"],
            "simulation": ["simulation", "simulator", "virtual"],
            "dataset": ["dataset", "data set", "corpus", "benchmark"],
            "visualization": ["visualization", "visualisation", "render"],
        }

    def check_priority5_eligibility(
        self,
        paper_title: str,
        paper_abstract: str,
        user_keywords: str,
        user_description: str = "",
        required_concepts: Optional[Sequence[ConceptInput]] = None,
        avoid_terms: Optional[Sequence[str]] = None,
    ) -> Tuple[bool, int, str]:
        """Return whether a paper should advance to AI scoring.

        Args:
            paper_title: Paper title
            paper_abstract: Paper abstract
            user_keywords: User supplied keywords string
            user_description: Optional free-form description
            required_concepts: Optional explicit concept definitions. Each
                entry can be a string (single phrase), a sequence of
                synonyms, or a dict with ``name`` and ``synonyms`` keys.
            avoid_terms: Terms that should immediately disqualify a
                result if they appear in the paper text.
        """

        paper_text = f"{paper_title} {paper_abstract or ''}".lower()
        scenario_tags = self._extract_scenario_tags(user_description)
        normalized_avoid = [term.lower() for term in (avoid_terms or [])]

        avoid_hit = self._contains_avoid_term(paper_text, normalized_avoid)
        if avoid_hit:
            return False, 2, f"❌ Contains excluded term: {avoid_hit}"

        concepts = self._resolve_concepts(required_concepts, user_keywords)
        if not concepts:
            return True, 5, self._format_reason(0, 0, scenario_tags, "No explicit concept constraints")

        matched = self._count_matched_concepts(paper_text, concepts)
        min_required = self._min_required_matches(len(concepts))

        if matched >= min_required:
            return True, 5, self._format_reason(matched, len(concepts), scenario_tags)

        if matched >= max(1, min_required - 1):
            return True, 4, self._format_reason(
                matched,
                len(concepts),
                scenario_tags,
                note="Partial concept match (relaxed)"
            )

        # Bottom tier: allow entry to AI as long as any concept matches, avoid empty candidate set
        if matched > 0:
            return True, 3, self._format_reason(
                matched,
                len(concepts),
                scenario_tags,
                note="Few concepts matched (baseline candidate)"
            )

        return True, 3, self._format_reason(
            matched,
            len(concepts),
            scenario_tags,
            note="AI-only judgment (gatekeeper baseline)"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_concepts(
        self,
        explicit: Optional[Sequence[ConceptInput]],
        user_keywords: str,
    ) -> List[Tuple[str, List[str]]]:
        """Build a concept list from explicit input or user keywords."""

        if explicit:
            concepts: List[Tuple[str, List[str]]] = []
            for item in explicit:
                if isinstance(item, str):
                    concepts.append((item, [item]))
                elif isinstance(item, dict):
                    name = item.get("name") or ",".join(item.get("synonyms", []))
                    synonyms = list(item.get("synonyms", [])) or ([name] if name else [])
                    if name:
                        concepts.append((name, synonyms))
                else:
                    synonyms = [str(term) for term in item if term]
                    if synonyms:
                        concepts.append((synonyms[0], synonyms))
            return concepts

        phrases = [phrase.strip() for phrase in re.split(r",|;|\n", user_keywords) if phrase.strip()]
        return [(phrase, [phrase]) for phrase in phrases]

    def _count_matched_concepts(self, paper_text: str, concepts: Sequence[Tuple[str, List[str]]]) -> int:
        matched = 0
        for _, synonym_list in concepts:
            if any(self._phrase_in_text(paper_text, synonym) for synonym in synonym_list):
                matched += 1
        return matched

    def _min_required_matches(self, concept_count: int) -> int:
        if concept_count == 0:
            return 0
        minimum = math.ceil(concept_count * self.min_match_ratio)
        return max(1, minimum)

    def _contains_avoid_term(self, paper_text: str, avoid_terms: Sequence[str]) -> Optional[str]:
        for term in avoid_terms:
            if term and term in paper_text:
                return term
        return None

    def _phrase_in_text(self, paper_text: str, phrase: str) -> bool:
        phrase = phrase.lower().strip()
        if not phrase:
            return False
        if " " in phrase:
            return phrase in paper_text
        pattern = rf"\b{re.escape(phrase)}\w*\b"
        return re.search(pattern, paper_text) is not None

    def _extract_scenario_tags(self, description: str) -> List[str]:
        description_lower = (description or "").lower()
        tags = [
            tag for tag, keywords in self.scenario_keywords.items()
            if any(keyword in description_lower for keyword in keywords)
        ]
        return tags

    def _format_reason(
        self,
        matched: int,
        total: int,
        scenario_tags: Sequence[str],
        note: str = "",
    ) -> str:
        tags = ", ".join(scenario_tags) if scenario_tags else "None"
        parts = [f"Concept coverage: {matched}/{total}", f"Scenario tags: {tags}"]
        if note:
            parts.append(note)
        return " | ".join(parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    checker = HardRequirementsChecker()
    sample_title = "Scenario-Based Validation of Automated Train Systems Using a 3D Virtual Railway Environment"
    sample_abstract = "This paper presents a 3D virtual railway environment for testing automation..."
    print(
        checker.check_priority5_eligibility(
            sample_title,
            sample_abstract,
            "3D worlds, autonomous rail vehicles",
            "technologies for creating 3D worlds for training and validation"
        )
    )
