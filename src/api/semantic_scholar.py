"""
Semantic Scholar API 
"""
import requests
import time
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticScholarClient:
    """Semantic Scholar API Client"""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str = None, rate_limit_delay: float = None):
        """
        Initialize client

        Args:
            api_key: API key
            rate_limit_delay: API request interval in seconds
                - Default 10 seconds without API key
                - Default 1 second with API key
        """
        self.session = requests.Session()
        self.api_key = api_key
        self.last_request_time = 0
        self.request_count = 0  # Request counter

        # Set different rate limiting strategies based on whether there is an API key
        if api_key:
            self.rate_limit_delay = rate_limit_delay or 1.0
            self.session.headers.update({'x-api-key': api_key})
            logger.info(" Using API Key, rate limit: 1 request per second")
        else:
            self.rate_limit_delay = rate_limit_delay or 10.0
            logger.info(" Using Public API, rate limit: 1 request per 10 seconds")

    def _rate_limit(self):
        """Rate limiting: ensure request interval is at least rate_limit_delay seconds"""
        elapsed = time.time() - self.last_request_time

        # If there is an API key, use a more conservative strategy: ensure at least 1.1 seconds interval
        if self.api_key:
            min_delay = 1.1  # A bit more conservative, 1.1 seconds instead of 1 second
            if elapsed < min_delay:
                wait_time = min_delay - elapsed
                logger.info(f" Rate limit wait {wait_time:.2f} seconds...")
                time.sleep(wait_time)
        else:
            # Public API uses the original strategy
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.info(f" Rate limit wait {wait_time:.1f} seconds...")
                time.sleep(wait_time)

        # Note: Don't update last_request_time here, but after the request is completed
        self.request_count += 1

        # If using Public API, take an extra 30-second break after every 5 requests
        if not self.api_key and self.request_count % 5 == 0:
            logger.info(f" Completed {self.request_count} requests, resting 30 seconds to avoid rate limiting...")
            time.sleep(30)

    def _make_request(self, endpoint: str, params: Dict = None, retry_count: int = 0, max_retries: int = 5) -> Dict:
        """
        Make API request with exponential backoff retry and error handling

        Args:
            endpoint: API endpoint
            params: Request parameters
            retry_count: Current retry count
            max_retries: Maximum retry count, default 5

        Returns:
            JSON data from API response
        """
        self._rate_limit()  # Rate limiting

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            logger.info(f" Request: {endpoint}")
            response = self.session.get(url, params=params, timeout=30)

            # Update time immediately after request completes (ensure sufficient interval for next request)
            self.last_request_time = time.time()

            if response.status_code == 200:
                logger.info(f" Success: {endpoint}")
                return response.json()

            elif response.status_code == 429:
                # Rate limited - exponential backoff retry
                if retry_count < max_retries:
                    # Prefer server-returned Retry-After
                    retry_after = int(response.headers.get('Retry-After', 0))

                    # If server doesn't provide it, use exponential backoff: 60, 90, 120, 150, 180 seconds
                    if retry_after == 0:
                        retry_after = 60 + (retry_count * 30)

                    logger.warning(f"  Rate limited (429), waiting {retry_after} seconds before retry...")
                    logger.warning(f"   Retry progress: {retry_count+1}/{max_retries}")
                    time.sleep(retry_after)

                    return self._make_request(endpoint, params, retry_count + 1, max_retries)
                else:
                    logger.error(f" Reached maximum retries ({max_retries}), giving up request")
                    return {}

            elif response.status_code == 500:
                # Server error - brief retry
                if retry_count < 2:
                    wait_time = 10
                    logger.warning(f"  Server error (500), waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1, max_retries)
                else:
                    logger.error(" Persistent server error, giving up request")
                    return {}

            elif response.status_code == 504:
                # Gateway timeout - brief retry
                if retry_count < 2:
                    wait_time = 10
                    logger.warning(f"  Gateway timeout (504), waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1, max_retries)
                else:
                    logger.error(" Persistent gateway timeout, giving up request")
                    return {}

            else:
                logger.error(f" API request failed: {response.status_code}")
                logger.error(f"   Response: {response.text[:200]}")
                return {}

        except requests.exceptions.Timeout:
            if retry_count < 2:
                logger.warning(f"  Request timeout, retrying... ({retry_count+1}/2)")
                time.sleep(10)
                return self._make_request(endpoint, params, retry_count + 1, max_retries)
            else:
                logger.error(f" Persistent request timeout, giving up")
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f" Network request error: {e}")
            return {}

    def search_papers(self, query: str, limit: int = 10,
                     year_from: Optional[int] = None) -> List[Dict]:
        """
        Search papers

        Args:
            query: Search keywords
            limit: Maximum number of papers to return
            year_from: Starting year, e.g., 2015 means search only papers from 2015 onwards

        Returns:
            List of paper data
        """
        logger.info(f"Search papers: '{query}' (limit: {limit} papers)")

        # Build request parameters
        params = {
            'query': query,
            'limit': limit,
            'fields': 'paperId,title,authors,year,abstract,citationCount,url,venue,fieldsOfStudy,externalIds'
        }

        # Add year filter
        if year_from:
            params['year'] = f"{year_from}-"

        # Make request
        result = self._make_request('paper/search', params)

        papers = result.get('data', [])
        logger.info(f" Found {len(papers)} papers")

        return papers

    def get_paper_details(self, paper_id: str) -> Optional[Dict]:
        """
        Get paper detailed information

        Args:
            paper_id: Semantic Scholar paper ID

        Returns:
            Detailed paper data
        """
        logger.info(f"Get paper details: {paper_id}")

        endpoint = f"paper/{paper_id}"
        params = {
            'fields': 'paperId,title,authors,year,abstract,citationCount,url,venue,fieldsOfStudy,externalIds'
        }

        result = self._make_request(endpoint, params)
        return result if result else None

    def get_paper_by_doi(self, doi: str) -> Optional[Dict]:
        """
        Get paper information by DOI (used to complete abstract)

        Args:
            doi: Paper DOI

        Returns:
            Paper data (if found)
        """
        return self.get_paper_details(f"DOI:{doi}")

    def get_citations(self, paper_id: str, limit: int = 20) -> List[Dict]:
        """
        Get papers that cite this paper (citing papers)

        Args:
            paper_id: Paper ID
            limit: Maximum number of results to return

        Returns:
            List of citing papers
        """
        logger.info(f"Get citing papers: {paper_id} (limit: {limit} papers)")

        endpoint = f"paper/{paper_id}/citations"
        params = {
            'limit': limit,
            'fields': 'paperId,title,authors,year,abstract,citationCount,url,venue,fieldsOfStudy,externalIds'
        }

        result = self._make_request(endpoint, params)

        # Extract citing papers
        citations = []
        if result and 'data' in result:
            for item in result['data']:
                if 'citingPaper' in item:
                    citations.append(item['citingPaper'])

        logger.info(f" Found {len(citations)} citing papers")
        return citations

    def get_references(self, paper_id: str, limit: int = 20) -> List[Dict]:
        """
        Get papers that this paper cites (cited papers / references)

        Args:
            paper_id: Paper ID
            limit: Maximum number of results to return

        Returns:
            List of cited papers
        """
        logger.info(f"Get references: {paper_id} (limit: {limit} papers)")

        endpoint = f"paper/{paper_id}/references"
        params = {
            'limit': limit,
            'fields': 'paperId,title,authors,year,abstract,citationCount,url,venue,fieldsOfStudy,externalIds'
        }

        result = self._make_request(endpoint, params)

        # Extract cited papers
        references = []
        if result and 'data' in result:
            for item in result['data']:
                if 'citedPaper' in item:
                    references.append(item['citedPaper'])

        logger.info(f" Found {len(references)} references")
        return references


if __name__ == "__main__":
    # Test API client
    print(" Testing Semantic Scholar API Client\n")

    client = SemanticScholarClient()

    # Test 1: Search papers
    print("=" * 60)
    print("Test 1: Search papers")
    print("=" * 60)
    papers = client.search_papers("machine learning", limit=3)

    if papers:
        print(f"\n Successfully found {len(papers)} papers:\n")
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'Unknown')
            year = paper.get('year', 'N/A')
            citations = paper.get('citationCount', 0)
            print(f"{i}. {title}")
            print(f"   Year: {year} | Citations: {citations}\n")
    else:
        print(" Search failed")

    # Test 2: Get citation relationships (using first paper)
    if papers:
        first_paper_id = papers[0].get('paperId')
        if first_paper_id:
            print("\n" + "=" * 60)
            print("Test 2: Get citation relationships")
            print("=" * 60)

            citations = client.get_citations(first_paper_id, limit=2)
            print(f"\n Found {len(citations)} citing papers")

            references = client.get_references(first_paper_id, limit=2)
            print(f" Found {len(references)} references")

    print("\n API client test completed!")
