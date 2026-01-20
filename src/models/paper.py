"""
Paper Data Model - Core data structure for papers
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json


@dataclass
class Paper:
    """Paper data class"""
    paper_id: str                      # Semantic Scholar ID
    title: str                         # title
    authors: List[str]                 # author list
    year: Optional[int]                # publication year
    abstract: Optional[str]            # abstract
    doi: Optional[str]                 # DOI
    citation_count: int                # citation count
    url: Optional[str]                 # paper URL
    venue: Optional[str]               # publication venue/journal
    fields_of_study: List[str]         # research fields

    @property
    def first_author(self) -> str:
        """Get first author"""
        return self.authors[0] if self.authors else "Unknown"

    @classmethod
    def from_s2_dict(cls, data: Dict[str, Any]) -> 'Paper':
        """
        Create Paper object from Semantic Scholar API response

        Args:
            data: Paper data dictionary returned by S2 API

        Returns:
            Paper object
        """
        # Extract author list
        authors = []
        if 'authors' in data and data['authors']:
            authors = [author.get('name', 'Unknown') for author in data['authors']]

        # Extract DOI
        doi = None
        if 'externalIds' in data and data['externalIds']:
            doi = data['externalIds'].get('DOI')

        # Extract research fields
        fields = data.get('fieldsOfStudy', []) or []

        return cls(
            paper_id=data.get('paperId', ''),
            title=data.get('title', 'Untitled'),
            authors=authors,
            year=data.get('year'),
            abstract=data.get('abstract'),
            doi=doi,
            citation_count=data.get('citationCount', 0),
            url=data.get('url'),
            venue=data.get('venue'),
            fields_of_study=fields
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """
        Convert to database storage format

        Returns:
            Dictionary suitable for database insertion
        """
        return {
            'paper_id': self.paper_id,
            'title': self.title,
            'authors': json.dumps(self.authors, ensure_ascii=False),  # JSON format for list storage
            'first_author': self.first_author,
            'year': self.year,
            'abstract': self.abstract,
            'doi': self.doi,
            'citation_count': self.citation_count,
            'url': self.url,
            'venue': self.venue,
            'fields_of_study': json.dumps(self.fields_of_study, ensure_ascii=False)
        }

    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> 'Paper':
        """
        Create Paper object from database record

        Args:
            data: Database query result dictionary

        Returns:
            Paper object
        """
        # Parse JSON fields
        authors = json.loads(data.get('authors', '[]'))
        fields = json.loads(data.get('fields_of_study', '[]'))

        return cls(
            paper_id=data['paper_id'],
            title=data['title'],
            authors=authors,
            year=data.get('year'),
            abstract=data.get('abstract'),
            doi=data.get('doi'),
            citation_count=data.get('citation_count', 0),
            url=data.get('url'),
            venue=data.get('venue'),
            fields_of_study=fields
        )

    def __str__(self) -> str:
        """Friendly string representation"""
        return f"Paper({self.title[:50]}... by {self.first_author}, {self.year})"

    def __repr__(self) -> str:
        return self.__str__()


if __name__ == "__main__":
    # Test Paper model
    test_data = {
        'paperId': 'test123',
        'title': 'Deep Learning for Autonomous Driving',
        'authors': [{'name': 'John Smith'}, {'name': 'Jane Doe'}],
        'year': 2023,
        'abstract': 'This paper presents a novel approach...',
        'citationCount': 128,
        'url': 'https://example.com',
        'venue': 'CVPR',
        'externalIds': {'DOI': '10.1109/CVPR.2023.12345'},
        'fieldsOfStudy': ['Computer Science', 'Engineering']
    }

    paper = Paper.from_s2_dict(test_data)
    print("✅ Paper created successfully:")
    print(paper)
    print(f"   First author: {paper.first_author}")
    print(f"   Citation count: {paper.citation_count}")

    # Test database format conversion
    db_dict = paper.to_db_dict()
    print("\n✅ Database format conversion successful")
    print(f"   Authors (JSON): {db_dict['authors']}")

    # Test restoring from database format
    paper2 = Paper.from_db_dict(db_dict)
    print("\n✅ Restored from database successfully:")
    print(paper2)
