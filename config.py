"""
Configuration Management Module - Centralized configuration management
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Application configuration class"""

    # ==================== API Configuration ====================
    CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
    SEMANTIC_SCHOLAR_API_KEY = os.getenv('SEMANTIC_SCHOLAR_API_KEY', '')

    # ==================== API Request Configuration ====================
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '1.0'))

    # ==================== Paper Search Configuration ====================
    INITIAL_PAPER_COUNT = int(os.getenv('INITIAL_PAPER_COUNT', '10'))
    CITATION_EXPAND_LIMIT = int(os.getenv('CITATION_EXPAND_LIMIT', '20'))
    MAX_CITATION_DEPTH = int(os.getenv('MAX_CITATION_DEPTH', '1'))
    MIN_CITATION_COUNT = int(os.getenv('MIN_CITATION_COUNT', '5'))
    TIME_WINDOW_YEARS = int(os.getenv('TIME_WINDOW_YEARS', '10'))

    # ==================== Database Configuration ====================
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/blatt.db')

    # ==================== Export Configuration ====================
    EXPORT_DIR = os.getenv('EXPORT_DIR', 'exports')
    MIN_PRIORITY_THRESHOLD = int(os.getenv('MIN_PRIORITY_THRESHOLD', '4'))  # Phase 2C: only export Priority 4-5

    # ==================== Flask Configuration ====================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-please-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')

    # ==================== File Upload Configuration ====================
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    @classmethod
    def validate(cls):
        """Validate required configuration items"""
        if not cls.CLAUDE_API_KEY:
            print("⚠️  Warning: CLAUDE_API_KEY not set! AI analysis will be unavailable.")
            print("   Please set CLAUDE_API_KEY in .env file")

        if not cls.SEMANTIC_SCHOLAR_API_KEY:
            print("ℹ️  Note: SEMANTIC_SCHOLAR_API_KEY not set.")
            print("   Using an API Key can increase rate limits, but is not required.")

    @classmethod
    def get_summary(cls):
        """Get configuration summary (for debugging)"""
        return {
            'CLAUDE_API_KEY': '***' + cls.CLAUDE_API_KEY[-4:] if cls.CLAUDE_API_KEY else 'Not Set',
            'SEMANTIC_SCHOLAR_API_KEY': '***' + cls.SEMANTIC_SCHOLAR_API_KEY[-4:] if cls.SEMANTIC_SCHOLAR_API_KEY else 'Not Set',
            'DATABASE_PATH': cls.DATABASE_PATH,
            'INITIAL_PAPER_COUNT': cls.INITIAL_PAPER_COUNT,
            'CITATION_EXPAND_LIMIT': cls.CITATION_EXPAND_LIMIT,
            'MAX_CITATION_DEPTH': cls.MAX_CITATION_DEPTH,
            'MIN_PRIORITY_THRESHOLD': cls.MIN_PRIORITY_THRESHOLD,
            'FLASK_ENV': cls.FLASK_ENV,
            'FLASK_DEBUG': cls.FLASK_DEBUG,
        }


if __name__ == '__main__':
    """Test configuration module"""
    print("🍃 Blatt - Configuration Test\n")

    # Validate configuration
    Config.validate()

    # Display configuration summary
    print("\n" + "="*60)
    print("Configuration Summary:")
    print("="*60)

    summary = Config.get_summary()
    for key, value in summary.items():
        print(f"{key:30s}: {value}")

    print("\n✅ Configuration loaded successfully!")
