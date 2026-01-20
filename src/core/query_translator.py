"""
Claude Intelligent Query Translator - Bridge between user intent and academic paper search

Core Features:
1. Understand the complete semantics of user input (not just keywords, but intent)
2. Translate colloquial/general descriptions into professional terminology used in academic papers
3. Generate multiple precise query combinations, searching from different angles
4. Avoid irrelevant papers caused by over-generalization

Example:
User input: "technology 3d worlds for autonomous rail vehicles"
Translated:
  - "virtual environment railway automation testing validation"
  - "simulation platform autonomous train digital twin"
  - "3D visualization train control system safety"

Effect:
- Found railway simulation papers ✓
- Avoided underwater robot papers ✗
"""
import re
from typing import Dict, List, Optional, Tuple, Sequence
import logging
import json
from string import Template

logger = logging.getLogger(__name__)

TRANSLATION_PROMPT_TEMPLATE = Template("""
You are a research assistant skilled in academic search. Please translate the user's input into a structured search plan.

User Input:
Keywords: $KEYWORDS
Description: $DESCRIPTION

Please strictly follow these steps to output JSON:
1. Semantic Decomposition (Dynamic Concepts)
   - Identify the user's objects/domains, technologies/methods, research purposes/scenarios, each as an independent concept.
   - Concepts are divided into primary (from keywords, hard requirements) and secondary (from description, for supplementary scenarios).
   - The concept count m is determined by semantics, could be 2, 3 or more. Don't split complete phrases (e.g., "autonomous rail vehicles").
   - If description mentions training/testing/validation/evaluation/scenario/simulation, must generate at least one secondary concept, e.g., "training & validation".
   - Each concept formatted as {"name": "...", "synonyms": ["...", "..."], "level": "primary|secondary"}, with at least 2 synonyms.
2. Professional Terms List: List 5-10 terms commonly used in paper titles, covering methods, domains, scenarios, data, etc.
3. Avoid Terms: List 5-8 similar domains to exclude (e.g., automotive, drones, etc.).
4. Generate 12-15 Query Combinations:
   - Each query has 2-4 precise terms, including focus and weight (0.5-1.0).
   - Query types must cover: domain+core tech≥2, method≥2, application≥3, data≥2, tool≥1, perception≥1, scenario≥1, synthetic data≥1, transfer≥1, survey≥1.
   - All queries must focus on identified domain, strictly no irrelevant domain terms.
5. Reasoning: Explain the basis for concept decomposition, primary/secondary distinction, and how queries cover all requirements.

Output JSON (no extra text):
{
  "semantic_understanding": "...",
  "professional_terms": ["..."],
  "core_concepts": [
    {"name": "...", "synonyms": ["...", "..."], "level": "primary"}
  ],
  "query_combinations": [
    {"query": "term1 term2", "focus": "...", "weight": 1.0}
  ],
  "avoid_terms": ["..."],
  "reasoning": "..."
}

Example (Railway):
- Input: "3D worlds, autonomous rail vehicles", description contains testing/validation.
- core_concepts:
  [{"name": "3D/virtual environment", "synonyms": ["3D", "virtual environment", "digital twin"], "level": "primary"},
   {"name": "autonomous rail vehicles", "synonyms": ["driverless train", "railway automation"], "level": "primary"},
   {"name": "training & validation", "synonyms": ["training", "testing", "validation", "scenario"], "level": "secondary"}]
- Missing any primary concept → cannot be Priority 5; secondary missing → max Priority 4.

Example (Medical):
- Input: "deep learning, medical imaging", description emphasizes diagnosis.
- core_concepts:
  [{"name": "deep learning", "synonyms": ["deep learning", "neural network"], "level": "primary"},
   {"name": "medical imaging", "synonyms": ["medical imaging", "radiology", "MRI"], "level": "primary"},
   {"name": "diagnosis", "synonyms": ["diagnosis", "detection", "classification"], "level": "secondary"}]
- Missing any primary concept → not Priority 5; secondary missing → Priority 4.
""")


class QueryTranslator:
    """
    Claude Intelligent Query Translator

    Acts as a "translator" between users and paper search APIs, converting
    user's colloquial input into professional terminology and query combinations
    actually used in academic papers
    """

    def __init__(self, claude_client=None):
        """
        Initialize query translator

        Args:
            claude_client: ClaudeClient instance (required)
        """
        self.claude_client = claude_client

    def translate(self, keywords: str, description: str = "") -> Dict[str, any]:
        """
        Translate user input into academic queries

        Args:
            keywords: User input keywords
            description: User additional description

        Returns:
            {
                "original_input": "original input",
                "semantic_understanding": "semantic understanding",
                "professional_terms": ["term1", "term2", ...],
                "query_combinations": [
                    {
                        "query": "query string 1",
                        "focus": "focus description",
                        "weight": 1.0  # importance weight
                    },
                    ...
                ],
                "avoid_terms": ["terms to avoid"],  # help filter irrelevant results
                "reasoning": "translation reasoning"
            }
        """
        if not self.claude_client:
            logger.error("❌ Claude API not configured, cannot perform intelligent translation")
            # Return simple fallback result
            return self._fallback_translation(keywords, description)

        logger.info(f"🌐 Starting to translate user query: '{keywords}'")
        if description:
            logger.info(f"   Description: '{description}'")

        try:
            result = self._call_claude_translate(keywords, description)

            # Validate return result
            if not result.get("query_combinations"):
                logger.warning("⚠️  Claude returned empty query combinations, using fallback")
                return self._fallback_translation(keywords, description)

            num_queries = len(result.get("query_combinations", []))
            fallback_terms = result.get("professional_terms") or self._split_keywords(keywords)
            result["core_concepts"] = self._normalize_core_concepts(
                result.get("core_concepts"),
                fallback_terms
            )

            num_terms = len(result.get("professional_terms", []))

            logger.info(f"✅ Translation complete:")
            logger.info(f"   - Professional terms: {num_terms}")
            logger.info(f"   - Query combinations: {num_queries}")
            logger.info(f"   - Semantic understanding: {result.get('semantic_understanding', 'N/A')}")

            # Display generated queries (for debugging)
            for i, qc in enumerate(result.get("query_combinations", [])[:3], 1):
                logger.info(f"   Query {i}: {qc.get('query', '')} (focus: {qc.get('focus', '')})")

            return result

        except Exception as e:
            logger.error(f"❌ Query translation failed: {e}")
            return self._fallback_translation(keywords, description)

    def _call_claude_translate(self, keywords: str, description: str) -> Dict:
        """
        Call Claude API for query translation

        Use carefully designed prompt to let Claude act as a "translator"
        """

        prompt = TRANSLATION_PROMPT_TEMPLATE.safe_substitute(
            KEYWORDS=keywords,
            DESCRIPTION=description if description else "None"
        )

        # Call Claude API
        response = self.claude_client.call_api(
            prompt=prompt,
            max_tokens=1500,  # Need more tokens for detailed query combinations
            temperature=0.3  # Lower temperature for stable and precise output
        )

        # Parse JSON response
        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # Try to extract JSON part
            logger.warning("⚠️  Claude returned non-pure JSON, trying to extract...")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("Unable to parse Claude response as JSON")

    def _fallback_translation(self, keywords: str, description: str) -> Dict:
        """
        Fallback solution when Claude API is unavailable

        Use simple rules to generate basic queries
        """
        logger.warning("⚠️  Using fallback translation solution")

        # Simple tokenization
        words = re.findall(r'\b\w+\b', keywords)
        if description:
            desc_words = re.findall(r'\b\w+\b', description)
            words.extend(desc_words[:5])  # Take at most 5 description words

        # Deduplicate and filter stop words
        stop_words = {'the', 'a', 'an', 'for', 'and', 'or', 'in', 'on', 'at', 'to'}
        words = [w for w in words if w.lower() not in stop_words]
        unique_words = []
        seen = set()
        for w in words:
            if w.lower() not in seen:
                unique_words.append(w)
                seen.add(w.lower())

        # Generate single query
        query = ' '.join(unique_words[:8])  # Max 8 words

        fallback_concepts = self._normalize_core_concepts(
            [],
            unique_words[:5]
        )

        return {
            "original_input": keywords,
            "semantic_understanding": "Simple rule analysis (Claude API not configured)",
            "professional_terms": unique_words[:10],
            "query_combinations": [
                {
                    "query": query,
                    "focus": "Basic keyword combination",
                    "weight": 1.0
                }
            ],
            "core_concepts": fallback_concepts,
            "avoid_terms": [],
            "reasoning": "Claude API not configured, using simple rules to generate queries"
        }

    def get_top_queries(self, translation_result: Dict, top_n: int = 3) -> List[str]:
        """
        Extract Top N query strings from translation result

        Args:
            translation_result: Result returned by translate()
            top_n: Number of queries to return

        Returns:
            List of query strings
        """
        query_combinations = translation_result.get("query_combinations", [])

        # Sort by weight
        sorted_queries = sorted(
            query_combinations,
            key=lambda x: x.get("weight", 0.5),
            reverse=True
        )

        # Extract query strings
        queries = [qc.get("query", "") for qc in sorted_queries[:top_n]]

        return [q for q in queries if q]  # Filter empty strings

    def _split_keywords(self, keywords: str) -> List[str]:
        segments = re.split(r'[,;\\n]', keywords or "")
        return [seg.strip() for seg in segments if seg.strip()]

    def _normalize_core_concepts(
        self,
        raw_concepts: Optional[List],
        fallback_terms: Sequence[str]
    ) -> List[Dict[str, List[str]]]:
        """
        Normalize core_concepts, ensure each concept has name and synonyms
        """
        normalized: List[Dict[str, List[str]]] = []

        items = raw_concepts or []
        for item in items:
            name = ""
            synonyms: List[str] = []
            level = ""
            if isinstance(item, dict):
                name = (item.get("name") or "").strip()
                synonyms = [s.strip() for s in item.get("synonyms", []) if s and s.strip()]
                level = (item.get("level") or "primary").strip().lower()
            elif isinstance(item, str):
                name = item.strip()
                synonyms = [name] if name else []
                level = "primary"
            elif isinstance(item, (list, tuple)):
                values = [str(s).strip() for s in item if s]
                if values:
                    name = values[0]
                    synonyms = values
                    level = "primary"

            if not synonyms and name:
                synonyms = [name]

            if synonyms:
                normalized.append({
                    "name": name or synonyms[0],
                    "synonyms": synonyms,
                    "level": "primary" if level not in {"primary", "secondary"} else level
                })

        if not normalized:
            fallback = [term.strip() for term in fallback_terms if term and term.strip()]
            for term in fallback[:3]:
                normalized.append({"name": term, "synonyms": [term], "level": "primary"})

        return normalized


# ==================== Demo and Testing ====================

def demo_query_translator():
    """Demo query translator (requires Claude API)"""
    print("\n" + "="*80)
    print("🌐 Claude Intelligent Query Translator - Demo")
    print("="*80)

    translator = QueryTranslator()

    test_cases = [
        ("technology 3d worlds for autonomous rail vehicles",
         "training, testing and validation"),

        ("validation, testing, simulation",
         "autonomous driving"),

        ("deep learning computer vision",
         "object detection in images"),
    ]

    print("\n[Test Cases]")
    for keywords, description in test_cases:
        print(f"\nUser Input:")
        print(f"  Keywords: {keywords}")
        print(f"  Description: {description}")
        print(f"\n  → Claude API configuration required to see translation results")

    print("\n💡 Tip: Configure CLAUDE_API_KEY to use intelligent translation feature")
    print("="*80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    demo_query_translator()
