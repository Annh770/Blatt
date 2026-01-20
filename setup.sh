#!/bin/bash

# ============================================
# Blatt Project Initialization Script
# Collect literature like collecting leaves
# ============================================
set -e  # Exit immediately on error

echo "🌻 Starting Blatt project initialization..."
echo ""

# 1. Check Python version
echo "📌 Step 1: Check Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Error: Python3 not found, please install Python 3.9+"
    exit 1
fi
echo "✅ Python version check passed"
echo ""

# 2. Create virtual environment
echo "📌 Step 2: Create Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created successfully"
else
    echo "ℹ️  Virtual environment already exists, skipping creation"
fi
echo ""

# 3. Activate virtual environment and install dependencies
echo "📌 Step 3: Install project dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# 4. Create necessary directories
echo "📌 Step 4: Create runtime directories..."
mkdir -p data
mkdir -p exports/excel
mkdir -p exports/bibtex
mkdir -p exports/visualizations
mkdir -p logs
mkdir -p data/cache
echo "✅ Directories created"
echo ""

# 5. Check configuration file
echo "📌 Step 5: Check configuration file..."
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file does not exist"
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  Important: Please edit .env file and fill in your Claude API Key:"
    echo "   nano .env"
    echo "   or"
    echo "   vim .env"
    echo ""
else
    echo "✅ .env file already exists"

    # Check if API Key is configured
    if grep -q "your_claude_api_key_here" .env; then
        echo "⚠️  Warning: Claude API Key in .env is not configured yet"
        echo "Please edit .env file and fill in a valid API Key"
        echo ""
    else
        echo "✅ Claude API Key is configured"
    fi
fi
echo ""

# 6. Initialize database
echo "📌 Step 6: Initialize SQLite database..."
python3 << END
try:
    from src.models.database import init_database
    init_database('data/blatt.db')
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"⚠️  Database initialization failed: {e}")
    print("This is normal because the database module has not been implemented yet")
    print("Run this step again after implementing src/models/database.py")
END
echo ""

# 7. Display next steps
echo "============================================"
echo "🎆 Blatt project initialization complete!"
echo "============================================"
echo ""
echo "📖 Next steps:"
echo ""
echo "1️⃣  Configure Claude API Key (if not already configured):"
echo "   nano .env"
echo ""
echo "2️⃣  View project status and implementation plan:"
echo "   cat PROJECT_STATUS.md"
echo ""
echo "3️⃣  View detailed technical documentation:"
echo "   cat CLAUDE.md"
echo ""
echo "4️⃣  Start implementing core modules (refer to CLAUDE.md Phase 2):"
echo "   - Implement src/models/database.py"
echo "   - Implement src/models/paper.py"
echo "   - Implement src/api/semantic_scholar.py"
echo ""
echo "5️⃣  Run tests (after implementation):"
echo "   pytest tests/"
echo ""
echo "6️⃣  Start the application (after all modules are implemented):"
echo "   python app.py"
echo ""
echo "📚 For more help, see README.md"
echo ""
