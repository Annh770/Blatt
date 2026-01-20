"""
Blatt - Flask Web Application
AI-Powered Academic Paper Search Assistant
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from config import Config
from src.models.database import Database
from src.core.multi_source_searcher import MultiSourceSearcher
from src.core.citation_expander import CitationExpander
from src.core.ai_analyzer import AIAnalyzer
from src.core.visualizer import PaperGraphVisualizer
from src.core.smart_query_builder import SmartQueryBuilder
from src.core.rule_based_filter import RuleBasedFilter
from src.core.keyword_expander import KeywordExpander
from src.core.query_translator import QueryTranslator
from src.core.hard_requirements_checker import HardRequirementsChecker
from src.utils.excel_exporter import ExcelExporter
from src.utils.bibtex_exporter import BibTeXExporter
import os
import logging
import json
from datetime import datetime
import re
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)

# Validate configuration
Config.validate()

# Initialize database
db = Database(Config.DATABASE_PATH)

# Initialize core components
searcher = MultiSourceSearcher(db, s2_api_key=Config.SEMANTIC_SCHOLAR_API_KEY)
expander = CitationExpander(db, s2_api_key=Config.SEMANTIC_SCHOLAR_API_KEY)
visualizer = PaperGraphVisualizer()
excel_exporter = ExcelExporter()
bibtex_exporter = BibTeXExporter()
query_builder = SmartQueryBuilder()
rule_filter = RuleBasedFilter()
hard_checker = HardRequirementsChecker()


def _split_keywords_for_concepts(text: str) -> List[str]:
    parts = re.split(r'[,;/\n]', text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _sanitize_core_concepts(
    raw_concepts,
    keywords: str,
    professional_terms: Optional[List[str]] = None
) -> List[Dict[str, List[str]]]:
    sanitized: List[Dict[str, List[str]]] = []

    def append_concept(name: str, synonyms: List[str]):
        cleaned = [s.strip() for s in (synonyms or []) if s and s.strip()]
        base = name.strip() if name else ""
        if not cleaned and base:
            cleaned = [base]
        if cleaned:
            sanitized.append({
                "name": base or cleaned[0],
                "synonyms": cleaned
            })

    if isinstance(raw_concepts, list):
        for item in raw_concepts:
            if isinstance(item, dict):
                append_concept(item.get("name", ""), item.get("synonyms", []))
            elif isinstance(item, str):
                append_concept(item, [item])
            elif isinstance(item, (list, tuple)):
                values = [str(v) for v in item if v]
                if values:
                    append_concept(values[0], values)

    if not sanitized:
        fallback_terms = _split_keywords_for_concepts(keywords)
        if professional_terms:
            fallback_terms.extend(professional_terms)
        seen = set()
        fallback = []
        for term in fallback_terms:
            key = term.lower()
            if key and key not in seen:
                seen.add(key)
                fallback.append(term)
        for term in fallback[:3]:
            append_concept(term, [term])

    return sanitized


def _dedupe_papers_by_title(papers: List[Dict]) -> List[Dict]:
    seen = {}
    for paper in papers:
        title = (paper.get('title') or '').strip().lower()
        year = paper.get('year')
        key = (title, year) if title else (paper.get('paper_id'), year)
        if key not in seen:
            seen[key] = paper
    return list(seen.values())

# Initialize AI analyzer and smart query translator (if API key is available)
ai_analyzer = None
query_translator = None
keyword_expander = None  # Keep old expander as fallback
if Config.CLAUDE_API_KEY:
    ai_analyzer = AIAnalyzer(db, Config.CLAUDE_API_KEY)
    # Smart query translator shares the same Claude client
    query_translator = QueryTranslator(claude_client=ai_analyzer.claude_client)
    keyword_expander = KeywordExpander(claude_client=ai_analyzer.claude_client)
    logger.info("✅ AI Analyzer initialized with Claude API")
    logger.info("✅ Query Translator initialized")
    logger.info("✅ Keyword Expander initialized")
else:
    logger.warning("⚠️  Claude API Key not set - AI analysis will be skipped")
    logger.warning("⚠️  Query Translator disabled - using fallback mode")
    query_translator = QueryTranslator()  # No API mode
    keyword_expander = KeywordExpander()  # No API mode


# ==================== Jinja2 Filters ====================
@app.template_filter('from_json')
def from_json_filter(value):
    """Convert JSON string to Python object"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value or []


# ==================== Route Definitions ====================

@app.route('/')
def index():
    """Homepage - Search form"""
    return render_template('index.html')

@app.after_request
def add_header(response):
    """Disable caching to ensure latest CSS is loaded"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.route('/search', methods=['POST'])
def search():
    """Handle search request"""
    try:
        # Get user input
        keywords = request.form.get('keywords', '').strip()
        description = request.form.get('description', '').strip()
        paper_count = int(request.form.get('paper_count', Config.INITIAL_PAPER_COUNT))
        citation_depth = int(request.form.get('citation_depth', Config.MAX_CITATION_DEPTH))

        if not keywords:
            return jsonify({'error': 'Please enter keywords'}), 400

        logger.info(f"New search request: {keywords}")

        # Create search history record
        search_id = db.create_search_history(keywords, description)

        # Start background task for search processing
        result = process_search(
            search_id, keywords, description,
            paper_count, citation_depth
        )

        return jsonify({
            'search_id': search_id,
            'status': 'completed',
            'result': result
        })

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def process_search(search_id, keywords, description,
                   paper_count=10, citation_depth=1):
    """
    Core search processing logic

    Returns:
        dict: Search result statistics
    """
    logger.info(f"[Search {search_id}] Starting processing")

    try:
        # ===== Strategy 3: Smart Translation Search Flow: Claude Translation + Precise Query =====

        # Step 0: Claude smart query translation (translate user input to professional academic queries)
        translation_result = None
        original_keywords_list = None
        expanded_keywords_list = None
        query_list = []

        logger.info(f"[Search {search_id}] Step 0: Query translation with Claude")
        translation_result = query_translator.translate(keywords, description)

        # Extract translation information
        semantic_understanding = translation_result.get('semantic_understanding', '')
        professional_terms = translation_result.get('professional_terms', [])
        avoid_terms = translation_result.get('avoid_terms', [])
        reasoning = translation_result.get('reasoning', '')
        core_concepts = _sanitize_core_concepts(
            translation_result.get('core_concepts'),
            keywords,
            professional_terms
        )
        relaxed_concepts = _sanitize_core_concepts(
            [],
            keywords,
            professional_terms
        )
        hard_guard_active = bool(core_concepts or avoid_terms)

        logger.info(f"[Search {search_id}] 🎯 Semantic understanding: {semantic_understanding}")
        logger.info(f"[Search {search_id}] 📚 Professional terms: {professional_terms[:5]}...")
        if avoid_terms:
            logger.info(f"[Search {search_id}] 🚫 Avoid terms: {avoid_terms}")
        logger.info(f"[Search {search_id}] 💡 Translation reasoning: {reasoning}")

        # Step 1A: Use translated query combinations
        query_combinations = translation_result.get('query_combinations', [])

        if query_combinations:
            # Use Claude's translated query combinations
            logger.info(f"[Search {search_id}] Step 1A: Using translated query combinations")
            # Keep dictionary format, add strategy field
            query_list = [
                {
                    "query": qc['query'],
                    "strategy": qc.get('focus', 'translated'),
                    "weight": qc.get('weight', 1.0)
                }
                for qc in query_combinations
            ]
            logger.info(f"[Search {search_id}] Generated {len(query_list)} translated queries")

            # Display query details
            for i, qc in enumerate(query_combinations[:3], 1):
                logger.info(f"[Search {search_id}]   Query {i} [{qc.get('weight', 1.0)}]: {qc['query']}")
                logger.info(f"[Search {search_id}]     Focus: {qc.get('focus', 'N/A')}")
        else:
            # Fallback: use traditional query builder
            logger.warning(f"[Search {search_id}] No translated queries, using fallback query builder")
            keywords_for_query = keywords
            if professional_terms:
                keywords_for_query = ', '.join(professional_terms[:8])
            query_list = query_builder.build_query_combinations(keywords_for_query, description, max_combinations=6)
            logger.info(f"[Search {search_id}] Generated {len(query_list)} fallback queries")

        # Save keywords for subsequent scoring
        original_keywords_list = [keywords]  # User's original input
        expanded_keywords_list = professional_terms  # Claude translated professional terms

        # Step 1B: Multi-query parallel search (Phase 2J: improve recall rate)
        logger.info(f"[Search {search_id}] Step 1B: Multi-query parallel search")
        candidate_papers = searcher.search_with_multiple_queries(
            query_list,
            papers_per_query=12,  # Phase 2J optimization: increased to 12 (10→12), supports 12-15 queries
            total_limit=200,      # Phase 2J optimization: increased to 200 (150→200), fully utilize queries
            year_from=None
        )
        logger.info(f"[Search {search_id}] Found {len(candidate_papers)} candidate papers")

        # Search 13 config: skip rule-based filtering, send all candidate papers directly to AI analysis
        from src.models.paper import Paper
        initial_papers = candidate_papers  # Use all candidate papers directly

        logger.info(f"[Search {search_id}] Using all {len(initial_papers)} candidates (Search 13 config)")

        def apply_hard_requirements(papers, stage_label, fallback_on_empty=True):
            """Lightweight gatekeeper: filter papers that clearly don't match domain/concept/avoid_terms"""
            if not papers:
                return papers

            def run_guard(concepts):
                if not concepts:
                    return [], []
                kept_local = []
                rejected_local = []
                for paper in papers:
                    is_ok, _, reason = hard_checker.check_priority5_eligibility(
                        paper_title=paper.title or "",
                        paper_abstract=paper.abstract or "",
                        user_keywords=keywords,
                        user_description=description,
                        required_concepts=concepts,
                        avoid_terms=avoid_terms
                    )
                    if is_ok:
                        kept_local.append(paper)
                    else:
                        rejected_local.append((paper, reason))
                return kept_local, rejected_local

            concepts_primary = core_concepts or relaxed_concepts
            kept, rejected = run_guard(concepts_primary)

            if rejected:
                logger.info(
                    f"[Search {search_id}] {stage_label}: "
                    f"filtered {len(rejected)}/{len(papers)} papers by hard requirements"
                )
                for paper, reason in rejected[:5]:
                    logger.debug(
                        f"[Search {search_id}]   Rejected '{paper.title[:80]}' -> {reason}"
                    )

            if not kept and core_concepts and relaxed_concepts and concepts_primary is not relaxed_concepts:
                logger.warning(
                    f"[Search {search_id}] {stage_label}: no papers left after strict guard, "
                    "retrying with relaxed keyword-based concepts"
                )
                kept, rejected_relaxed = run_guard(relaxed_concepts)
                if rejected_relaxed:
                    logger.info(
                        f"[Search {search_id}] {stage_label} (relaxed): "
                        f"filtered {len(rejected_relaxed)}/{len(papers)} papers"
                    )

            if kept and len(kept) < 30:
                logger.warning(
                    f"[Search {search_id}] {stage_label}: only {len(kept)} papers kept; "
                    "fallback to avoid-terms only to ensure coverage"
                )
                kept = papers

            if not kept and fallback_on_empty:
                logger.warning(
                    f"[Search {search_id}] {stage_label}: all papers were filtered. "
                    "Falling back to original list to avoid empty results."
                )
                return papers

            return kept

        if ai_analyzer:
            filtered_initial = apply_hard_requirements(
                initial_papers,
                "Initial candidate guard",
                fallback_on_empty=not hard_guard_active
            )
            if filtered_initial:
                initial_papers = filtered_initial
                logger.info(
                    f"[Search {search_id}] Hard guard kept {len(initial_papers)} papers for AI scoring"
                )

        if not initial_papers:
            logger.warning(f"[Search {search_id}] No papers found")
            db.update_search_history(
                search_id, total_papers=0, relevant_papers=0,
                status='completed'
            )
            return {'total_papers': 0, 'relevant_papers': 0}

        # Step 2A: AI scoring for initial papers (identify Priority 4-5 as expansion seeds)
        if ai_analyzer:
            logger.info(f"[Search {search_id}] Step 2A: Initial AI scoring to identify high-value seeds")
            ai_analyzer.score_papers(initial_papers, search_id, keywords, description)

            # Get Priority 5 and Priority 4 papers as expansion seeds
            priority5_papers_dict = db.get_scored_papers(search_id, min_priority=5)
            priority4_papers_dict = db.get_scored_papers(search_id, min_priority=4)

            priority5_papers = [Paper.from_db_dict(p) for p in priority5_papers_dict]
            priority4_papers = [Paper.from_db_dict(p) for p in priority4_papers_dict if p['priority'] == 4]

            logger.info(f"   Found {len(priority5_papers)} Priority 5 papers (will expand deeply)")
            logger.info(f"   Found {len(priority4_papers)} Priority 4 papers (will expand moderately)")

            # Step 2B: Two-phase citation expansion (only for Priority 4-5)
            all_papers = initial_papers.copy()

            if citation_depth > 0 and (priority5_papers or priority4_papers):
                logger.info(f"[Search {search_id}] Step 2B: Query-based intelligent citation expansion (Phase 2I)")

                # Phase 2J improvement: increase citation expansion limit to improve recall rate
                # Stage 1: Expand Priority 5 papers (query filtering + 12 papers/paper + global 180 papers)
                if priority5_papers:
                    logger.info(f"   Expanding {len(priority5_papers)} Priority 5 papers with query filtering...")
                    p5_expansion = expander.expand_with_query_filtering(
                        priority5_papers,
                        translated_queries=query_list,  # Phase 2I: use translated queries for filtering
                        depth=citation_depth,
                        per_paper_limit=12,   # Phase 2J: keep 12 papers/paper
                        global_limit=180      # Phase 2J optimization: increased to 180 (supports 15 P5×12)
                    )
                    all_papers.extend([p for p in p5_expansion['papers'] if p.paper_id not in {paper.paper_id for paper in all_papers}])
                    logger.info(f"   → Priority 5 expansion added {len(p5_expansion['papers']) - len(priority5_papers)} new papers")
                    logger.info(f"   → Used {p5_expansion['stats'].get('queries_used', 0)} queries for filtering")

                # Stage 2: Expand Priority 4 papers (query filtering + 10 papers/paper + global 150 papers)
                if priority4_papers:
                    logger.info(f"   Expanding {len(priority4_papers)} Priority 4 papers with query filtering...")
                    p4_expansion = expander.expand_with_query_filtering(
                        priority4_papers,
                        translated_queries=query_list,  # Phase 2I: use translated queries for filtering
                        depth=citation_depth,
                        per_paper_limit=10,   # Phase 2J optimization: P4 reduced to 10 (prioritize P5 full expansion)
                        global_limit=150      # Phase 2J optimization: increased to 150 (moderate total control)
                    )
                    all_papers.extend([p for p in p4_expansion['papers'] if p.paper_id not in {paper.paper_id for paper in all_papers}])
                    logger.info(f"   → Priority 4 expansion added {len(p4_expansion['papers']) - len(priority4_papers)} new papers")
                    logger.info(f"   → Used {p4_expansion['stats'].get('queries_used', 0)} queries for filtering")

                logger.info(f"[Search {search_id}] Total papers after expansion: {len(all_papers)}")

                # Step 2C: AI scoring for newly expanded papers
                new_papers = [p for p in all_papers if p.paper_id not in {paper.paper_id for paper in initial_papers}]
                if new_papers:
                    new_papers = apply_hard_requirements(
                        new_papers,
                        "Expanded papers guard",
                        fallback_on_empty=not hard_guard_active
                    )
                if new_papers:
                    logger.info(f"[Search {search_id}] Step 2C: AI scoring for {len(new_papers)} newly expanded papers")
                    ai_analyzer.score_papers(new_papers, search_id, keywords, description)
            else:
                logger.info(f"[Search {search_id}] No Priority 4-5 papers found, skipping citation expansion")
        else:
            # No AI case: follow original expansion flow
            all_papers = initial_papers
            if citation_depth > 0:
                logger.info(f"[Search {search_id}] Step 2: Expanding citations (depth={citation_depth})")
                expansion_result = expander.expand(
                    initial_papers,
                    depth=citation_depth,
                    citation_limit=Config.CITATION_EXPAND_LIMIT
                )
                all_papers = expansion_result['papers']
                logger.info(f"[Search {search_id}] Expanded to {len(all_papers)} papers")

            # Set default scores for all papers
            logger.warning(f"[Search {search_id}] AI analysis skipped (no API key)")
            for paper in all_papers:
                db.add_paper_score(
                    search_id=search_id,
                    paper_id=paper.paper_id,
                    priority=3,  # 默认Priority 3
                    matched_keywords=[],
                    analysis_reason='No AI analysis (API key not set)'
                )

        # Step 4: Get high-scoring papers
        effective_min_priority = max(Config.MIN_PRIORITY_THRESHOLD, 4)
        scored_papers = db.get_scored_papers(
            search_id,
            min_priority=effective_min_priority
        )
        original_count = len(scored_papers)
        scored_papers = [
            paper for paper in scored_papers
            if paper.get('priority', 0) >= effective_min_priority
        ]
        deduped = _dedupe_papers_by_title(scored_papers)
        if len(deduped) != len(scored_papers):
            logger.info(
                f"[Search {search_id}] Removed {len(scored_papers) - len(deduped)} duplicate entries by title"
            )
        scored_papers = deduped
        logger.info(
            f"[Search {search_id}] {len(scored_papers)} relevant papers "
            f"(filtered from {original_count})"
        )

        # Step 5: Analyze paper relationships (if AI available)
        if ai_analyzer and scored_papers:
            logger.info(f"[Search {search_id}] Step 4: Analyzing relationships")
            relationships = db.get_all_relationships_for_papers(
                [p['paper_id'] for p in scored_papers]
            )

            # Select important relationships for AI analysis (max 50)
            important_rels = relationships[:50]
            paper_dict = {p['paper_id']: p for p in scored_papers}

            paper_pairs = []
            for rel in important_rels:
                source = paper_dict.get(rel['source_paper_id'])
                target = paper_dict.get(rel['target_paper_id'])
                if source and target:
                    from src.models.paper import Paper
                    source_paper = Paper.from_db_dict(source)
                    target_paper = Paper.from_db_dict(target)
                    paper_pairs.append((source_paper, target_paper))

            if paper_pairs:
                ai_analyzer.analyze_relationships(paper_pairs)

        # Step 6: Export data
        logger.info(f"[Search {search_id}] Step 5: Exporting data")

        # Create export directories
        os.makedirs(f"{Config.EXPORT_DIR}/excel", exist_ok=True)
        os.makedirs(f"{Config.EXPORT_DIR}/bibtex", exist_ok=True)
        os.makedirs(f"{Config.EXPORT_DIR}/visualizations", exist_ok=True)

        graph_path = None

        # Export Excel
        excel_path = f"{Config.EXPORT_DIR}/excel/search_{search_id}_papers.xlsx"
        excel_exporter.export(scored_papers, excel_path)

        # Export BibTeX
        bibtex_path = f"{Config.EXPORT_DIR}/bibtex/search_{search_id}_papers.bib"
        bibtex_exporter.export(scored_papers, bibtex_path)

        # Generate visualization graph
        if scored_papers:
            relationships = db.get_all_relationships_for_papers(
                [p['paper_id'] for p in scored_papers]
            )
            graph_path = f"{Config.EXPORT_DIR}/visualizations/search_{search_id}_graph.html"
            visualizer.generate(
                scored_papers,
                relationships,
                graph_path,
                title=f"Paper Network: {keywords}"
            )

        # Step 7: Update search history status (save translation results)
        db.update_search_history(
            search_id,
            total_papers=len(all_papers),
            relevant_papers=len(scored_papers),
            status='completed',
            translation_result=json.dumps(translation_result) if translation_result else None
        )

        logger.info(f"[Search {search_id}] Completed successfully")

        return {
            'total_papers': len(all_papers),
            'relevant_papers': len(scored_papers),
            'excel_path': excel_path,
            'bibtex_path': bibtex_path,
            'graph_path': graph_path
        }

    except Exception as e:
        logger.error(f"[Search {search_id}] Failed: {e}", exc_info=True)
        db.update_search_history(search_id, status='failed')
        raise


@app.route('/results/<int:search_id>')
def results(search_id):
    """Results display page"""
    try:
        # Get search history
        search = db.get_search_history(search_id)
        if not search:
            return "Search not found", 404

        # Get paper list
        papers = db.get_scored_papers(search_id, min_priority=Config.MIN_PRIORITY_THRESHOLD)

        return render_template(
            'results.html',
            search=search,
            papers=papers
        )

    except Exception as e:
        logger.error(f"Failed to load results: {e}", exc_info=True)
        return f"Error: {e}", 500


@app.route('/download/<path:filename>')
def download(filename):
    """Download exported file"""
    try:
        file_path = os.path.join(Config.EXPORT_DIR, filename)
        if not os.path.exists(file_path):
            return "File not found", 404

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        return f"Error: {e}", 500


@app.route('/graph/<int:search_id>')
def view_graph(search_id):
    """View visualization graph"""
    try:
        graph_path = f"{Config.EXPORT_DIR}/visualizations/search_{search_id}_graph.html"
        if not os.path.exists(graph_path):
            return "Graph not found", 404

        return send_file(graph_path)

    except Exception as e:
        logger.error(f"Failed to load graph: {e}", exc_info=True)
        return f"Error: {e}", 500


# ==================== Error Handling ====================

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('base.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"Internal error: {error}", exc_info=True)
    return render_template('base.html'), 500


# ==================== Main Entry Point ====================

if __name__ == '__main__':
    print("=" * 70)
    print("🍃 Blatt - AI-Powered Academic Paper Search Assistant")
    print("=" * 70)
    print(f"Environment: {Config.FLASK_ENV}")
    print(f"Debug mode: {Config.FLASK_DEBUG}")
    print(f"Database: {Config.DATABASE_PATH}")
    print(f"AI Analysis: {'Enabled' if ai_analyzer else 'Disabled (no API key)'}")
    print("=" * 70)
    print(f"\nStarting server at http://0.0.0.0:5000")
    print("Press Ctrl+C to quit\n")

    app.run(
        debug=Config.FLASK_DEBUG,
        host='0.0.0.0',
        port=5000
    )
