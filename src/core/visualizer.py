"""
Visualization Generator - Generate interactive paper relationship graphs

Uses pyvis library to generate HTML interactive network graphs, displaying citation relationships and evolution history between papers.
"""
from pyvis.network import Network
import networkx as nx
from typing import List, Dict, Optional, Set
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperGraphVisualizer:
    """Paper relationship graph visualization generator"""

    def __init__(self):
        """Initialize visualization generator"""
        # Relationship type color mapping
        self.relationship_colors = {
            'improves': '#FF6B6B',      # Red - improves
            'builds_on': '#4ECDC4',     # Cyan - builds on
            'compares': '#FFD93D',      # Yellow - compares
            'applies': '#6BCF7F',       # Green - applies to
            'surveys': '#A8DADC',       # Light blue - surveys
            'extends': '#F4A261',       # Orange - extends
            'cites': '#CCCCCC'          # Gray - cites (default)
        }

        # Priority color mapping
        self.priority_colors = {
            5: '#00C853',  # Dark green - highly relevant
            4: '#FFD600',  # Yellow - relevant
            3: '#90CAF9',  # Light blue - partially relevant
            2: '#FFAB91',  # Light orange - weakly relevant
            1: '#E0E0E0'   # Gray - irrelevant
        }

    def generate(
        self,
        papers: List[Dict],
        relationships: List[Dict],
        output_path: str,
        title: str = "Paper Citation Network",
        height: str = "900px",
        width: str = "100%"
    ) -> str:
        """
        Generate interactive paper relationship graph

        Args:
            papers: Paper list (containing priority and other fields)
            relationships: Relationship list
            output_path: Output HTML file path
            title: Graph title
            height: Graph height
            width: Graph width

        Returns:
            Generated HTML file path
        """
        if not papers:
            logger.warning("⚠️  No paper data to visualize")
            return None

        logger.info(f"📊 Preparing to generate visualization graph...")
        logger.info(f"   Papers: {len(papers)}")
        logger.info(f"   Relationships: {len(relationships)}")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Create pyvis network graph
        net = Network(
            height=height,
            width=width,
            bgcolor='#ffffff',
            font_color='#000000',
            directed=True,
            notebook=False
        )

        # Add nodes
        self._add_paper_nodes(net, papers)

        # Add edges
        self._add_relationship_edges(net, relationships)

        # Configure layout options
        net.set_options(self._get_layout_options())

        # Save as HTML
        net.save_graph(output_path)

        # Add legend to HTML file
        self._add_legend_to_html(output_path)

        logger.info(f"✅ Visualization graph generated: {output_path}")
        logger.info(f"   Please open in browser to view")

        return output_path

    def _add_paper_nodes(self, net: Network, papers: List[Dict]):
        """Add paper nodes"""
        for paper in papers:
            paper_id = paper.get('paper_id', '')
            title = paper.get('title', 'Unknown')
            year = paper.get('year', 'N/A')
            priority = paper.get('priority', 3)
            citations = paper.get('citation_count', 0)
            first_author = paper.get('first_author', 'Unknown')
            venue = paper.get('venue', 'N/A')

            # Node color based on Priority
            color = self.priority_colors.get(priority, '#E0E0E0')

            # Node size based on citation count (logarithmic scaling)
            import math
            size = 10 + min(math.log(citations + 1) * 5, 40)

            # Node label (short display)
            label = f"{title[:40]}...\n{first_author} ({year})"

            # Hover tooltip (detailed info)
            matched_kws = paper.get('matched_keywords', '[]')
            if isinstance(matched_kws, str):
                try:
                    matched_kws = json.loads(matched_kws)
                except:
                    matched_kws = []

            # Get abstract (if available)
            abstract = paper.get('abstract', '')
            if abstract:
                # Limit abstract length to avoid oversized hover box
                abstract_preview = abstract[:200] + '...' if len(abstract) > 200 else abstract
            else:
                abstract_preview = 'No abstract available'

            # Build hover tooltip (using plain text to avoid HTML escape issues)
            hover_parts = [
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"{title}",
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"Author: {first_author} et al.",
                f"Year: {year}",
                f"Venue: {venue}",
                f"Citations: {citations}",
                f"Priority: {priority} {'★' * priority}",
                f"Keywords: {', '.join(matched_kws) if matched_kws else 'None'}",
            ]

            # Add analysis reason (if available)
            if paper.get('analysis_reason'):
                hover_parts.append(f"Reason: {paper.get('analysis_reason')}")

            # Add abstract
            hover_parts.append("")
            hover_parts.append(f"Abstract:")
            hover_parts.append(f"  {abstract_preview}")
            hover_parts.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            hover_title = "\n".join(hover_parts)

            # Add node
            net.add_node(
                paper_id,
                label=label,
                title=hover_title,
                color=color,
                size=size,
                shape='box',
                borderWidth=2,
                borderWidthSelected=4,
                font={'size': 12, 'face': 'Arial'},
                level=year if isinstance(year, int) else 2020  # Y-axis arranged by year
            )

    def _add_relationship_edges(self, net: Network, relationships: List[Dict]):
        """Add relationship edges (optimized: reduce overlap)"""
        # Count edges between each node pair for dynamic curvature adjustment
        edge_counts = {}
        for rel in relationships:
            source_id = rel.get('source_paper_id', '')
            target_id = rel.get('target_paper_id', '')
            key = tuple(sorted([source_id, target_id]))
            edge_counts[key] = edge_counts.get(key, 0) + 1

        # Track added edges for dynamic curvature adjustment
        added_edges = {}

        for rel in relationships:
            source_id = rel.get('source_paper_id', '')
            target_id = rel.get('target_paper_id', '')
            rel_type = rel.get('relationship_type', 'cites')
            rel_desc = rel.get('relationship_desc', '')

            # Edge color based on relationship type (with opacity)
            color = self.relationship_colors.get(rel_type, '#CCCCCC')
            # Add opacity: important relationships opaque, general citations semi-transparent
            if rel_type == 'cites':
                color = {'color': color, 'opacity': 0.5}
            else:
                color = {'color': color, 'opacity': 0.8}

            # Edge width: important relationships thicker
            width = 3 if rel_type != 'cites' else 1.5

            # Edge style: important relationships solid, general citations dashed
            dashes = False if rel_type != 'cites' else [5, 5]

            # Dynamic curvature adjustment to avoid overlap
            key = tuple(sorted([source_id, target_id]))
            edge_index = added_edges.get(key, 0)
            added_edges[key] = edge_index + 1

            # Adjust curvature based on edge index
            # roundness increases from 0.1 to 0.9, supports up to 5 edges
            roundness = 0.15 + (edge_index * 0.2)

            # Use negative curvature for reverse edges
            if source_id > target_id:
                roundness = -roundness

            # Hover tooltip (using plain text to avoid HTML escape issues)
            rel_name_cn = self._get_relationship_name(rel_type)
            rel_name_en = rel_type.replace('_', ' ').title()

            hover_parts = [
                f"━━━━━━━━━━━━━━━━━━━━━━━━",
                f"Relationship",
                f"━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"Direction: {source_id[:20]}... → {target_id[:20]}...",
                f"Type: {rel_name_en} / {rel_name_cn}",
                f"Description: {rel_desc or 'General citation'}",
                f"━━━━━━━━━━━━━━━━━━━━━━━━"
            ]

            hover_title = "\n".join(hover_parts)

            try:
                net.add_edge(
                    source_id,
                    target_id,
                    title=hover_title,
                    color=color,
                    width=width,
                    dashes=dashes,
                    arrows='to',
                    arrowStrikethrough=False,
                    smooth={
                        'enabled': True,
                        'type': 'curvedCW',
                        'roundness': roundness  # Dynamic curvature
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️  Failed to add edge ({source_id} -> {target_id}): {e}")

    def _get_relationship_name(self, rel_type: str) -> str:
        """Get relationship type display name"""
        names = {
            'improves': 'improves',
            'builds_on': 'builds on',
            'compares': 'compares',
            'applies': 'applies to',
            'surveys': 'surveys',
            'extends': 'extends',
            'cites': 'cites'
        }
        return names.get(rel_type, 'cites')

    def _get_layout_options(self) -> str:
        """Return graph layout configuration (JSON string)"""
        options = """
{
  "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "UD",
      "sortMethod": "directed",
      "levelSeparation": 200,
      "nodeSpacing": 150,
      "treeSpacing": 250
    }
  },
  "physics": {
    "enabled": false,
    "hierarchicalRepulsion": {
      "centralGravity": 0.0,
      "springLength": 200,
      "springConstant": 0.01,
      "nodeDistance": 150,
      "damping": 0.09
    }
  },
  "edges": {
    "smooth": {
      "type": "cubicBezier",
      "forceDirection": "vertical",
      "roundness": 0.4
    },
    "arrows": {
      "to": {
        "enabled": true,
        "scaleFactor": 1.0
      }
    }
  },
  "nodes": {
    "font": {
      "size": 14,
      "face": "Arial",
      "align": "center"
    },
    "borderWidth": 2,
    "borderWidthSelected": 4,
    "scaling": {
      "min": 10,
      "max": 50
    }
  },
  "interaction": {
    "hover": true,
    "navigationButtons": true,
    "keyboard": {
      "enabled": true
    },
    "zoomView": true,
    "dragView": true,
    "tooltipDelay": 100
  }
}
"""
        return options

    def generate_multi_keyword_graphs(
        self,
        papers: List[Dict],
        relationships: List[Dict],
        keywords: List[str],
        output_dir: str
    ) -> Dict[str, str]:
        """
        Generate separate subgraphs for each keyword

        Args:
            papers: Paper list
            relationships: Relationship list
            keywords: Keyword list
            output_dir: Output directory

        Returns:
            {"simulation": "/path/to/simulation_graph.html", ...}
        """
        logger.info(f"📊 Preparing to generate multi-keyword graphs...")
        logger.info(f"   Keywords: {len(keywords)}")

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        output_paths = {}

        # Group papers by keyword
        keyword_groups = self._group_papers_by_keyword(papers, keywords)

        for keyword, group_papers in keyword_groups.items():
            if not group_papers:
                logger.warning(f"⚠️  Keyword '{keyword}' has no matching papers, skipping")
                continue

            logger.info(f"   Generating '{keyword}' subgraph ({len(group_papers)} papers)")

            # Filter relevant relationships
            group_paper_ids = {p['paper_id'] for p in group_papers}
            group_rels = [
                r for r in relationships
                if r['source_paper_id'] in group_paper_ids and
                   r['target_paper_id'] in group_paper_ids
            ]

            # Generate subgraph
            output_path = f"{output_dir}/{keyword}_graph.html"
            self.generate(
                group_papers,
                group_rels,
                output_path,
                title=f"📚 {keyword.upper()} - Paper Network"
            )

            output_paths[keyword] = output_path

        # Generate combined graph (all papers)
        logger.info(f"   Generating combined graph ({len(papers)} papers)")
        combined_path = f"{output_dir}/combined_graph.html"
        self.generate(
            papers,
            relationships,
            combined_path,
            title="📚 Complete Paper Network - All Keywords"
        )
        output_paths['combined'] = combined_path

        logger.info(f"✅ Multi-keyword graphs generated! Total {len(output_paths)} files")

        return output_paths

    def _group_papers_by_keyword(
        self,
        papers: List[Dict],
        keywords: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Group papers by primary keyword

        Args:
            papers: Paper list
            keywords: User-input keyword list

        Returns:
            {"simulation": [paper1, paper2], "validation": [...]}
        """
        groups = {kw: [] for kw in keywords}

        for paper in papers:
            # Parse matched keywords
            matched_kws = paper.get('matched_keywords', '[]')
            if isinstance(matched_kws, str):
                try:
                    matched_kws = json.loads(matched_kws)
                except:
                    matched_kws = []

            # Find first matching user keyword as primary keyword
            primary_kw = None
            for kw in keywords:
                # Case-insensitive matching
                if any(kw.lower() in mk.lower() for mk in matched_kws):
                    primary_kw = kw
                    break

            if primary_kw:
                groups[primary_kw].append(paper)
            else:
                # If no keyword matches, add to first group
                if keywords:
                    groups[keywords[0]].append(paper)

        return groups

    def generate_temporal_graph(
        self,
        papers: List[Dict],
        relationships: List[Dict],
        output_path: str
    ) -> str:
        """
        Generate temporal evolution graph (emphasizing year hierarchy)

        Args:
            papers: Paper list
            relationships: Relationship list
            output_path: Output path

        Returns:
            Generated HTML file path
        """
        logger.info(f"📊 Generating temporal evolution graph...")

        # Statistics by year
        year_counts = {}
        for paper in papers:
            year = paper.get('year', 'Unknown')
            year_counts[year] = year_counts.get(year, 0) + 1

        logger.info(f"   Year distribution:")
        for year in sorted(year_counts.keys(), reverse=True):
            logger.info(f"      {year}: {year_counts[year]} papers")

        # Generate graph
        return self.generate(
            papers,
            relationships,
            output_path,
            title="📚 Paper Evolution - Temporal View",
            height="1000px"
        )

    def _add_legend_to_html(self, html_path: str):
        """
        Add legend to HTML file (top right corner)

        Args:
            html_path: HTML file path
        """
        # Read generated HTML file
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Define legend HTML and CSS
        legend_html = """
<style>
.legend-container {
    position: fixed;
    top: 20px;
    right: 20px;
    background: rgba(255, 255, 255, 0.95);
    border: 2px solid #333;
    border-radius: 8px;
    padding: 15px;
    font-family: Arial, sans-serif;
    font-size: 14px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    z-index: 1000;
    max-width: 280px;
}

.legend-title {
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 12px;
    color: #333;
    border-bottom: 2px solid #333;
    padding-bottom: 8px;
}

.legend-section {
    margin-bottom: 15px;
}

.legend-section-title {
    font-weight: bold;
    font-size: 13px;
    color: #555;
    margin-bottom: 8px;
}

.legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
    padding: 3px 0;
}

.legend-line {
    width: 40px;
    height: 3px;
    margin-right: 10px;
    border-radius: 2px;
}

.legend-line.dashed {
    background: repeating-linear-gradient(
        to right,
        currentColor,
        currentColor 5px,
        transparent 5px,
        transparent 10px
    );
    height: 2px;
}

.legend-text {
    color: #333;
    font-size: 13px;
}

.legend-node {
    width: 20px;
    height: 20px;
    margin-right: 10px;
    border-radius: 4px;
    border: 2px solid #666;
}
</style>

<div class="legend-container">
    <!-- Relationship Types Legend -->
    <div class="legend-section">
        <div class="legend-section-title">Relationship Types</div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #FF6B6B;"></div>
            <span class="legend-text">Improves</span>
        </div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #4ECDC4;"></div>
            <span class="legend-text">Builds On</span>
        </div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #FFD93D;"></div>
            <span class="legend-text">Compares</span>
        </div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #6BCF7F;"></div>
            <span class="legend-text">Applies</span>
        </div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #A8DADC;"></div>
            <span class="legend-text">Surveys</span>
        </div>

        <div class="legend-item">
            <div class="legend-line" style="background-color: #F4A261;"></div>
            <span class="legend-text">Extends</span>
        </div>

        <div class="legend-item">
            <div class="legend-line dashed" style="color: #CCCCCC;"></div>
            <span class="legend-text">Cites</span>
        </div>
    </div>

    <!-- Priority Levels Legend -->
    <div class="legend-section">
        <div class="legend-section-title">Priority Levels</div>

        <div class="legend-item">
            <div class="legend-node" style="background-color: #00C853;"></div>
            <span class="legend-text">Priority 5 - Highly Relevant</span>
        </div>

        <div class="legend-item">
            <div class="legend-node" style="background-color: #FFD600;"></div>
            <span class="legend-text">Priority 4 - Relevant</span>
        </div>

        <div class="legend-item">
            <div class="legend-node" style="background-color: #90CAF9;"></div>
            <span class="legend-text">Priority 3 - Partially Relevant</span>
        </div>

        <div class="legend-item">
            <div class="legend-node" style="background-color: #FFAB91;"></div>
            <span class="legend-text">Priority 2 - Weakly Relevant</span>
        </div>

        <div class="legend-item">
            <div class="legend-node" style="background-color: #E0E0E0;"></div>
            <span class="legend-text">Priority 1 - Irrelevant</span>
        </div>
    </div>

    <!-- Instructions -->
    <div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 11px; color: #666; line-height: 1.6;">
        <div style="margin-bottom: 4px;">Arrow Direction: A → B means A cites B</div>
        <div style="margin-bottom: 4px;">Node Size: Based on citation count</div>
        <div>Vertical Axis: Arranged by year, newer on top</div>
    </div>
</div>
"""

        # Insert legend before </body> tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', legend_html + '\n</body>')
        else:
            # If no </body> tag, append to end
            html_content += legend_html

        # Write back to file
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"   ✅ Legend added to graph")

    def get_graph_statistics(
        self,
        papers: List[Dict],
        relationships: List[Dict]
    ) -> Dict:
        """
        Calculate graph statistics

        Args:
            papers: Paper list
            relationships: Relationship list

        Returns:
            Statistics dictionary
        """
        # Priority distribution
        priority_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for paper in papers:
            priority = paper.get('priority', 3)
            priority_dist[priority] = priority_dist.get(priority, 0) + 1

        # Year range
        years = [p['year'] for p in papers if isinstance(p.get('year'), int)]
        year_range = (min(years), max(years)) if years else (None, None)

        # Relationship type distribution
        rel_type_dist = {}
        for rel in relationships:
            rel_type = rel.get('relationship_type', 'cites')
            rel_type_dist[rel_type] = rel_type_dist.get(rel_type, 0) + 1

        # Calculate average citations
        citations = [p.get('citation_count', 0) for p in papers]
        avg_citations = sum(citations) / len(citations) if citations else 0

        stats = {
            'total_papers': len(papers),
            'total_relationships': len(relationships),
            'priority_distribution': priority_dist,
            'year_range': year_range,
            'relationship_type_distribution': rel_type_dist,
            'average_citations': round(avg_citations, 1),
            'max_citations': max(citations) if citations else 0
        }

        return stats


if __name__ == "__main__":
    # Test visualization generator
    print("🍃 Testing visualization generator\n")

    visualizer = PaperGraphVisualizer()

    # Create test data
    test_papers = [
        {
            'paper_id': 'paper1',
            'title': 'Deep Learning for Autonomous Driving',
            'first_author': 'John Smith',
            'year': 2020,
            'priority': 5,
            'citation_count': 150,
            'venue': 'CVPR 2020',
            'matched_keywords': '["autonomous driving", "deep learning"]',
            'analysis_reason': 'Highly relevant, directly discusses deep learning methods for autonomous driving'
        },
        {
            'paper_id': 'paper2',
            'title': 'Machine Learning in Robotics',
            'first_author': 'Alice Wang',
            'year': 2021,
            'priority': 4,
            'citation_count': 80,
            'venue': 'ICRA 2021',
            'matched_keywords': '["machine learning", "robotics"]',
            'analysis_reason': 'Relevant, discusses machine learning applications in robotics'
        },
        {
            'paper_id': 'paper3',
            'title': 'Computer Vision Basics',
            'first_author': 'Bob Johnson',
            'year': 2019,
            'priority': 3,
            'citation_count': 200,
            'venue': 'ICCV 2019',
            'matched_keywords': '["computer vision"]',
            'analysis_reason': 'Partially relevant, computer vision fundamentals'
        }
    ]

    test_relationships = [
        {
            'source_paper_id': 'paper1',
            'target_paper_id': 'paper3',
            'relationship_type': 'builds_on',
            'relationship_desc': 'A builds on B computer vision theory'
        },
        {
            'source_paper_id': 'paper2',
            'target_paper_id': 'paper3',
            'relationship_type': 'improves',
            'relationship_desc': 'A improves B methods'
        }
    ]

    # Test 1: Basic graph generation
    print("=" * 60)
    print("Test 1: Basic graph generation")
    print("=" * 60)

    output_file = "test_graph.html"
    result = visualizer.generate(
        papers=test_papers,
        relationships=test_relationships,
        output_path=output_file
    )

    if result:
        print(f"✅ Graph generated: {result}")
        print(f"   Please open in browser to view")

    # Test 2: Graph statistics
    print("\n" + "=" * 60)
    print("Test 2: Graph statistics")
    print("=" * 60)

    stats = visualizer.get_graph_statistics(test_papers, test_relationships)
    print(f"✅ Statistics:")
    print(f"   Total papers: {stats['total_papers']}")
    print(f"   Total relationships: {stats['total_relationships']}")
    print(f"   Priority distribution: {stats['priority_distribution']}")
    print(f"   Year range: {stats['year_range']}")
    print(f"   Average citations: {stats['average_citations']}")

    # Test 3: Multi-keyword graphs
    print("\n" + "=" * 60)
    print("Test 3: Multi-keyword graphs")
    print("=" * 60)

    keywords = ["autonomous driving", "machine learning"]
    output_dir = "test_graphs"

    result_paths = visualizer.generate_multi_keyword_graphs(
        papers=test_papers,
        relationships=test_relationships,
        keywords=keywords,
        output_dir=output_dir
    )

    print(f"✅ Generated {len(result_paths)} graph files:")
    for keyword, path in result_paths.items():
        print(f"   {keyword}: {path}")

    print("\n🎉 All tests completed!")
