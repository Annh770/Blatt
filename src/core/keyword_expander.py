"""
Intelligent Keyword Expander - Uses Claude API

Features:
1. Detect if user input contains generic terms (technology, method, approach, etc.)
2. Use Claude API to expand generic terms into specific professional terminology
3. Support multi-language input, maintain original language output
"""
import re
from typing import Dict, List, Optional
import logging
import json

logger = logging.getLogger(__name__)


class KeywordExpander:
    """
    Intelligent Keyword Expander

    Uses Claude API to expand user-input generic keywords into specific professional terminology
    """

    # Generic terms list (signal words that need expansion)
    GENERIC_TERMS = {
        # English
        'technology', 'technologies', 'technique', 'techniques',
        'method', 'methods', 'approach', 'approaches',
        'solution', 'solutions', 'system', 'systems',
        'tool', 'tools', 'framework', 'frameworks',
        'algorithm', 'algorithms',

        # German
        'technologie', 'technologien', 'methode', 'methoden',
        'ansatz', 'ansätze', 'verfahren', 'lösung', 'lösungen',

        # French
        'technologie', 'technologies', 'méthode', 'méthodes',
        'approche', 'approches', 'solution', 'solutions',
    }

    def __init__(self, claude_client=None):
        """
        Initialize keyword expander

        Args:
            claude_client: ClaudeClient instance (optional)
        """
        self.claude_client = claude_client

    def needs_expansion(self, keywords: str) -> bool:
        """
        Detect if keywords need expansion

        Strategy:
        1. Check if contains generic terms
        2. Check if too few keywords (<3 words)

        Args:
            keywords: User-input keywords

        Returns:
            Whether expansion is needed
        """
        if not keywords:
            return False

        keywords_lower = keywords.lower()
        words = re.findall(r'\b\w+\b', keywords_lower)

        # Check if contains generic terms
        has_generic = any(term in words for term in self.GENERIC_TERMS)

        # Check if too few keywords (less than 3 substantive words)
        has_few_keywords = len(words) < 3

        should_expand = has_generic or has_few_keywords

        if should_expand:
            logger.info(f"🔍 Expansion needed: generic_terms={has_generic}, few_keywords={has_few_keywords}")

        return should_expand

    def expand(self, keywords: str, description: str = "") -> Dict[str, any]:
        """
        Expand keywords

        Args:
            keywords: User-input keywords
            description: User supplementary description

        Returns:
            {
                "original_keywords": ["technology", "3D", "railway"],
                "expanded_keywords": ["LiDAR", "point cloud", "autonomous train", ...],
                "all_keywords": [...],  # original + expanded
                "reasoning": "Expanded 'technology' to specific computer vision technologies"
            }
        """
        if not self.claude_client:
            logger.warning("⚠️  Claude API not configured, skipping keyword expansion")
            return {
                "original_keywords": self._extract_keywords(keywords),
                "expanded_keywords": [],
                "all_keywords": self._extract_keywords(keywords),
                "reasoning": "Claude API not configured, expansion skipped"
            }

        logger.info(f"🤖 Starting keyword expansion: {keywords}")

        # Call Claude API
        try:
            result = self._call_claude_expand(keywords, description)

            original = self._extract_keywords(keywords)
            expanded = result.get("expanded_keywords", [])

            # Merge original and expanded keywords (deduplicate)
            all_kws = original.copy()
            for kw in expanded:
                if kw.lower() not in [k.lower() for k in all_kws]:
                    all_kws.append(kw)

            logger.info(f"✅ Expansion complete: {len(original)} → {len(all_kws)} keywords")
            logger.info(f"   Expanded: {expanded[:5]}...")

            return {
                "original_keywords": original,
                "expanded_keywords": expanded,
                "all_keywords": all_kws,
                "reasoning": result.get("reasoning", "")
            }

        except Exception as e:
            logger.error(f"❌ Keyword expansion failed: {e}")
            # Return original keywords on failure
            return {
                "original_keywords": self._extract_keywords(keywords),
                "expanded_keywords": [],
                "all_keywords": self._extract_keywords(keywords),
                "reasoning": f"Expansion failed: {e}"
            }

    def _call_claude_expand(self, keywords: str, description: str) -> Dict:
        """
        Call Claude API to expand keywords

        Returns:
            {
                "expanded_keywords": ["kw1", "kw2", ...],
                "reasoning": "Expansion reasoning"
            }
        """
        prompt = f"""You are an academic research assistant. The user is searching for academic papers, but their keywords may be too generic or not professional enough.

User input:
Keywords: {keywords}
Description: {description if description else "None"}

Please help the user expand their keywords for more precise search. Requirements:

1. **Identify generic terms**: If contains "technology", "method", "approach" etc., replace with specific technology names, algorithms, or tools in that domain

2. **Add synonyms and related terms**:
   - Professional terminology (e.g. "3D" → "point cloud", "mesh", "reconstruction")
   - Technology names (e.g. "autonomous" → "SLAM", "sensor fusion")
   - Domain keywords (e.g. "railway" + "3D" → "track detection", "infrastructure modeling")

3. **Maintain original language**:
   - If user inputs English, output English terms
   - If user inputs German, output German terms
   - Do not translate, keep input language

4. **Generate 5-8 expanded keywords**, sorted by relevance

5. **Output JSON format**:
{{
    "expanded_keywords": ["specific_term1", "specific_term2", "specific_term3", ...],
    "reasoning": "Brief explanation of expansion approach (1-2 sentences)"
}}

Important: Only output JSON, no other explanation."""

        # Call Claude API
        response = self.claude_client.call_api(
            prompt=prompt,
            max_tokens=500,
            temperature=0.3  # Lower temperature for stable output
        )

        # Parse JSON response
        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # If not pure JSON, try to extract
            logger.warning("Claude returned non-JSON format, attempting extraction...")
            # Try to extract JSON part
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("Cannot parse Claude response as JSON")

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text (tokenization)

        Returns:
            Keyword list
        """
        if not text:
            return []

        # Split by comma, semicolon
        parts = re.split(r'[,;、]', text)

        keywords = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 1:
                keywords.append(part)

        # If no punctuation separators, split by space
        if not keywords:
            words = text.split()
            keywords = [w.strip() for w in words if len(w.strip()) > 1]

        return keywords


# ==================== Demo and Test ====================

def demo_keyword_expander():
    """Demo keyword expander"""
    print("\n" + "="*70)
    print("🧪 Intelligent Keyword Expander - Demo")
    print("="*70)

    # Requires actual Claude API for testing
    # Only demonstrating detection logic here

    expander = KeywordExpander()

    test_cases = [
        "technology 3D railway",
        "deep learning neural networks",
        "autonome Fahrzeug Technologie",
        "validation, testing, simulation"
    ]

    print("\n[Checking if expansion needed]")
    for keywords in test_cases:
        needs = expander.needs_expansion(keywords)
        print(f"  '{keywords}' → {'Needs expansion ✓' if needs else 'No expansion ✗'}")

    print("\n💡 Note: Claude API configuration required for actual keyword expansion")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    demo_keyword_expander()
