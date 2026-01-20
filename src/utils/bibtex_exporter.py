"""
BibTeX Exporter - Export paper data to BibTeX format
"""
from typing import List, Dict
import json
import logging
import os
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BibTeXExporter:
    """BibTeX Exporter for reference management software"""

    def __init__(self):
        """Initialize exporter"""
        self.default_output_dir = "exports/bibtex"

    def export(
        self,
        papers: List[Dict],
        output_path: str,
        entry_type: str = "article"
    ) -> str:
        """
        Export papers to BibTeX format

        Args:
            papers: List of paper data
            output_path: Output file path
            entry_type: BibTeX entry type ('article', 'inproceedings', 'misc')

        Returns:
            Actual saved file path
        """
        if not papers:
            logger.warning("⚠️  No paper data to export")
            return None

        logger.info(f"📚 Preparing to export {len(papers)} papers to BibTeX...")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate BibTeX entries
        bibtex_entries = []
        for i, paper in enumerate(papers):
            entry = self._generate_bibtex_entry(paper, i, entry_type)
            bibtex_entries.append(entry)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(bibtex_entries))

        logger.info(f"✅ BibTeX export successful: {output_path}")
        logger.info(f"   Total {len(bibtex_entries)} entries")

        return output_path

    def _generate_bibtex_entry(
        self,
        paper: Dict,
        index: int,
        entry_type: str = "article"
    ) -> str:
        """
        Generate BibTeX entry for a single paper

        Args:
            paper: Paper data
            index: Index (used to generate unique citation key)
            entry_type: Entry type

        Returns:
            BibTeX formatted string
        """
        # Generate citation key
        cite_key = self._generate_cite_key(paper, index)

        # Parse author list
        authors = self._parse_json_field(paper.get('authors', '[]'))
        authors_str = ' and '.join(authors) if authors else 'Unknown'

        # Basic fields
        year = paper.get('year', 'N/A')
        title = self._escape_latex(paper.get('title', 'Unknown'))
        venue = paper.get('venue', '')

        # Infer entry type based on venue
        if not entry_type or entry_type == "auto":
            entry_type = self._infer_entry_type(venue)

        # Build BibTeX entry
        if entry_type == "article":
            entry = self._generate_article_entry(
                cite_key, title, authors_str, year, venue, paper
            )
        elif entry_type == "inproceedings":
            entry = self._generate_inproceedings_entry(
                cite_key, title, authors_str, year, venue, paper
            )
        else:  # misc
            entry = self._generate_misc_entry(
                cite_key, title, authors_str, year, paper
            )

        return entry

    def _generate_cite_key(self, paper: Dict, index: int) -> str:
        """
        Generate citation key

        Format: FirstAuthor_Year_Index
        Example: Smith_2020_001
        """
        first_author = paper.get('first_author', 'Unknown')

        # Remove spaces and special characters
        first_author_clean = re.sub(r'[^\w]', '', first_author)

        year = paper.get('year', 'XXXX')
        cite_key = f"{first_author_clean}{year}_{index:03d}"

        return cite_key

    def _infer_entry_type(self, venue: str) -> str:
        """Infer BibTeX entry type based on venue"""
        if not venue:
            return "misc"

        venue_lower = venue.lower()

        # Conference proceedings
        conference_keywords = ['conference', 'proceedings', 'workshop', 'symposium',
                              'cvpr', 'iccv', 'eccv', 'nips', 'icml', 'iclr',
                              'aaai', 'ijcai', 'acl', 'emnlp', 'icra', 'iros']
        if any(kw in venue_lower for kw in conference_keywords):
            return "inproceedings"

        # Journal articles
        journal_keywords = ['journal', 'transactions', 'letters', 'nature',
                           'science', 'pnas', 'cell', 'lancet']
        if any(kw in venue_lower for kw in journal_keywords):
            return "article"

        # arXiv etc
        if 'arxiv' in venue_lower:
            return "misc"

        return "article"  # Default

    def _generate_article_entry(
        self,
        cite_key: str,
        title: str,
        authors: str,
        year: str,
        venue: str,
        paper: Dict
    ) -> str:
        """Generate article type entry (journal paper)"""
        doi = paper.get('doi', '')
        url = paper.get('url', '')
        abstract = paper.get('abstract', '')[:500] if paper.get('abstract') else ''

        entry = f"""@article{{{cite_key},
  title = {{{title}}},
  author = {{{authors}}},
  year = {{{year}}},
  journal = {{{venue or 'Unknown'}}},"""

        if doi:
            entry += f"\n  doi = {{{doi}}},"
        if url:
            entry += f"\n  url = {{{url}}},"
        if abstract:
            entry += f"\n  abstract = {{{self._escape_latex(abstract)}...}},"

        # Add custom fields (e.g., Priority)
        if 'priority' in paper:
            entry += f"\n  note = {{Priority: {paper['priority']}}},"

        entry = entry.rstrip(',') + "\n}"
        return entry

    def _generate_inproceedings_entry(
        self,
        cite_key: str,
        title: str,
        authors: str,
        year: str,
        venue: str,
        paper: Dict
    ) -> str:
        """Generate inproceedings type entry (conference paper)"""
        doi = paper.get('doi', '')
        url = paper.get('url', '')

        entry = f"""@inproceedings{{{cite_key},
  title = {{{title}}},
  author = {{{authors}}},
  year = {{{year}}},
  booktitle = {{{venue or 'Unknown Conference'}}},"""

        if doi:
            entry += f"\n  doi = {{{doi}}},"
        if url:
            entry += f"\n  url = {{{url}}},"

        if 'priority' in paper:
            entry += f"\n  note = {{Priority: {paper['priority']}}},"

        entry = entry.rstrip(',') + "\n}"
        return entry

    def _generate_misc_entry(
        self,
        cite_key: str,
        title: str,
        authors: str,
        year: str,
        paper: Dict
    ) -> str:
        """Generate misc type entry (other types)"""
        url = paper.get('url', '')
        venue = paper.get('venue', '')

        entry = f"""@misc{{{cite_key},
  title = {{{title}}},
  author = {{{authors}}},
  year = {{{year}}},"""

        if venue:
            entry += f"\n  howpublished = {{{venue}}},"
        if url:
            entry += f"\n  url = {{{url}}},"

        if 'priority' in paper:
            entry += f"\n  note = {{Priority: {paper['priority']}}},"

        entry = entry.rstrip(',') + "\n}"
        return entry

    def _parse_json_field(self, field):
        """Parse JSON field"""
        if isinstance(field, str):
            try:
                return json.loads(field)
            except:
                return []
        elif isinstance(field, list):
            return field
        else:
            return []

    def _escape_latex(self, text: str) -> str:
        """
        Escape LaTeX special characters

        Args:
            text: Original text

        Returns:
            Escaped text
        """
        if not text:
            return ""

        # LaTeX special character mapping
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
            '\\': r'\textbackslash{}',
        }

        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        return text


if __name__ == "__main__":
    # Test BibTeX exporter
    print("🍃 Testing BibTeX Exporter\n")

    exporter = BibTeXExporter()

    # Create test data
    test_papers = [
        {
            'paper_id': 'paper1',
            'title': 'Deep Learning for Autonomous Driving',
            'authors': '["John Smith", "Jane Doe"]',
            'first_author': 'John Smith',
            'year': 2020,
            'priority': 5,
            'citation_count': 150,
            'venue': 'CVPR 2020',
            'doi': '10.1109/CVPR.2020.12345',
            'url': 'https://example.com/paper1',
            'abstract': 'This paper presents a novel deep learning approach for autonomous driving systems.'
        },
        {
            'paper_id': 'paper2',
            'title': 'Machine Learning in Robotics: A Survey',
            'authors': '["Alice Wang", "Bob Johnson"]',
            'first_author': 'Alice Wang',
            'year': 2021,
            'priority': 4,
            'citation_count': 80,
            'venue': 'IEEE Transactions on Robotics',
            'doi': '10.1109/TRO.2021.54321',
            'url': 'https://example.com/paper2',
            'abstract': 'A comprehensive survey of machine learning techniques in robotics.'
        },
        {
            'paper_id': 'paper3',
            'title': 'Computer Vision with PyTorch',
            'authors': '["Charlie Brown"]',
            'first_author': 'Charlie Brown',
            'year': 2022,
            'priority': 3,
            'citation_count': 45,
            'venue': 'arXiv preprint arXiv:2201.12345',
            'url': 'https://arxiv.org/abs/2201.12345',
            'abstract': 'An introduction to computer vision using PyTorch framework.'
        }
    ]

    # Test 1: Basic export
    print("=" * 60)
    print("Test 1: Basic BibTeX Export")
    print("=" * 60)

    output_file = "test_papers.bib"
    result = exporter.export(
        papers=test_papers,
        output_path=output_file,
        entry_type="auto"  # Auto-detect type
    )

    if result and os.path.exists(result):
        file_size = os.path.getsize(result) / 1024
        print(f"✅ Export successful: {result}")
        print(f"   File size: {file_size:.1f} KB")
        print(f"   Number of papers: {len(test_papers)} entries")

        # Display content preview
        with open(result, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"\nContent preview (first 500 characters):")
            print("-" * 60)
            print(content[:500])
            print("...")
            print("-" * 60)

    # Test 2: Force article type
    print("\n" + "=" * 60)
    print("Test 2: Force article type export")
    print("=" * 60)

    output_file2 = "test_papers_articles.bib"
    result2 = exporter.export(
        papers=test_papers,
        output_path=output_file2,
        entry_type="article"
    )

    if result2:
        print(f"✅ Export successful: {result2}")

    # Test 3: Special characters in title
    print("\n" + "=" * 60)
    print("Test 3: Special character escaping")
    print("=" * 60)

    special_paper = [{
        'paper_id': 'paper_special',
        'title': 'ML & AI: 50% Progress in $100 Projects #2023',
        'authors': '["Test Author"]',
        'first_author': 'Test',
        'year': 2023,
        'venue': 'Test Conference',
        'url': 'https://example.com'
    }]

    output_file3 = "test_special_chars.bib"
    result3 = exporter.export(
        papers=special_paper,
        output_path=output_file3
    )

    if result3:
        print(f"✅ Special character export successful: {result3}")
        with open(result3, 'r', encoding='utf-8') as f:
            print(f"\nEscaping result:")
            print(f.read())

    print("\n🎉 All tests completed!")
    print(f"\nGenerated files:")
    for f in [output_file, output_file2, output_file3]:
        if os.path.exists(f):
            print(f"   - {f}")
