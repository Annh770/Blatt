"""
Smart Query Builder - Rule Engine Version (No AI API required)

Features:
1. Identify parallel keywords (comma, semicolon, and/or separated)
2. Generate multiple query combinations
3. Intelligent keyword extraction

Note: Search papers in the same language as user input (no auto-translation)
"""
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class SmartQueryBuilder:
    """
    Smart Query Builder (Rule Engine)

    Features:
    - Free, fast (no AI API cost)
    - Identify parallel keywords
    - Generate multiple query combinations
    - Search papers in same language as user input
    """

    def __init__(self):
        # Stop words (for filtering descriptions)
        self.stop_words = {
            'focus', 'on', 'the', 'a', 'an', 'in', 'of', 'for', 'to',
            'with', 'about', 'related', 'regarding', 'concerning', 'using',
            'based', 'via', 'from', 'by', 'at', 'is', 'are', 'was', 'were',
            # German stop words
            'der', 'die', 'das', 'des', 'dem', 'den', 'von', 'für', 'mit',
            # Chinese stop words (not added for now, requires tokenization)
        }

    def parse_parallel_keywords(self, text: str) -> List[str]:
        """
        Parse parallel keywords

        Recognition patterns:
        - Comma separated: "validation, testing, simulation"
        - Semicolon separated: "A; B; C"
        - And connected: "validation and testing"
        - Or connected: "validation or testing"
        - Slash separated: "validation/testing"

        Returns:
            Keyword list
        """
        if not text:
            return []

        # Replace conjunctions with commas
        text = re.sub(r'\s+and\s+', ',', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+or\s+', ',', text, flags=re.IGNORECASE)
        text = re.sub(r'[;/]', ',', text)

        # Split and clean
        keywords = [k.strip() for k in text.split(',') if k.strip()]

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        if len(unique_keywords) > 1:
            logger.info(f"📝 Identified {len(unique_keywords)} parallel keywords: {unique_keywords}")

        return unique_keywords

    def extract_important_terms(self, description: str, max_terms: int = 8) -> List[str]:
        """
        Extract important terms from description

        Strategy:
        1. Split by punctuation
        2. Filter stop words
        3. Keep top N most important (increased to 8 to avoid missing important info)

        Returns:
            Important terms list
        """
        if not description:
            return []

        # Split by punctuation
        phrases = re.split(r'[,;、]', description)

        important = []
        for phrase in phrases:
            phrase = phrase.strip().lower()

            # Remove leading stop words
            words = phrase.split()
            while words and words[0] in self.stop_words:
                words.pop(0)

            if words:
                clean_phrase = ' '.join(words)
                # Avoid very short words (like single letters)
                if len(clean_phrase) > 2:
                    important.append(clean_phrase)

        # Limit count
        result = important[:max_terms]

        if result:
            logger.info(f"📝 Extracted important terms: {result}")

        return result

    def build_query_combinations(self, keywords: str, description: str = "",
                                 max_combinations: int = 8) -> List[Dict[str, str]]:
        """
        Build multiple query combinations (no translation version)

        Strategy:
        1. Identify parallel keywords
        2. Extract important terms
        3. Generate various combinations

        Returns:
            Query list: [{"query": "...", "strategy": "...", "description": "..."}]
        """
        queries = []

        # === Step 1: Identify parallel keywords ===
        parallel_main = self.parse_parallel_keywords(keywords)
        parallel_desc = self.parse_parallel_keywords(description)

        # Extract important terms from description (increased to 8 to avoid missing)
        important_terms = self.extract_important_terms(description, max_terms=8)

        # If description has parallel terms, add to important terms
        if parallel_desc:
            important_terms.extend(parallel_desc[:5])  # Increased to 5
            # Deduplicate
            seen = set()
            important_terms = [t for t in important_terms
                             if not (t.lower() in seen or seen.add(t.lower()))]

        # === Step 2: Generate query combinations ===

        # Strategy 1: Core keywords query (avoid too long)
        # Only use keywords, exclude full description (avoid too long query causing S2 no results)
        queries.append({
            "query": keywords,
            "strategy": "core",
            "description": "Core keywords"
        })

        # Strategy 2: Core keywords + first important term
        if important_terms:
            core_query = f"{keywords} {important_terms[0]}"
            queries.append({
                "query": core_query,
                "strategy": "core",
                "description": f"Core query + main term"
            })

        # Strategy 3: Split parallel keywords (if multiple keywords)
        if len(parallel_main) > 1:
            logger.info(f"📝 Found {len(parallel_main)} parallel keywords, generating split queries")
            for kw in parallel_main:
                if important_terms:
                    # Each keyword + first important term
                    combo = f"{kw} {important_terms[0]}"
                else:
                    # Only keyword
                    combo = kw

                queries.append({
                    "query": combo,
                    "strategy": "split",
                    "description": f"Split query: {kw}"
                })

        # Strategy 4: Parallel keywords + parallel terms combination (fine search)
        if len(parallel_main) > 1 and len(parallel_desc) > 1:
            logger.info(f"📝 Found parallel keywords and terms, generating cross combinations")
            # Match each keyword with a term
            for i, kw in enumerate(parallel_main[:3]):  # Max 3 keywords
                if i < len(parallel_desc):
                    combo = f"{kw} {parallel_desc[i]}"
                    queries.append({
                        "query": combo,
                        "strategy": "cross",
                        "description": f"Cross combination: {kw} + {parallel_desc[i]}"
                    })

        # Strategy 5: Only core keywords (most relaxed)
        queries.append({
            "query": keywords,
            "strategy": "minimal",
            "description": "Minimal query (keywords only)"
        })

        # === Deduplicate and limit count ===
        seen_queries = set()
        unique_queries = []
        for q in queries:
            query_lower = q["query"].lower().strip()
            if query_lower not in seen_queries and len(query_lower) > 2:
                seen_queries.add(query_lower)
                unique_queries.append(q)

                # Stop when reaching limit
                if len(unique_queries) >= max_combinations:
                    break

        logger.info(f"🎯 Generated {len(unique_queries)} query combinations")
        for i, q in enumerate(unique_queries):
            logger.info(f"   {i+1}. [{q['strategy']:8s}] {q['query']}")

        return unique_queries

    def build_simple_query(self, keywords: str, description: str = "") -> str:
        """
        Build simple query (single query string, backward compatible)

        Strategy: Keywords + first important term
        """
        # Extract important terms from description
        important = self.extract_important_terms(description, max_terms=1)

        if important:
            query = f"{keywords} {important[0]}"
        elif description:
            query = f"{keywords} {description}"
        else:
            query = keywords

        logger.info(f"🎯 Simple query: {query}")
        return query


# ==================== Test and Demo ====================

def demo_smart_query_builder():
    """Demo smart query builder (no translation version)"""
    print("\n" + "="*70)
    print("🧪 Smart Query Builder - Demo (No Translation Version)")
    print("="*70)

    builder = SmartQueryBuilder()

    # Test case 1: English parallel keywords
    print("\n[Case 1] English parallel keywords")
    print("Input:")
    print("  keywords: 'validation, testing, simulation'")
    print("  description: 'autonomous driving safety'")

    queries = builder.build_query_combinations(
        "validation, testing, simulation",
        "autonomous driving safety"
    )

    print(f"\nGenerated {len(queries)} queries:")
    for i, q in enumerate(queries):
        print(f"  {i+1}. [{q['strategy']:8s}] {q['query']}")

    # Test case 2: Parallel keywords + parallel description
    print("\n[Case 2] Parallel keywords + parallel description (fine search)")
    print("Input:")
    print("  keywords: 'validation, testing, simulation'")
    print("  description: 'autonomous driving, robotics, UAV'")

    queries = builder.build_query_combinations(
        "validation, testing, simulation",
        "autonomous driving, robotics, UAV"
    )

    print(f"\nGenerated {len(queries)} queries:")
    for i, q in enumerate(queries):
        print(f"  {i+1}. [{q['strategy']:8s}] {q['query']}")

    # Test case 3: Simple query
    print("\n[Case 3] Simple single keyword")
    print("Input:")
    print("  keywords: 'neural architecture search'")
    print("  description: 'focus on efficient methods'")

    queries = builder.build_query_combinations(
        "neural architecture search",
        "focus on efficient methods"
    )

    print(f"\nGenerated {len(queries)} queries:")
    for i, q in enumerate(queries):
        print(f"  {i+1}. [{q['strategy']:8s}] {q['query']}")

    print("\n" + "="*70)
    print("✅ Demo complete!")
    print("\n💡 Note: Search papers in the same language as user input")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    demo_smart_query_builder()
