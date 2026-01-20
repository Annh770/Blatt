"""
Citation Network Expander - Automatically expands paper citation relationship networks
"""
from typing import List, Dict, Set, Optional
import logging
from datetime import datetime

from src.api.semantic_scholar import SemanticScholarClient
from src.models.database import Database
from src.models.paper import Paper
from src.models.relationship import Relationship

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CitationExpander:
    """Citation network expander"""

    def __init__(self, db: Database, s2_api_key: Optional[str] = None):
        """
        Initialize expander

        Args:
            db: Database instance
            s2_api_key: Semantic Scholar API Key (optional)
        """
        self.db = db
        self.s2_client = SemanticScholarClient(api_key=s2_api_key)

    def expand(
        self,
        seed_papers: List[Paper],
        depth: int = 1,
        citation_limit: int = 10,
        reference_limit: int = 10,
        min_citation_count: int = 0,
        year_from: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Expand citation network

        Args:
            seed_papers: Initial paper list (seed papers)
            depth: Expansion depth (1=1 level only, 2=2 levels)
            citation_limit: Number of citing papers to get per paper
            reference_limit: Number of references to get per paper
            min_citation_count: Minimum citation count filter
            year_from: Year filter (only keep papers after this year)

        Returns:
            {
                'papers': List[Paper],           # All papers (including seed papers)
                'relationships': List[Dict],     # All relationships
                'stats': Dict                    # Statistics
            }
        """
        logger.info(f"🍃 Starting citation network expansion")
        logger.info(f"   Seed papers: {len(seed_papers)}")
        logger.info(f"   Expansion depth: {depth} levels")
        logger.info(f"   Per paper: {citation_limit} citing + {reference_limit} references")
        if year_from:
            logger.info(f"   Year filter: >= {year_from}")

        # All papers dictionary (paper_id -> Paper)
        all_papers_dict = {p.paper_id: p for p in seed_papers}

        # Set of processed paper IDs (avoid duplicate processing)
        processed_ids = set()

        # All relationships list
        all_relationships = []

        # Current level papers
        current_level_papers = seed_papers.copy()

        # Statistics
        stats = {
            'initial_papers': len(seed_papers),
            'total_papers': len(seed_papers),
            'total_relationships': 0,
            'papers_per_level': [len(seed_papers)],
            'skipped_by_year': 0,
            'skipped_by_citations': 0
        }

        # Expand level by level
        for level in range(depth):
            logger.info(f"\n📊 Expanding level {level + 1}...")
            logger.info(f"   Current level papers: {len(current_level_papers)}")

            next_level_papers = []
            level_new_papers = 0
            level_relationships = 0

            for paper in current_level_papers:
                # Skip already processed papers
                if paper.paper_id in processed_ids:
                    continue

                logger.info(f"   Processing paper: {paper.title[:50]}...")

                # 1. Get citing papers (papers that cite this paper)
                citing_papers = self._get_citing_papers(
                    paper,
                    limit=citation_limit,
                    min_citation_count=min_citation_count,
                    year_from=year_from
                )

                for citing_paper in citing_papers:
                    # Add new paper
                    if citing_paper.paper_id not in all_papers_dict:
                        all_papers_dict[citing_paper.paper_id] = citing_paper
                        next_level_papers.append(citing_paper)
                        level_new_papers += 1

                    # Record relationship: citing_paper cites paper
                    relationship = {
                        'source_paper_id': citing_paper.paper_id,
                        'target_paper_id': paper.paper_id,
                        'relationship_type': Relationship.TYPE_CITES,
                        'relationship_desc': None
                    }
                    all_relationships.append(relationship)
                    level_relationships += 1

                    # Store in database
                    self.db.add_relationship(
                        citing_paper.paper_id,
                        paper.paper_id,
                        Relationship.TYPE_CITES
                    )

                # 2. Get references (papers this paper cites)
                cited_papers = self._get_cited_papers(
                    paper,
                    limit=reference_limit,
                    min_citation_count=min_citation_count,
                    year_from=year_from
                )

                for cited_paper in cited_papers:
                    # Add new paper
                    if cited_paper.paper_id not in all_papers_dict:
                        all_papers_dict[cited_paper.paper_id] = cited_paper
                        next_level_papers.append(cited_paper)
                        level_new_papers += 1

                    # Record relationship: paper cites cited_paper
                    relationship = {
                        'source_paper_id': paper.paper_id,
                        'target_paper_id': cited_paper.paper_id,
                        'relationship_type': Relationship.TYPE_CITES,
                        'relationship_desc': None
                    }
                    all_relationships.append(relationship)
                    level_relationships += 1

                    # Store in database
                    self.db.add_relationship(
                        paper.paper_id,
                        cited_paper.paper_id,
                        Relationship.TYPE_CITES
                    )

                # Mark as processed
                processed_ids.add(paper.paper_id)

            # Update statistics
            stats['papers_per_level'].append(level_new_papers)
            stats['total_papers'] += level_new_papers
            stats['total_relationships'] += level_relationships

            logger.info(f"✅ Level {level + 1} complete")
            logger.info(f"   New papers: {level_new_papers}")
            logger.info(f"   New relationships: {level_relationships}")

            # Next level
            current_level_papers = next_level_papers

            # If no new papers, end early
            if not next_level_papers:
                logger.info(f"   No more papers to expand, ending early")
                break

        # Summarize results
        all_papers = list(all_papers_dict.values())

        logger.info(f"\n🎉 Citation network expansion complete!")
        logger.info(f"   Total papers: {stats['total_papers']}")
        logger.info(f"   Total relationships: {stats['total_relationships']}")
        logger.info(f"   Papers per level: {stats['papers_per_level']}")

        return {
            'papers': all_papers,
            'relationships': all_relationships,
            'stats': stats
        }

    def matches_any_query(self, paper_dict: Dict, translated_queries: List[Dict]) -> bool:
        """
        Check if paper matches any query (Phase 2I)

        Args:
            paper_dict: Paper dict from S2 API (contains title and abstract)
            translated_queries: Query list from query_translator
                                Format: [{"query": "autonomous train simulation", "strategy": "..."}]

        Returns:
            True if paper matches any query (AND logic within each query)

        Principle:
        - Iterate through each query
        - For each query, extract keywords and check if ALL are in the paper (AND logic)
        - Return True if any query matches
        """
        title = (paper_dict.get('title') or '').lower()
        abstract = (paper_dict.get('abstract') or '').lower()
        text = f"{title} {abstract}"

        for query_obj in translated_queries:
            query = query_obj.get('query', '').lower()

            # Extract keywords from query (simple tokenization, remove common stop words)
            stop_words = {'for', 'and', 'or', 'in', 'on', 'at', 'to', 'the', 'a', 'an', 'of', 'with', 'by'}
            query_words = [w.strip() for w in query.split() if w.strip() and w.strip() not in stop_words]

            # AND logic: all keywords must appear
            if all(word in text for word in query_words):
                logger.debug(f"      ✓ Matched query: {query}")
                return True

        return False

    def expand_with_query_filtering(
        self,
        seed_papers: List[Paper],
        translated_queries: List[Dict],
        depth: int = 1,
        per_paper_limit: int = 10,
        global_limit: int = 200,
        year_from: Optional[int] = None,
        min_citation_count: int = 0
    ) -> Dict[str, any]:
        """
        Citation network expansion with query-based intelligent filtering (Phase 2I core improvement)

        Args:
            seed_papers: Seed paper list (Priority 5 or Priority 4 papers)
            translated_queries: Semantic expansion queries from query_translator
            depth: Expansion depth (usually 1)
            per_paper_limit: Max citing/reference count per paper (default 10)
            global_limit: Global paper count limit (default 200)
            year_from: Year filter
            min_citation_count: Minimum citation count

        Returns:
            {
                'papers': [Paper object list],
                'relationships': [Relationship list],
                'stats': {Statistics}
            }

        Improvement strategy:
        1. Get 100 candidate citing papers from S2
        2. Use translated_queries to filter matching papers
        3. Sort by citation_count and take top per_paper_limit
        4. Global total not exceeding global_limit
        """
        logger.info(f"🔍 Starting query-based intelligent expansion (Phase 2I)")
        logger.info(f"   Seed papers: {len(seed_papers)}")
        logger.info(f"   Query count: {len(translated_queries)}")
        logger.info(f"   Per paper limit: {per_paper_limit} | Global limit: {global_limit}")

        all_papers = {}
        all_relationships = []
        papers_seen = set()
        global_count = 0

        # Initialize seed papers
        for paper in seed_papers:
            all_papers[paper.paper_id] = paper
            papers_seen.add(paper.paper_id)

        # Expand to specified depth
        current_level = seed_papers

        for level in range(depth):
            logger.info(f"\n📊 Level {level + 1} expansion starting (current papers: {len(current_level)})")
            next_level_papers = []
            level_stats = {'citing': 0, 'references': 0, 'filtered': 0}

            for i, paper in enumerate(current_level):
                if global_count >= global_limit:
                    logger.info(f"   ⚠️  Reached global limit {global_limit}, stopping expansion")
                    break

                logger.info(f"   [{i+1}/{len(current_level)}] Expanding: {paper.title[:50]}...")

                # 1. Get citing papers (papers that cite this paper)
                try:
                    # Get 100 candidates from S2
                    raw_citing = self.s2_client.get_citations(paper.paper_id, limit=100)

                    # Query filtering
                    matched_citing = []
                    for raw_paper in raw_citing:
                        if self.matches_any_query(raw_paper, translated_queries):
                            matched_citing.append(raw_paper)

                    # Sort by citation count and limit
                    matched_citing.sort(key=lambda x: x.get('citationCount', 0), reverse=True)
                    matched_citing = matched_citing[:per_paper_limit]

                    logger.info(f"      Citing: {len(raw_citing)} candidates → {len(matched_citing)} matched")
                    level_stats['citing'] += len(matched_citing)

                    # Convert and store
                    for raw_paper in matched_citing:
                        if global_count >= global_limit:
                            break

                        citing_paper = Paper.from_s2_dict(raw_paper)

                        # Year and citation count filter
                        if year_from and citing_paper.year and citing_paper.year < year_from:
                            continue
                        if citing_paper.citation_count < min_citation_count:
                            continue

                        if citing_paper.paper_id not in papers_seen:
                            papers_seen.add(citing_paper.paper_id)
                            all_papers[citing_paper.paper_id] = citing_paper
                            next_level_papers.append(citing_paper)
                            global_count += 1

                            # Store in database
                            self.db.add_or_update_paper(citing_paper.to_db_dict())

                        # Record relationship
                        all_relationships.append({
                            'source_paper_id': citing_paper.paper_id,
                            'target_paper_id': paper.paper_id,
                            'relationship_type': 'cites'
                        })
                        self.db.add_relationship(
                            citing_paper.paper_id,
                            paper.paper_id,
                            'cites'
                        )

                except Exception as e:
                    logger.error(f"      Failed to get citing papers: {e}")

                # 2. Get references (papers this paper cites)
                if global_count < global_limit:
                    try:
                        # Get 100 candidates from S2
                        raw_refs = self.s2_client.get_references(paper.paper_id, limit=100)

                        # Query filtering
                        matched_refs = []
                        for raw_paper in raw_refs:
                            if self.matches_any_query(raw_paper, translated_queries):
                                matched_refs.append(raw_paper)

                        # Sort by citation count and limit
                        matched_refs.sort(key=lambda x: x.get('citationCount', 0), reverse=True)
                        matched_refs = matched_refs[:per_paper_limit]

                        logger.info(f"      References: {len(raw_refs)} candidates → {len(matched_refs)} matched")
                        level_stats['references'] += len(matched_refs)

                        # Convert and store
                        for raw_paper in matched_refs:
                            if global_count >= global_limit:
                                break

                            ref_paper = Paper.from_s2_dict(raw_paper)

                            # Year and citation count filter
                            if year_from and ref_paper.year and ref_paper.year < year_from:
                                continue
                            if ref_paper.citation_count < min_citation_count:
                                continue

                            if ref_paper.paper_id not in papers_seen:
                                papers_seen.add(ref_paper.paper_id)
                                all_papers[ref_paper.paper_id] = ref_paper
                                next_level_papers.append(ref_paper)
                                global_count += 1

                                # Store in database
                                self.db.add_or_update_paper(ref_paper.to_db_dict())

                            # Record relationship
                            all_relationships.append({
                                'source_paper_id': paper.paper_id,
                                'target_paper_id': ref_paper.paper_id,
                                'relationship_type': 'cites'
                            })
                            self.db.add_relationship(
                                paper.paper_id,
                                ref_paper.paper_id,
                                'cites'
                            )

                    except Exception as e:
                        logger.error(f"      Failed to get references: {e}")

            logger.info(f"   ✅ Level {level + 1} complete:")
            logger.info(f"      Citing: {level_stats['citing']} papers")
            logger.info(f"      References: {level_stats['references']} papers")
            logger.info(f"      Total papers: {len(all_papers)}")

            current_level = next_level_papers

        # Return results
        logger.info(f"\n✅ Expansion complete!")
        logger.info(f"   Total papers: {len(all_papers)}")
        logger.info(f"   Total relationships: {len(all_relationships)}")

        return {
            'papers': list(all_papers.values()),
            'relationships': all_relationships,
            'stats': {
                'total_papers': len(all_papers),
                'total_relationships': len(all_relationships),
                'seed_papers': len(seed_papers),
                'queries_used': len(translated_queries)
            }
        }

    def _get_citing_papers(
        self,
        paper: Paper,
        limit: int = 10,
        min_citation_count: int = 0,
        year_from: Optional[int] = None
    ) -> List[Paper]:
        """
        Get papers that cite this paper (citing papers)

        Args:
            paper: The cited paper
            limit: Limit on number to get
            min_citation_count: Minimum citation count
            year_from: Year filter

        Returns:
            List of papers
        """
        try:
            raw_papers = self.s2_client.get_citations(paper.paper_id, limit=limit * 2)  # Get more, filter later
            papers = []

            for raw_paper in raw_papers:
                # Convert to Paper object
                citing_paper = Paper.from_s2_dict(raw_paper)

                # Filter conditions
                if citing_paper.citation_count < min_citation_count:
                    continue
                if year_from and citing_paper.year and citing_paper.year < year_from:
                    continue

                papers.append(citing_paper)

                # Store in database
                self.db.add_or_update_paper(citing_paper.to_db_dict())

                # Stop when reaching limit
                if len(papers) >= limit:
                    break

            logger.info(f"      Got citing papers: {len(papers)}")
            return papers

        except Exception as e:
            logger.error(f"      Failed to get citing papers ({paper.paper_id}): {e}")
            return []

    def _get_cited_papers(
        self,
        paper: Paper,
        limit: int = 10,
        min_citation_count: int = 0,
        year_from: Optional[int] = None
    ) -> List[Paper]:
        """
        Get papers this paper cites (references/cited papers)

        Args:
            paper: The citing paper
            limit: Limit on number to get
            min_citation_count: Minimum citation count
            year_from: Year filter

        Returns:
            List of papers
        """
        try:
            raw_papers = self.s2_client.get_references(paper.paper_id, limit=limit * 2)
            papers = []

            for raw_paper in raw_papers:
                # Convert to Paper object
                cited_paper = Paper.from_s2_dict(raw_paper)

                # Filter conditions
                if cited_paper.citation_count < min_citation_count:
                    continue
                if year_from and cited_paper.year and cited_paper.year < year_from:
                    continue

                papers.append(cited_paper)

                # Store in database
                self.db.add_or_update_paper(cited_paper.to_db_dict())

                # Stop when reaching limit
                if len(papers) >= limit:
                    break

            logger.info(f"      Got references: {len(papers)}")
            return papers

        except Exception as e:
            logger.error(f"      Failed to get references ({paper.paper_id}): {e}")
            return []

    def expand_from_paper_ids(
        self,
        paper_ids: List[str],
        **kwargs
    ) -> Dict[str, any]:
        """
        Expand from paper ID list (convenience method)

        Args:
            paper_ids: List of paper IDs
            **kwargs: Other parameters passed to expand()

        Returns:
            Expansion results
        """
        # Get paper objects from database
        seed_papers = []
        for paper_id in paper_ids:
            paper_dict = self.db.get_paper_by_id(paper_id)
            if paper_dict:
                paper = Paper.from_db_dict(paper_dict)
                seed_papers.append(paper)
            else:
                logger.warning(f"⚠️  Paper {paper_id} not in database, skipping")

        if not seed_papers:
            logger.error("❌ No valid seed papers found")
            return {
                'papers': [],
                'relationships': [],
                'stats': {'error': 'No valid seed papers'}
            }

        return self.expand(seed_papers, **kwargs)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    api_key = os.getenv('SEMANTIC_SCHOLAR_API_KEY')

    # Test citation network expander
    print("🍃 Testing citation network expander")

    # Initialize database
    db = Database(':memory:')

    # Create expander
    expander = CitationExpander(db, s2_api_key=api_key)

    # Create test paper
    test_paper = Paper(
        paper_id='649def34f8be52c8b66281af98ae884c09aef38b',  # A classic autonomous driving paper
        title='End to End Learning for Self-Driving Cars',
        authors=['Mariusz Bojarski'],
        year=2016,
        abstract='Test abstract',
        doi=None,
        citation_count=3000,
        url='https://example.com',
        venue='arXiv',
        fields_of_study=['Computer Science']
    )

    # Store in database
    db.add_or_update_paper(test_paper.to_db_dict())

    print(f"\nTest paper: {test_paper.title}")
    print(f"Starting expansion...")

    # Expand (1 level only, 5 citations each)
    result = expander.expand(
        seed_papers=[test_paper],
        depth=1,
        citation_limit=5,
        reference_limit=5,
        year_from=2015
    )

    print(f"\n✅ Expansion complete!")
    print(f"   Total papers: {len(result['papers'])}")
    print(f"   Total relationships: {len(result['relationships'])}")
    print(f"   Statistics: {result['stats']}")
