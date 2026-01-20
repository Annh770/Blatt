"""
Multi-Source Unified Searcher - Integrates Semantic Scholar + arXiv + CrossRef
Automatically selects optimal data sources for robust and comprehensive paper retrieval
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import List, Dict, Optional
import logging

from src.api.semantic_scholar import SemanticScholarClient
from src.api.arxiv_client import ArxivClient
from src.api.crossref_client import CrossRefClient
from src.models.database import Database
from src.models.paper import Paper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiSourceSearcher:
    """Multi-source paper searcher"""

    def __init__(self, db: Database, s2_api_key: Optional[str] = None):
        """
        Initialize multi-source searcher

        Args:
            db: Database instance
            s2_api_key: Semantic Scholar API Key (optional)
        """
        self.db = db

        # Initialize three data sources
        self.s2_client = SemanticScholarClient(api_key=s2_api_key)
        self.arxiv_client = ArxivClient()
        self.crossref_client = CrossRefClient()

        logger.info("📚 Multi-source searcher initialized")
        logger.info("   - Semantic Scholar (AI/CS coverage)")
        logger.info("   - arXiv (preprints)")
        logger.info("   - CrossRef (cross-disciplinary, includes IEEE/Springer)")

    def search(self, keywords: str, description: str = "",
               limit: int = 10, year_from: Optional[int] = None,
               sources: List[str] = None) -> List[Paper]:
        """
        Multi-source paper search (with automatic deduplication)

        Args:
            keywords: Search keywords
            description: Additional description (optional)
            limit: Number of papers to return
            year_from: Starting year (optional)
            sources: List of data sources, defaults to ['s2', 'crossref', 'arxiv']

        Returns:
            List of Paper objects (deduplicated)
        """
        # Default to using all data sources
        if sources is None:
            sources = ['s2', 'crossref', 'arxiv']

        query = self._build_query(keywords, description)
        all_papers = []
        paper_ids_seen = set()  # For deduplication

        logger.info(f"🔍 Starting multi-source search: '{query}'")
        logger.info(f"   Sources: {', '.join(sources)}")

        # Search each data source by priority
        for source in sources:
            try:
                papers = self._search_source(source, query, limit, year_from)

                # Deduplicate and add
                for paper in papers:
                    # Use title + first author as deduplication key
                    dedup_key = f"{paper.title}_{paper.first_author}".lower()

                    if dedup_key not in paper_ids_seen:
                        paper_ids_seen.add(dedup_key)
                        all_papers.append(paper)

                        # Store in database
                        self.db.add_or_update_paper(paper.to_db_dict())

                logger.info(f"   ✅ {source.upper()}: Found {len(papers)} papers (after dedup: {len(all_papers)})")

            except Exception as e:
                logger.warning(f"   ⚠️  {source.upper()} search failed: {e}")
                continue

        # Sort by citation count
        all_papers.sort(key=lambda p: p.citation_count or 0, reverse=True)

        # Limit return count
        result = all_papers[:limit]

        logger.info(f"✅ Multi-source search complete! Found {len(result)} papers")
        return result

    def _search_source(self, source: str, query: str,
                      limit: int, year_from: Optional[int]) -> List[Paper]:
        """
        Search a single data source

        Args:
            source: Data source name ('s2', 'arxiv', 'crossref')
            query: Search query
            limit: Return count
            year_from: Starting year

        Returns:
            List of Paper objects
        """
        raw_papers = []

        if source == 's2':
            raw_papers = self.s2_client.search_papers(
                query=query,
                limit=limit,
                year_from=year_from
            )
        elif source == 'arxiv':
            raw_papers = self.arxiv_client.search_papers(
                query=query,
                limit=limit
            )
        elif source == 'crossref':
            raw_papers = self.crossref_client.search_papers(
                query=query,
                limit=limit,
                year_from=year_from
            )
        else:
            logger.warning(f"Unknown data source: {source}")
            return []

        # Convert to Paper objects
        papers = []
        for raw_paper in raw_papers:
            try:
                paper = Paper.from_s2_dict(raw_paper)

                # Abstract completion: if no abstract but has DOI, try to get from S2
                if not paper.abstract and paper.doi:
                    try:
                        s2_data = self.s2_client.get_paper_by_doi(paper.doi)
                        if s2_data and s2_data.get('abstract'):
                            paper.abstract = s2_data['abstract']
                            logger.info(f"✅ Abstract completed: {paper.title[:40]}...")
                    except Exception as e:
                        logger.debug(f"Abstract completion failed: {e}")

                papers.append(paper)
            except Exception as e:
                logger.warning(f"Paper parsing failed: {e}")
                continue

        return papers

    def search_by_priority(self, keywords: str, description: str = "",
                          limit: int = 10, year_from: Optional[int] = None) -> List[Paper]:
        """
        Priority search strategy: S2 first, then supplement with CrossRef and arXiv

        Args:
            keywords: Search keywords
            description: Additional description
            limit: Target paper count
            year_from: Starting year

        Returns:
            List of Paper objects
        """
        query = self._build_query(keywords, description)
        papers = []
        paper_ids_seen = set()

        logger.info(f"🔍 Priority search: '{query}'")

        # 1. Try Semantic Scholar first
        try:
            logger.info("   Trying Semantic Scholar...")
            s2_papers = self._search_source('s2', query, limit, year_from)

            for paper in s2_papers:
                dedup_key = f"{paper.title}_{paper.first_author}".lower()
                if dedup_key not in paper_ids_seen:
                    paper_ids_seen.add(dedup_key)
                    papers.append(paper)
                    self.db.add_or_update_paper(paper.to_db_dict())

            logger.info(f"   ✅ S2: {len(papers)} papers")

        except Exception as e:
            logger.warning(f"   ⚠️  S2 failed: {e}")

        # 2. If insufficient, supplement with CrossRef
        if len(papers) < limit:
            try:
                remaining = limit - len(papers)
                logger.info(f"   Trying CrossRef (need {remaining} more)...")

                crossref_papers = self._search_source('crossref', query, remaining, year_from)

                for paper in crossref_papers:
                    dedup_key = f"{paper.title}_{paper.first_author}".lower()
                    if dedup_key not in paper_ids_seen:
                        paper_ids_seen.add(dedup_key)
                        papers.append(paper)
                        self.db.add_or_update_paper(paper.to_db_dict())

                logger.info(f"   ✅ CrossRef: +{len(papers) - len(paper_ids_seen)} papers")

            except Exception as e:
                logger.warning(f"   ⚠️  CrossRef failed: {e}")

        # 3. If still insufficient, supplement with arXiv
        if len(papers) < limit:
            try:
                remaining = limit - len(papers)
                logger.info(f"   Trying arXiv (need {remaining} more)...")

                arxiv_papers = self._search_source('arxiv', query, remaining, None)

                for paper in arxiv_papers:
                    dedup_key = f"{paper.title}_{paper.first_author}".lower()
                    if dedup_key not in paper_ids_seen:
                        paper_ids_seen.add(dedup_key)
                        papers.append(paper)
                        self.db.add_or_update_paper(paper.to_db_dict())

                logger.info(f"   ✅ arXiv: +{len(papers) - len(paper_ids_seen)} papers")

            except Exception as e:
                logger.warning(f"   ⚠️  arXiv failed: {e}")

        # Sort by citation count
        papers.sort(key=lambda p: p.citation_count or 0, reverse=True)

        logger.info(f"✅ Priority search complete! Total {len(papers)} papers")
        return papers[:limit]

    def _detect_priority_sources(self, query_info: Dict[str, str]) -> List[str]:
        """
        Determine data source priority based on query type (Phase 2H - Domain-Agnostic)

        Args:
            query_info: Query info dict containing "query" and optional "strategy"/"focus"

        Returns:
            List of data sources in priority order

        Principle (universal):
        - Implementation queries (framework, dataset, tool) → arXiv first (preprints update faster)
        - Survey queries (survey, review) → Semantic Scholar first (complete citation data)
        - Default → Semantic Scholar first (high quality)
        """
        query = query_info.get("query", "").lower()
        focus = query_info.get("focus", "").lower()
        strategy = query_info.get("strategy", "").lower()

        # Implementation type → arXiv first
        implementation_keywords = ['framework', 'dataset', 'benchmark', 'tool', 'platform', 'library']
        if any(kw in query or kw in focus or kw in strategy for kw in implementation_keywords):
            return ['arxiv', 's2', 'crossref']

        # Survey type → S2 first
        survey_keywords = ['survey', 'review', 'state-of-the-art', 'overview']
        if any(kw in query or kw in focus or kw in strategy for kw in survey_keywords):
            return ['s2', 'crossref', 'arxiv']

        # Default → S2 first
        return ['s2', 'arxiv', 'crossref']

    def search_with_multiple_queries(self, query_list: List[Dict[str, str]],
                                    papers_per_query: int = 20,
                                    total_limit: int = 100,
                                    year_from: Optional[int] = None,
                                    sources: List[str] = None,
                                    dynamic_source_priority: bool = True) -> List[Paper]:
        """
        Search using multiple queries in parallel (core feature!)

        Args:
            query_list: List of queries [{"query": "...", "strategy": "..."}]
            papers_per_query: Papers per query (default 20, Phase 2A optimized)
            total_limit: Total paper limit (default 100, Phase 2A optimized)
            year_from: Starting year
            sources: Data source list (if provided, overrides dynamic priority)
            dynamic_source_priority: Enable dynamic source priority (Phase 2H)

        Returns:
            Deduplicated list of papers
        """
        all_papers = []
        paper_ids_seen = set()

        logger.info(f"🔍 Multi-query parallel search: {len(query_list)} queries")
        if dynamic_source_priority and sources is None:
            logger.info(f"   💡 Dynamic source priority enabled (Phase 2H)")

        for i, query_info in enumerate(query_list):
            query = query_info["query"]
            strategy = query_info.get("strategy", "unknown")

            # Phase 2H: Dynamically determine data source priority
            if sources is None and dynamic_source_priority:
                query_sources = self._detect_priority_sources(query_info)
                logger.info(f"   Query {i+1}/{len(query_list)} [{strategy:8s}]: {query}")
                logger.info(f"      → Sources: {' > '.join(query_sources)}")
            else:
                query_sources = sources if sources else ['s2', 'crossref', 'arxiv']
                logger.info(f"   Query {i+1}/{len(query_list)} [{strategy:8s}]: {query}")

            # Search for each query
            try:
                for source in query_sources:
                    papers = self._search_source(source, query, papers_per_query, year_from)

                    for paper in papers:
                        dedup_key = f"{paper.title}_{paper.first_author}".lower()

                        if dedup_key not in paper_ids_seen:
                            paper_ids_seen.add(dedup_key)
                            all_papers.append(paper)

                            # Store in database
                            self.db.add_or_update_paper(paper.to_db_dict())

                            # Stop when reaching total limit
                            if len(all_papers) >= total_limit:
                                logger.info(f"   ✅ Reached paper limit ({total_limit}), stopping search")
                                break

                    if len(all_papers) >= total_limit:
                        break

            except Exception as e:
                logger.warning(f"   ⚠️  Query failed: {e}")
                continue

            if len(all_papers) >= total_limit:
                break

        # Sort by citation count
        all_papers.sort(key=lambda p: p.citation_count or 0, reverse=True)

        logger.info(f"✅ Multi-query search complete! Found {len(all_papers)} papers (deduplicated)")

        return all_papers[:total_limit]

    def _build_query(self, keywords: str, description: str) -> str:
        """Build search query string"""
        if description:
            return f"{keywords} {description}"
        return keywords


if __name__ == "__main__":
    # Test multi-source searcher
    print("🧪 Testing multi-source searcher\n")

    # Initialize
    db = Database(":memory:")
    searcher = MultiSourceSearcher(db)

    # Test 1: Full-source search
    print("=" * 60)
    print("Test 1: Full-source search 'deep learning'")
    print("=" * 60 + "\n")

    papers = searcher.search(
        keywords="deep learning",
        limit=10,
        sources=['crossref', 'arxiv']  # Test these two first, avoid S2 rate limiting
    )

    if papers:
        print(f"\n✅ Found {len(papers)} papers:\n")
        for i, paper in enumerate(papers[:5], 1):  # Only show first 5
            print(f"{i}. {paper.title[:70]}...")
            print(f"   Author: {paper.first_author}")
            print(f"   Year: {paper.year} | Citations: {paper.citation_count}")
            print(f"   Venue: {paper.venue or 'N/A'}")
            print(f"   ID: {paper.paper_id}\n")
    else:
        print("❌ Search failed")

    # Test 2: Priority search
    print("\n" + "=" * 60)
    print("Test 2: Priority search 'autonomous driving'")
    print("=" * 60 + "\n")

    papers2 = searcher.search_by_priority(
        keywords="autonomous driving",
        description="simulation",
        limit=5
    )

    if papers2:
        print(f"\n✅ Found {len(papers2)} papers")
        for i, paper in enumerate(papers2, 1):
            print(f"{i}. {paper.title[:50]}... ({paper.year})")

    print("\n🎉 Testing complete!")
