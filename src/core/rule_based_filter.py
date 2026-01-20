"""
Rule-Based Paper Filter - No AI API Required

Filter top N most relevant papers from candidates
Using rule-based scoring: title match + abstract match + citations + year
"""
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class RuleBasedFilter:
    """
    Rule-Based Paper Filter

    Scoring dimensions:
    1. Title keyword match (40%)
    2. Abstract keyword match (30%)
    3. Citation count (20%)
    4. Publication year (10%)
    """

    def __init__(self):
        pass

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords (tokenize and clean)"""
        # Convert to lowercase
        text = text.lower()

        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)

        # Tokenize
        words = text.split()

        # Filter short words and numbers
        keywords = [w for w in words if len(w) > 2 and not w.isdigit()]

        return keywords

    def calculate_match_score(self, paper_text: str, query_keywords: List[str],
                             original_keywords: List[str] = None,
                             expanded_keywords: List[str] = None) -> float:
        """
        Calculate text-keyword match score (supports hybrid scoring)

        Strategy:
        1. Original keyword exact match → high weight (1.0)
        2. Expanded keyword match → medium weight (0.6)
        3. Stem fuzzy match → low weight (0.3)

        Args:
            paper_text: Paper text (title or abstract)
            query_keywords: All query keywords (backward compatible)
            original_keywords: User's original input keywords (new version)
            expanded_keywords: Claude-expanded keywords (new version)

        Returns:
            Match score (0-100)
        """
        if not paper_text:
            return 0.0

        paper_text_lower = paper_text.lower()

        # If no separated keywords provided, use legacy logic
        if original_keywords is None and expanded_keywords is None:
            return self._simple_match_score(paper_text_lower, query_keywords)

        # New hybrid scoring logic
        score = 0.0
        max_score = 0.0

        # Core improvement: Check if all important keywords are present
        # Heavily penalize if long words (>5 chars) from original keywords are missing
        core_keywords_missing = 0
        core_keywords_total = 0
        if original_keywords:
            for kw in original_keywords:
                kw_lower = kw.lower().strip()
                # Long keywords are considered core concepts (e.g., "autonomous", "vehicles", "rail")
                if len(kw_lower) > 5:
                    core_keywords_total += 1
                    if kw_lower not in paper_text_lower:
                        core_keywords_missing += 1

        # If more than half of core keywords missing, return low score
        if core_keywords_total > 0 and core_keywords_missing / core_keywords_total > 0.5:
            return 5.0  # Max 5 points, avoid irrelevant papers ranking high

        # Weight 1: Original keyword exact match (weight 1.0)
        if original_keywords:
            for kw in original_keywords:
                kw_lower = kw.lower().strip()
                if kw_lower in paper_text_lower:
                    score += 1.0
                max_score += 1.0

        # Weight 2: Expanded keyword match (weight 0.6)
        if expanded_keywords:
            for kw in expanded_keywords:
                kw_lower = kw.lower().strip()
                if kw_lower in paper_text_lower:
                    score += 0.6
                max_score += 0.6

        # Weight 3: Stem fuzzy match (weight 0.3)
        # e.g., "autonomous" can match "autonome", "automation"
        all_keywords = (original_keywords or []) + (expanded_keywords or [])
        for kw in all_keywords:
            if self._fuzzy_match(kw, paper_text_lower):
                score += 0.3

        # Normalize to 0-100
        if max_score == 0:
            return 0.0

        normalized_score = (score / max_score) * 100
        return min(100, normalized_score)  # Cap at 100

    def _simple_match_score(self, paper_text_lower: str,
                            query_keywords: List[str]) -> float:
        """
        Simple match scoring (backward compatible)

        Returns:
            Match score (0-100)
        """
        if not query_keywords:
            return 0.0

        matches = 0
        for keyword in query_keywords:
            if keyword.lower() in paper_text_lower:
                matches += 1

        match_rate = matches / len(query_keywords)
        return match_rate * 100

    def _fuzzy_match(self, keyword: str, text: str) -> bool:
        """
        Fuzzy match (stem matching)

        Strategy:
        - If keyword length >= 6, match first 5 characters
        - e.g., "autonomous" stem is "auton", can match "autonome", "automation"

        Args:
            keyword: Keyword
            text: Text to match

        Returns:
            Whether fuzzy match found
        """
        keyword = keyword.lower().strip()
        if len(keyword) < 6:
            return False  # Don't fuzzy match short words

        # Extract stem (first 5 characters)
        stem = keyword[:5]

        # Check if stem is in text (as word beginning)
        import re
        pattern = r'\b' + re.escape(stem)
        return bool(re.search(pattern, text))

    def normalize_value(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0-100"""
        if max_val == min_val:
            return 50.0

        normalized = (value - min_val) / (max_val - min_val) * 100
        return max(0, min(100, normalized))

    def filter_top_papers(self, papers: List[Dict], user_keywords: str,
                         user_description: str = "", top_n: int = 10,
                         original_keywords: List[str] = None,
                         expanded_keywords: List[str] = None) -> List[Dict]:
        """
        Filter Top N relevant papers

        Args:
            papers: Candidate paper list
            user_keywords: User input keywords
            user_description: User description
            top_n: Return count

        Returns:
            Filtered paper list (with relevance_score)
        """
        if not papers:
            return []

        logger.info(f"🔍 Rule-based filtering: selecting Top {top_n} from {len(papers)} candidate papers")

        # If separated keywords provided, use new scoring
        if original_keywords or expanded_keywords:
            logger.info(f"   Original keywords: {original_keywords}")
            logger.info(f"   Expanded keywords: {expanded_keywords[:5] if expanded_keywords else []}")

            # Calculate score for each paper (new version)
            scored_papers = []
            for paper in papers:
                score = self._calculate_paper_score_v2(
                    paper, original_keywords, expanded_keywords, papers
                )
                paper_with_score = paper.copy()
                paper_with_score['relevance_score'] = score
                scored_papers.append(paper_with_score)
        else:
            # Legacy compatible logic
            all_user_text = f"{user_keywords} {user_description}"
            query_keywords = self.extract_keywords(all_user_text)

            logger.info(f"   User keywords: {query_keywords[:10]}...")  # Show only first 10

            # Calculate score for each paper (legacy)
            scored_papers = []
            for paper in papers:
                score = self._calculate_paper_score(
                    paper, query_keywords, papers
                )
                paper_with_score = paper.copy()
                paper_with_score['relevance_score'] = score
                scored_papers.append(paper_with_score)

        # Sort by score
        scored_papers.sort(key=lambda p: p['relevance_score'], reverse=True)

        # Take Top N
        top_papers = scored_papers[:top_n]

        logger.info(f"✅ Filtering complete! Top {top_n} paper score range: "
                   f"{top_papers[0]['relevance_score']:.1f} - {top_papers[-1]['relevance_score']:.1f}")

        return top_papers

    def _calculate_paper_score_v2(self, paper: Dict,
                                   original_keywords: List[str],
                                   expanded_keywords: List[str],
                                   all_papers: List[Dict]) -> float:
        """
        Calculate paper's composite score (new version - supports expanded keywords)

        Returns:
            Composite score (0-100)
        """
        # === Dimension 1: Title match (weight 40%) ===
        title = paper.get('title', '')
        title_score = self.calculate_match_score(
            title, [],
            original_keywords=original_keywords,
            expanded_keywords=expanded_keywords
        )

        # === Dimension 2: Abstract match (weight 40%) ===
        abstract = paper.get('abstract', '')
        abstract_score = self.calculate_match_score(
            abstract, [],
            original_keywords=original_keywords,
            expanded_keywords=expanded_keywords
        )

        # === Dimension 3: Citation count (weight 10%) ===
        citation_count = paper.get('citation_count', 0) or 0

        all_citations = [p.get('citation_count', 0) or 0 for p in all_papers]
        min_citations = min(all_citations) if all_citations else 0
        max_citations = max(all_citations) if all_citations else 100

        citation_score = self.normalize_value(
            citation_count, min_citations, max_citations
        )

        # === Dimension 4: Publication year (weight 10%) ===
        year = paper.get('year') or 2000

        all_years = [p.get('year') or 2000 for p in all_papers]
        min_year = min(all_years) if all_years else 2000
        max_year = max(all_years) if all_years else 2024

        year_score = self.normalize_value(year, min_year, max_year)

        # === Composite score ===
        total_score = (
            title_score * 0.40 +
            abstract_score * 0.40 +
            citation_score * 0.10 +
            year_score * 0.10
        )

        return total_score

    def _calculate_paper_score(self, paper: Dict, query_keywords: List[str],
                               all_papers: List[Dict]) -> float:
        """
        Calculate paper's composite score (legacy - backward compatible)

        Returns:
            Composite score (0-100)
        """
        # === Dimension 1: Title match (weight 40%) ===
        title = paper.get('title', '')
        title_score = self.calculate_match_score(title, query_keywords)

        # === Dimension 2: Abstract match (weight 30%) ===
        abstract = paper.get('abstract', '')
        abstract_score = self.calculate_match_score(abstract, query_keywords)

        # === Dimension 3: Citation count (weight 20%) ===
        citation_count = paper.get('citation_count', 0) or 0

        # Calculate citation range for all papers (for normalization)
        all_citations = [p.get('citation_count', 0) or 0 for p in all_papers]
        min_citations = min(all_citations) if all_citations else 0
        max_citations = max(all_citations) if all_citations else 100

        citation_score = self.normalize_value(
            citation_count, min_citations, max_citations
        )

        # === Dimension 4: Publication year (weight 10%) ===
        year = paper.get('year') or 2000

        # Recent papers score higher
        all_years = [p.get('year') or 2000 for p in all_papers]
        min_year = min(all_years) if all_years else 2000
        max_year = max(all_years) if all_years else 2024

        year_score = self.normalize_value(year, min_year, max_year)

        # === Composite score ===
        total_score = (
            title_score * 0.40 +
            abstract_score * 0.40 +
            citation_score * 0.10 +
            year_score * 0.10
        )

        return total_score


# ==================== Test and Demo ====================

def demo_rule_based_filter():
    """Demo rule-based filter"""
    print("\n" + "="*70)
    print("🧪 Rule-Based Filter - Demo")
    print("="*70)

    filter = RuleBasedFilter()

    # 模拟候选论文
    papers = [
        {
            "paper_id": "1",
            "title": "Deep Learning for Autonomous Driving Validation",
            "abstract": "We propose a novel validation framework for autonomous driving using deep learning and simulation...",
            "citation_count": 150,
            "year": 2023
        },
        {
            "paper_id": "2",
            "title": "Testing Methods in Robotics",
            "abstract": "This paper surveys testing methods in robotics systems...",
            "citation_count": 80,
            "year": 2022
        },
        {
            "paper_id": "3",
            "title": "Simulation-based Validation for Autonomous Vehicles",
            "abstract": "We present a simulation platform for validating autonomous vehicle behavior...",
            "citation_count": 200,
            "year": 2024
        },
        {
            "paper_id": "4",
            "title": "Machine Learning in Computer Vision",
            "abstract": "An overview of machine learning techniques for computer vision...",
            "citation_count": 500,
            "year": 2020
        },
        {
            "paper_id": "5",
            "title": "Autonomous Driving Testing Framework",
            "abstract": "A comprehensive testing framework for autonomous driving systems...",
            "citation_count": 120,
            "year": 2023
        }
    ]

    # User input
    user_keywords = "autonomous driving validation testing"
    user_description = "focus on simulation methods"

    print(f"\nUser input:")
    print(f"  Keywords: {user_keywords}")
    print(f"  Description: {user_description}")
    print(f"\nCandidate papers: {len(papers)}")

    # Filter Top 3
    top_papers = filter.filter_top_papers(
        papers, user_keywords, user_description, top_n=3
    )

    print(f"\nTop 3 papers:")
    for i, paper in enumerate(top_papers):
        print(f"\n{i+1}. [Score: {paper['relevance_score']:.1f}]")
        print(f"   Title: {paper['title']}")
        print(f"   Citations: {paper['citation_count']} | Year: {paper['year']}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    demo_rule_based_filter()
