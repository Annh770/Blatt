"""
arXiv API 
"""
import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArxivClient:
    """arXiv API Client"""

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self, rate_limit_delay: float = 3.0):
        """
        Initialize client

        Args:
            rate_limit_delay: API request interval in seconds, arXiv recommends 3 seconds
        """
        self.session = requests.Session()
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

    def _rate_limit(self):
        """Rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def search_papers(self, query: str, limit: int = 10, retry_count: int = 0) -> List[Dict]:
        """
        Search papers

        Args:
            query: Search keywords
            limit: Number of papers to return
            retry_count: Current retry count (internal use)

        Returns:
            List of paper data (converted to unified format)
        """
        logger.info(f"arXiv search: '{query}' (limit: {limit} papers)")

        self._rate_limit()

        params = {
            'search_query': f'all:{query}',
            'start': 0,
            'max_results': limit,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            # Parse XML response
            papers = self._parse_xml(response.text)
            logger.info(f" Found {len(papers)} arXiv papers")

            return papers

        except requests.HTTPError as e:
            # Special handling for 429 error (rate limiting)
            if e.response.status_code == 429 and retry_count < 3:
                wait_time = int(e.response.headers.get('Retry-After', 60))
                logger.warning(f"⚠️  arXiv rate limited (429), retry {retry_count+1}, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return self.search_papers(query, limit, retry_count + 1)
            else:
                logger.error(f"❌ arXiv HTTP error: {e}")
                return []

        except Exception as e:
            logger.error(f"❌ arXiv API error: {e}")
            return []

    def _parse_xml(self, xml_text: str) -> List[Dict]:
        """
        Parse arXiv XML response and convert to unified format

        Args:
            xml_text: XML response text

        Returns:
            List of papers in unified format
        """
        papers = []
        root = ET.fromstring(xml_text)

        # arXiv uses Atom namespace
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }

        for entry in root.findall('atom:entry', ns):
            try:
                # Extract paper ID (from URL)
                id_url = entry.find('atom:id', ns).text
                paper_id = id_url.split('/abs/')[-1]

                # Extract title
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')

                # Extract authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns).text
                    authors.append({'name': name})

                # Extract abstract
                abstract = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')

                # Extract publication date
                published = entry.find('atom:published', ns).text
                year = int(published[:4])

                # Extract categories (as fields of study)
                categories = []
                for category in entry.findall('atom:category', ns):
                    categories.append(category.get('term'))

                # Extract links
                url = None
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        url = link.get('href')
                        break
                if not url:
                    url = id_url

                # Convert to unified format (compatible with Semantic Scholar format)
                paper = {
                    'paperId': f'arXiv:{paper_id}',
                    'title': title,
                    'authors': authors,
                    'year': year,
                    'abstract': abstract,
                    'doi': None,  # arXiv typically does not have DOI
                    'citationCount': 0,  # arXiv API does not provide citation count
                    'url': url,
                    'venue': 'arXiv',
                    'externalIds': {'ArXiv': paper_id},
                    'fieldsOfStudy': categories
                }

                papers.append(paper)

            except Exception as e:
                logger.warning(f"Failed to parse paper: {e}")
                continue

        return papers


if __name__ == "__main__":
    # Test arXiv client
    print(" Testing arXiv API Client\n")

    client = ArxivClient()

    # Test search
    print("=" * 60)
    print("Search: 'machine learning'")
    print("=" * 60)

    papers = client.search_papers("machine learning", limit=3)

    if papers:
        print(f"\n Success! Found {len(papers)} papers:\n")
        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper['title'][:80]}...")
            print(f"   Authors: {paper['authors'][0]['name'] if paper['authors'] else 'Unknown'}")
            print(f"   Year: {paper['year']}")
            print(f"   ID: {paper['paperId']}\n")
    else:
        print(" Search failed")

    print(" Test completed!")
