"""
Database Module - Responsible for SQLite database creation and operations
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


def init_database(db_path: str = "data/blatt.db"):
    """
    Initialize database, create all necessary tables

    Args:
        db_path: Database file path
    """
    # Ensure directory exists (except for memory database)
    if db_path != ':memory:':
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Create papers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            authors TEXT,
            first_author TEXT,
            year INTEGER,
            abstract TEXT,
            doi TEXT,
            citation_count INTEGER DEFAULT 0,
            url TEXT,
            venue TEXT,
            fields_of_study TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes to speed up queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_paper_id ON papers(paper_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON papers(year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citation_count ON papers(citation_count)')

    # 2. Create relationships table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_paper_id TEXT NOT NULL,
            target_paper_id TEXT NOT NULL,
            relationship_type TEXT DEFAULT 'cites',
            relationship_desc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_paper_id) REFERENCES papers(paper_id),
            FOREIGN KEY (target_paper_id) REFERENCES papers(paper_id),
            UNIQUE(source_paper_id, target_paper_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_paper ON relationships(source_paper_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_target_paper ON relationships(target_paper_id)')

    # 3. Create search history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT NOT NULL,
            description TEXT,
            total_papers INTEGER DEFAULT 0,
            relevant_papers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'in_progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # 4. Create paper scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            paper_id TEXT NOT NULL,
            priority INTEGER CHECK(priority >= 1 AND priority <= 5),
            matched_keywords TEXT,
            analysis_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (search_id) REFERENCES search_history(id),
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id),
            UNIQUE(search_id, paper_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_paper ON paper_scores(search_id, paper_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_priority ON paper_scores(priority)')

    conn.commit()
    conn.close()

    print(f"✅ Database initialized successfully: {db_path}")


class Database:
    """Database operations class"""

    def __init__(self, db_path: str = "data/blatt.db"):
        self.db_path = db_path
        self._conn = None  # Persistent connection for in-memory database

        # For in-memory database, keep connection open
        if db_path == ':memory:':
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
            self._init_tables(self._conn)
        else:
            init_database(db_path)

    def _init_tables(self, conn):
        """Initialize tables on the given connection"""
        cursor = conn.cursor()

        # Create papers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                authors TEXT,
                first_author TEXT,
                year INTEGER,
                abstract TEXT,
                doi TEXT,
                citation_count INTEGER DEFAULT 0,
                url TEXT,
                venue TEXT,
                fields_of_study TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_paper_id ON papers(paper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON papers(year)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_citation_count ON papers(citation_count)')

        # Create relationships table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_paper_id TEXT NOT NULL,
                target_paper_id TEXT NOT NULL,
                relationship_type TEXT DEFAULT 'cites',
                relationship_desc TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_paper_id, target_paper_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_paper ON relationships(source_paper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_target_paper ON relationships(target_paper_id)')

        # Create search_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keywords TEXT NOT NULL,
                description TEXT,
                total_papers INTEGER DEFAULT 0,
                relevant_papers INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        # Create paper_scores table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                paper_id TEXT NOT NULL,
                priority INTEGER CHECK(priority >= 1 AND priority <= 5),
                matched_keywords TEXT,
                analysis_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(search_id, paper_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_paper ON paper_scores(search_id, paper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_priority ON paper_scores(priority)')

        conn.commit()

    def get_connection(self):
        """Get database connection"""
        if self._conn:
            return self._conn  # Return persistent connection (in-memory database)
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _close_connection(self, conn):
        """Close connection (except for in-memory database)"""
        if not self._conn:  # Only close non-persistent connections
            conn.close()

    # ==================== Paper Operations ====================

    def add_or_update_paper(self, paper_data) -> int:
        """
        Add or update paper

        Args:
            paper_data: Paper object or paper data dictionary

        Returns:
            Paper ID in database
        """
        from src.models.paper import Paper

        # If it's a Paper object, convert to dictionary
        if isinstance(paper_data, Paper):
            paper_data = paper_data.to_db_dict()

        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if paper already exists
        cursor.execute('SELECT id FROM papers WHERE paper_id = ?', (paper_data['paper_id'],))
        existing = cursor.fetchone()

        if existing:
            # Update existing paper
            cursor.execute('''
                UPDATE papers SET
                    title = ?, authors = ?, first_author = ?, year = ?,
                    abstract = ?, doi = ?, citation_count = ?, url = ?,
                    venue = ?, fields_of_study = ?, updated_at = CURRENT_TIMESTAMP
                WHERE paper_id = ?
            ''', (
                paper_data['title'],
                paper_data['authors'],
                paper_data['first_author'],
                paper_data['year'],
                paper_data['abstract'],
                paper_data['doi'],
                paper_data['citation_count'],
                paper_data['url'],
                paper_data['venue'],
                paper_data['fields_of_study'],
                paper_data['paper_id']
            ))
            paper_db_id = existing[0]
        else:
            # Insert new paper
            cursor.execute('''
                INSERT INTO papers (
                    paper_id, title, authors, first_author, year,
                    abstract, doi, citation_count, url, venue, fields_of_study
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                paper_data['paper_id'],
                paper_data['title'],
                paper_data['authors'],
                paper_data['first_author'],
                paper_data['year'],
                paper_data['abstract'],
                paper_data['doi'],
                paper_data['citation_count'],
                paper_data['url'],
                paper_data['venue'],
                paper_data['fields_of_study']
            ))
            paper_db_id = cursor.lastrowid

        conn.commit()
        self._close_connection(conn)
        return paper_db_id

    def get_paper_by_id(self, paper_id: str) -> Optional[Dict]:
        """Get paper by paper_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM papers WHERE paper_id = ?', (paper_id,))
        row = cursor.fetchone()
        self._close_connection(conn)

        if row:
            return dict(row)
        return None

    # ==================== Relationship Operations ====================

    def add_relationship(self, source_id: str, target_id: str,
                        rel_type: str = 'cites', rel_desc: str = None) -> int:
        """
        Add paper relationship

        Args:
            source_id: Citing paper ID
            target_id: Cited paper ID
            rel_type: Relationship type
            rel_desc: Relationship description

        Returns:
            Relationship record ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO relationships
            (source_paper_id, target_paper_id, relationship_type, relationship_desc)
            VALUES (?, ?, ?, ?)
        ''', (source_id, target_id, rel_type, rel_desc))

        rel_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        return rel_id

    def get_relationships_for_paper(self, paper_id: str) -> List[Dict]:
        """
        Get all relationships for a paper (including as source and target)

        Args:
            paper_id: Paper ID

        Returns:
            List of relationships
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM relationships
            WHERE source_paper_id = ? OR target_paper_id = ?
        ''', (paper_id, paper_id))

        rows = cursor.fetchall()
        self._close_connection(conn)

        return [dict(row) for row in rows]

    def get_all_relationships_for_papers(self, paper_ids: List[str]) -> List[Dict]:
        """
        Get all relationships between multiple papers

        Args:
            paper_ids: List of paper IDs

        Returns:
            List of relationships
        """
        if not paper_ids:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        # Build IN clause
        placeholders = ','.join(['?'] * len(paper_ids))
        query = f'''
            SELECT * FROM relationships
            WHERE source_paper_id IN ({placeholders})
            AND target_paper_id IN ({placeholders})
        '''

        cursor.execute(query, paper_ids + paper_ids)
        rows = cursor.fetchall()
        self._close_connection(conn)

        return [dict(row) for row in rows]

    def update_relationship(self, source_id: str, target_id: str,
                          rel_type: str = None, rel_desc: str = None) -> None:
        """
        Update relationship type and description

        Args:
            source_id: Citing paper ID
            target_id: Cited paper ID
            rel_type: New relationship type (optional)
            rel_desc: New relationship description (optional)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        values = []

        if rel_type is not None:
            updates.append('relationship_type = ?')
            values.append(rel_type)
        if rel_desc is not None:
            updates.append('relationship_desc = ?')
            values.append(rel_desc)

        if updates:
            query = f'''
                UPDATE relationships
                SET {', '.join(updates)}, created_at = CURRENT_TIMESTAMP
                WHERE source_paper_id = ? AND target_paper_id = ?
            '''
            values.extend([source_id, target_id])
            cursor.execute(query, values)

        conn.commit()
        self._close_connection(conn)

    def relationship_exists(self, source_id: str, target_id: str) -> bool:
        """
        Check if relationship already exists

        Args:
            source_id: Citing paper ID
            target_id: Cited paper ID

        Returns:
            Whether exists
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM relationships
            WHERE source_paper_id = ? AND target_paper_id = ?
        ''', (source_id, target_id))

        count = cursor.fetchone()[0]
        self._close_connection(conn)

        return count > 0

    # ==================== Search History Operations ====================

    def create_search_history(self, keywords: str, description: str = "") -> int:
        """Create search history record"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO search_history (keywords, description)
            VALUES (?, ?)
        ''', (keywords, description))

        search_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        return search_id

    def update_search_history(self, search_id: int, **kwargs):
        """Update search history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Build dynamic update statement
        updates = []
        values = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)

        if updates:
            query = f"UPDATE search_history SET {', '.join(updates)} WHERE id = ?"
            values.append(search_id)
            cursor.execute(query, values)

        conn.commit()
        self._close_connection(conn)

    def get_search_history(self, search_id: int) -> Dict:
        """Get search history record"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM search_history WHERE id = ?
        ''', (search_id,))

        row = cursor.fetchone()
        self._close_connection(conn)

        return dict(row) if row else None

    # ==================== Scoring Operations ====================

    def add_paper_score(self, search_id: int, paper_id: str, priority: int,
                       matched_keywords: List[str], analysis_reason: str) -> int:
        """Add paper score result"""
        conn = self.get_connection()
        cursor = conn.cursor()

        keywords_json = json.dumps(matched_keywords, ensure_ascii=False)

        cursor.execute('''
            INSERT OR REPLACE INTO paper_scores
            (search_id, paper_id, priority, matched_keywords, analysis_reason)
            VALUES (?, ?, ?, ?, ?)
        ''', (search_id, paper_id, priority, keywords_json, analysis_reason))

        score_id = cursor.lastrowid
        conn.commit()
        self._close_connection(conn)
        return score_id

    def get_scored_papers(self, search_id: int, min_priority: int = 3) -> List[Dict]:
        """Get papers with priority >= min_priority from a search"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.*, ps.priority, ps.matched_keywords, ps.analysis_reason
            FROM papers p
            JOIN paper_scores ps ON p.paper_id = ps.paper_id
            WHERE ps.search_id = ? AND ps.priority >= ?
            ORDER BY ps.priority DESC, p.citation_count DESC
        ''', (search_id, min_priority))

        rows = cursor.fetchall()
        self._close_connection(conn)

        return [dict(row) for row in rows]


if __name__ == "__main__":
    # Test database initialization
    db = Database()
    print("✅ Database module test passed")
