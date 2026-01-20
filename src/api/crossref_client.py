"""
CrossRef API 
"""
import requests
import time
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrossRefClient:
    """CrossRef API Client"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, mailto: str = "paper-search@example.com", rate_limit_delay: float = 1.0):
        """
        Initialize client

        Args:
            mailto: Email address (polite pool, can get faster speed)
            rate_limit_delay: Request interval (seconds)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'Blatt-PaperSearch/1.0 (mailto:{mailto})'
        })
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

    def _rate_limit(self):
        """Rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def search_papers(self, query: str, limit: int = 10,
                     year_from: int = None) -> List[Dict]:
        """
        Search papers

        Args:
            query: Search keywords
            limit: Number of results to return
            year_from: Starting year

        Returns:
            List of papers in unified format
        """
        logger.info(f"CrossRef search: '{query}' (limit: {limit} papers)")

        self._rate_limit()

        params = {
            'query': query,
            'rows': limit,
            'sort': 'relevance'
        }

        if year_from:
            params['filter'] = f'from-pub-date:{year_from}'

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get('message', {}).get('items', [])

            papers = []
            for item in items:
                paper = self._convert_to_standard_format(item)
                if paper:
                    papers.append(paper)

            logger.info(f" Found {len(papers)} CrossRef papers")
            return papers

        except Exception as e:
            logger.error(f"CrossRef API error: {e}")
            return []

    def _convert_to_standard_format(self, item: Dict) -> Optional[Dict]:
        """Convert to unified format, compatible with Semantic Scholar format"""
        try:
            # DOI
            doi = item.get('DOI')
            if not doi:
                return None

            # Title
            title_list = item.get('title', [])
            title = title_list[0] if title_list else 'Untitled'

            # Authors
            authors = []
            for author in item.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                name = f"{given} {family}".strip()
                if name:
                    authors.append({'name': name})

            # Year
            year = None
            pub_print = item.get('published-print', {}).get('date-parts', [[]])[0]
            pub_online = item.get('published-online', {}).get('date-parts', [[]])[0]

            if pub_print:
                year = pub_print[0]
            elif pub_online:
                year = pub_online[0]

            # Abstract (CrossRef rarely provides this)
            abstract = item.get('abstract')

            # Journal/Conference
            venue_list = item.get('container-title', [])
            venue = venue_list[0] if venue_list else None

            # Citation count
            citation_count = item.get('is-referenced-by-count', 0)

            # URL
            url = f"https://doi.org/{doi}"

            # Unified format
            return {
                'paperId': f'DOI:{doi}',
                'title': title,
                'authors': authors,
                'year': year,
                'abstract': abstract,
                'doi': doi,
                'citationCount': citation_count,
                'url': url,
                'venue': venue,
                'externalIds': {'DOI': doi},
                'fieldsOfStudy': []
            }

        except Exception as e:
            logger.warning(f"Parsing failed: {e}")
            return None


if __name__ == "__main__":
    # Test
    print(" Testing CrossRef API Client\n")

    client = CrossRefClient()

    print("=" * 60)
    print("Search: 'autonomous driving'")
    print("=" * 60 + "\n")

    papers = client.search_papers("autonomous driving", limit=5)

    if papers:
        print(f" Found {len(papers)} papers:\n")
        for i, p in enumerate(papers, 1):
            print(f"{i}. {p['title'][:70]}...")
            author = p['authors'][0]['name'] if p['authors'] else 'Unknown'
            print(f"   Authors: {author}")
            print(f"   Year: {p['year']}")
            print(f"   Source: {p['venue']}")
            print(f"   Citations: {p['citationCount']}")
            print(f"   DOI: {p['doi']}\n")
    else:
        print(" Search failed")

    print(" Test completed!")
