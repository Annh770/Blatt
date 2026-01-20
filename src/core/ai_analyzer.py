"""
AI Analyzer - Use Claude API for paper relevance analysis and relationship analysis

Reverted to Search 13 configuration: removed all Phase 2D-2H complex mechanisms
"""
from typing import List, Dict, Optional
import logging

from src.api.claude_client import ClaudeClient
from src.models.database import Database
from src.models.paper import Paper
from src.models.relationship import Relationship

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI analyzer for paper relevance scoring and relationship analysis"""

    def __init__(self, db: Database, claude_api_key: str):
        """
        Initialize AI analyzer

        Args:
            db: Database instance
            claude_api_key: Claude API Key
        """
        self.db = db
        self.claude_client = ClaudeClient(api_key=claude_api_key)

        logger.info("🍃 AI Analyzer initialized successfully (Search 13 configuration)")

    def score_papers(
        self,
        papers: List[Paper],
        search_id: int,
        user_keywords: str,
        user_description: str = ""
    ) -> List[Dict]:
        """
        Score papers and store in database (Search 13 configuration: no hard review, direct AI analysis)

        Args:
            papers: List of papers
            search_id: Search history ID
            user_keywords: User search keywords
            user_description: User additional description

        Returns:
            List of scoring results [{"paper_id": "...", "priority": 4, ...}, ...]
        """
        logger.info(f"\n🔍 Starting to score {len(papers)} papers (Search 13 configuration)...")
        logger.info(f"   Keywords: {user_keywords}")
        logger.info(f"   Description: {user_description}")

        all_scores = []
        batch_size = 10

        # Search 13 configuration: direct AI analysis of all papers, no hard review
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(papers) + batch_size - 1) // batch_size

            logger.info(f"\n📊 Batch {batch_num}/{total_batches} ({len(batch)} papers)...")

            # Prepare paper data
            papers_data = [
                {
                    "title": p.title,
                    "abstract": p.abstract or "No abstract available"
                }
                for p in batch
            ]

            # Call Claude API for batch analysis
            scores = self.claude_client.batch_analyze_relevance(
                papers=papers_data,
                user_keywords=user_keywords,
                user_description=user_description
            )

            # Process results and store in database
            for score in scores:
                paper_idx = score['paper_index']
                if paper_idx >= len(batch):
                    logger.warning(f"⚠️  Invalid paper_index: {paper_idx}")
                    continue

                paper = batch[paper_idx]

                score_record = {
                    'paper_id': paper.paper_id,
                    'priority': score['priority'],
                    'matched_keywords': score['matched_keywords'],
                    'domain_match': score.get('domain_match', 'general'),  # 🔧 Bug #2 fix: new field
                    'reason': score['reason']
                }

                self._post_process_score(score_record, user_keywords, user_description)

                # Store in database
                self.db.add_paper_score(
                    search_id=search_id,
                    paper_id=paper.paper_id,
                    priority=score_record['priority'],
                    matched_keywords=score_record['matched_keywords'],
                    analysis_reason=score_record['reason']
                )

                all_scores.append(score_record)

                # Log output
                priority_emoji = "⭐" * score_record['priority']
                logger.info(f"   [{priority_emoji}] {paper.title[:50]}...")

        logger.info(f"\n✅ Scoring complete! Total {len(all_scores)} papers")

        # Statistics on score distribution
        priority_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for score in all_scores:
            priority_counts[score['priority']] += 1

        logger.info(f"\n📈 Score Distribution:")
        for priority in range(5, 0, -1):
            count = priority_counts[priority]
            percentage = (count / len(all_scores) * 100) if all_scores else 0
            logger.info(f"   Priority {priority}: {count} papers ({percentage:.1f}%)")

        return all_scores

    def _post_process_score(self, score_record: Dict, user_keywords: str, user_description: str = "") -> None:
        """
        Secondary validation of Priority based on reason and matched keywords
        """
        reason = score_record.get('reason') or ''
        reason_lower = reason.lower()
        matched_keywords = score_record.get('matched_keywords') or []
        normalized_keywords = [
            kw.lower() for kw in matched_keywords if isinstance(kw, str)
        ]

        priority = score_record.get('priority', 4)
        adjustments = []

        domain_terms = ('rail', 'railway', 'train', 'metro', 'tram', 'rolling stock')
        requires_rail_domain = any(
            term in (user_keywords or '').lower() for term in domain_terms
        )
        # 🔧 Bug #3 fix: Use word boundary matching to avoid "train" matching "training"
        has_rail_keyword = any(
            any(self._contains_word(kw, term) for term in domain_terms)
            for kw in normalized_keywords
        )

        if requires_rail_domain and priority == 5 and not has_rail_keyword:
            priority = 4
            adjustments.append("Missing railway domain keyword, auto-downgraded to Priority 4")

        # 🔧 Bug #2 fix: Directly check domain_match field instead of parsing reason text
        domain_match = score_record.get('domain_match', 'general')
        if domain_match == 'mismatch':
            if priority > 4:
                priority = 4
                adjustments.append("Domain mismatch, max Priority 4")

        primary_missing_terms = ('missing primary concept', 'missing 3D', 'missing autonomous', 'missing rail', 'concept missing', 'missing core concept')
        if any(term in reason.lower() for term in primary_missing_terms) and priority > 4:
            priority = 4
            adjustments.append("Missing primary concept, auto-downgraded to Priority 4")

        if 'contains 0/' in reason.lower() or 'contains 1/' in reason.lower():
            if priority > 3:
                priority = 3
                adjustments.append("Insufficient concept hits, downgraded to Priority 3")

        if 'irrelevant' in reason.lower() and priority > 3:
            priority = 3
            adjustments.append("Marked as irrelevant, downgraded to Priority 3")

        if self._requires_scenario_keywords(user_keywords, user_description):
            scenario_terms = ('training', 'testing', 'validation', 'evaluation', 'benchmark', 'scenario')
            has_scenario = any(
                any(term in kw for term in scenario_terms) for kw in normalized_keywords
            )
            if not has_scenario and priority > 4:
                priority = 4
                adjustments.append("Missing training/testing scenario keywords, downgraded to Priority 4")

        if adjustments:
            note = " | ".join(adjustments)
            score_record['reason'] = f"{reason} | {note}" if reason else note

        score_record['priority'] = priority

    def _contains_word(self, text: str, word: str) -> bool:
        """
        🔧 Bug #3 fix: Check if text contains complete word (word boundary matching)

        Avoid substring mismatch, e.g.:
        - "train" should not match "training"
        - "train" should match "train system"
        """
        import re
        # Use word boundary \b to ensure complete word matching
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _requires_scenario_keywords(self, user_keywords: str, user_description: str) -> bool:
        text = f"{user_keywords or ''} {user_description or ''}".lower()
        scenario_terms = ('training', 'test', 'testing', 'validation', 'verify', 'evaluation', 'scenario', 'benchmark')
        return any(term in text for term in scenario_terms)

    def analyze_relationships(
        self,
        paper_pairs: List[tuple],
        update_existing: bool = True
    ) -> Dict[str, int]:
        """
        Analyze relationships between paper pairs and update database

        Args:
            paper_pairs: List of paper pairs [(source_paper, target_paper), ...]
            update_existing: Whether to update existing relationships

        Returns:
            Statistics {"analyzed": 10, "updated": 5, "skipped": 5}
        """
        logger.info(f"\n🔗 Starting to analyze {len(paper_pairs)} paper relationships...")

        stats = {
            'analyzed': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0
        }

        for source_paper, target_paper in paper_pairs:
            # Check if relationship already exists
            if not update_existing and self.db.relationship_exists(
                source_paper.paper_id, target_paper.paper_id
            ):
                stats['skipped'] += 1
                continue

            logger.info(f"   Analyzing relationship: {source_paper.title[:30]}... -> {target_paper.title[:30]}...")

            # Prepare paper data
            source_data = {
                "title": source_paper.title,
                "abstract": source_paper.abstract or "No abstract"
            }
            target_data = {
                "title": target_paper.title,
                "abstract": target_paper.abstract or "No abstract"
            }

            # Call Claude API to analyze relationship
            relationship = self.claude_client.analyze_relationship(
                source_paper=source_data,
                target_paper=target_data
            )

            if relationship:
                # Update relationship in database
                try:
                    self.db.update_relationship(
                        source_id=source_paper.paper_id,
                        target_id=target_paper.paper_id,
                        rel_type=relationship['type'],
                        rel_desc=relationship['description']
                    )
                    stats['updated'] += 1
                    stats['analyzed'] += 1

                    rel_desc = Relationship.get_type_description(relationship['type'])
                    logger.info(f"      ✅ {rel_desc}: {relationship['description']}")
                except Exception as e:
                    logger.error(f"      ❌ Failed to update relationship: {e}")
                    stats['failed'] += 1
            else:
                stats['failed'] += 1

        logger.info(f"\n✅ Relationship analysis complete!")
        logger.info(f"   Analyzed: {stats['analyzed']}")
        logger.info(f"   Updated: {stats['updated']}")
        logger.info(f"   Skipped: {stats['skipped']}")
        logger.info(f"   Failed: {stats['failed']}")

        return stats

    def get_high_priority_papers(
        self,
        search_id: int,
        min_priority: int = 3
    ) -> List[Dict]:
        """
        Get high priority papers (convenience method)

        Args:
            search_id: Search history ID
            min_priority: Minimum Priority threshold

        Returns:
            List of papers (with scoring information)
        """
        papers = self.db.get_scored_papers(search_id, min_priority)
        logger.info(f"📚 Found {len(papers)} papers with Priority >= {min_priority}")
        return papers

    def filter_and_analyze_relationships(
        self,
        search_id: int,
        min_priority: int = 3,
        max_relationships: int = 50
    ) -> Dict:
        """
        Filter high priority papers and analyze relationships between them

        Args:
            search_id: Search history ID
            min_priority: Minimum Priority threshold
            max_relationships: Maximum number of relationships to analyze

        Returns:
            {"papers": [...], "relationships_stats": {...}}
        """
        # 1. Get high priority papers
        high_priority_papers = self.get_high_priority_papers(search_id, min_priority)

        if not high_priority_papers:
            logger.warning("⚠️  No high priority papers found matching criteria")
            return {"papers": [], "relationships_stats": {}}

        # 2. Get relationships between these papers
        paper_ids = [p['paper_id'] for p in high_priority_papers]
        relationships = self.db.get_all_relationships_for_papers(paper_ids)

        logger.info(f"🔗 Found {len(relationships)} relationships")

        # 3. Select important relationships for AI analysis (limit quantity)
        important_rels = relationships[:max_relationships]

        # 4. Build paper pairs
        paper_dict = {p['paper_id']: p for p in high_priority_papers}
        paper_pairs = []

        for rel in important_rels:
            source_id = rel['source_paper_id']
            target_id = rel['target_paper_id']

            if source_id in paper_dict and target_id in paper_dict:
                # Convert from database data to Paper objects
                source_paper = Paper.from_db_dict(paper_dict[source_id])
                target_paper = Paper.from_db_dict(paper_dict[target_id])
                paper_pairs.append((source_paper, target_paper))

        # 5. Analyze relationships
        if paper_pairs:
            stats = self.analyze_relationships(paper_pairs)
        else:
            stats = {'analyzed': 0, 'updated': 0, 'skipped': 0, 'failed': 0}

        return {
            "papers": high_priority_papers,
            "relationships_stats": stats
        }


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    claude_api_key = os.getenv('CLAUDE_API_KEY')

    if not claude_api_key:
        print("❌ Please set CLAUDE_API_KEY environment variable")
        exit(1)

    print("🍃 Testing AI Analyzer\n")

    # Initialize database and analyzer
    db = Database(':memory:')
    analyzer = AIAnalyzer(db, claude_api_key)

    # Create test papers
    test_papers = [
        Paper(
            paper_id='paper1',
            title='Deep Learning for Autonomous Driving',
            authors=['John Smith'],
            year=2020,
            abstract='This paper presents a deep learning approach for autonomous vehicles.',
            doi=None,
            citation_count=100,
            url='http://example.com/1',
            venue='CVPR',
            fields_of_study=['Computer Science']
        ),
        Paper(
            paper_id='paper2',
            title='Machine Learning in Healthcare',
            authors=['Jane Doe'],
            year=2021,
            abstract='We apply machine learning to medical diagnosis.',
            doi=None,
            citation_count=50,
            url='http://example.com/2',
            venue='Nature',
            fields_of_study=['Medicine']
        )
    ]

    # Store in database
    for paper in test_papers:
        db.add_or_update_paper(paper.to_db_dict())

    # Create search history
    search_id = db.create_search_history(
        keywords="autonomous driving, deep learning",
        description="focus on autonomous vehicles"
    )

    # Test scoring
    print("=" * 60)
    print("Test: Paper Scoring")
    print("=" * 60)

    scores = analyzer.score_papers(
        papers=test_papers,
        search_id=search_id,
        user_keywords="autonomous driving, deep learning",
        user_description="focus on autonomous vehicles"
    )

    # Get high priority papers
    high_priority = analyzer.get_high_priority_papers(search_id, min_priority=3)
    print(f"\n✅ Found {len(high_priority)} high priority papers")

    print("\n🎉 Testing complete!")
