"""
Paper Searcher - Integrates APIs and database, provides high-level search interface
Supports multiple data sources: Semantic Scholar (primary) + arXiv (backup)
"""
from typing import List
import logging

from src.api.semantic_scholar import SemanticScholarClient
from src.api.arxiv_client import ArxivClient
from src.models.database import Database
from src.models.paper import Paper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperSearcher:
    """Paper Searcher"""

    def __init__(self, db: Database, use_arxiv: bool = False):
        """
        Initialize searcher

        Args:
            db: Database instance
            use_arxiv: Whether to use arXiv as data source (default uses Semantic Scholar)
        """
        self.db = db
        self.use_arxiv = use_arxiv

        if use_arxiv:
            self.client = ArxivClient()
            logger.info("📚 Using arXiv as data source")
        else:
            self.client = SemanticScholarClient()
            logger.info("📚 Using Semantic Scholar as data source")

    def search(self, keywords: str, description: str = "",
               limit: int = 10, year_from: int = None) -> List[Paper]:
        """
        Search papers and save to database

        Args:
            keywords: Search keywords
            description: Supplementary description (optional)
            limit: Number of papers to return
            year_from: Starting year (optional)

        Returns:
            List of Paper objects
        """
        logger.info(f"🔍 Starting search: '{keywords}'")

        # Build search query
        query = self._build_query(keywords, description)

        # Search from data source (automatically select S2 or arXiv)
        if self.use_arxiv:
            raw_papers = self.client.search_papers(query=query, limit=limit)
        else:
            raw_papers = self.client.search_papers(
                query=query,
                limit=limit,
                year_from=year_from
            )

        if not raw_papers:
            logger.warning("No papers found")
            return []

        # Convert to Paper objects and save to database
        papers = []
        for raw_paper in raw_papers:
            try:
                # Create Paper object
                paper = Paper.from_s2_dict(raw_paper)

                # Save to database
                self.db.add_or_update_paper(paper.to_db_dict())

                papers.append(paper)

            except Exception as e:
                logger.error(f"Failed to process paper: {e}")
                continue

        logger.info(f"✅ Successfully processed {len(papers)} papers")
        return papers

    def _build_query(self, keywords: str, description: str) -> str:
        """
        Build search query string

        Args:
            keywords: Keywords
            description: Supplementary description

        Returns:
            Complete query string
        """
        if description:
            return f"{keywords} {description}"
        return keywords


if __name__ == "__main__":
    # Test paper searcher
    print("🧪 Testing Paper Searcher\n")

    # Initialize database and searcher
    db = Database("data/ye_test.db")
    searcher = PaperSearcher(db)

    # Test search
    print("=" * 60)
    print("Search: 'autonomous driving'")
    print("=" * 60 + "\n")

    papers = searcher.search(
        keywords="autonomous driving",
        description="simulation and testing",
        limit=5
    )

    # Display results
    if papers:
        print(f"\n✅ Search successful! Found {len(papers)} papers:\n")
        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper.title}")
            print(f"   Authors: {paper.first_author}")
            print(f"   Year: {paper.year} | Citations: {paper.citation_count}")
            print(f"   ID: {paper.paper_id}\n")

        # Verify database storage
        print("=" * 60)
        print("Verify database storage")
        print("=" * 60 + "\n")

        first_paper = papers[0]
        db_paper = db.get_paper_by_id(first_paper.paper_id)

        if db_paper:
            print(f"✅ Successfully retrieved paper from database:")
            print(f"   Title: {db_paper['title']}")
            print(f"   Authors: {db_paper['first_author']}")
        else:
            print("❌ Database retrieval failed")

    else:
        print("❌ Search failed")

    print("\n🎉 Searcher test completed!")
