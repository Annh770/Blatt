# Blatt (Leaf) - AI-Powered Academic Paper Search Assistant

An all-in-one AI platform for literature search and the visualization of functional relationships between papers.
Collect literature like collecting leaves 🍃

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


## ✨ Core Features

- 🔍 **Smart Retrieval**: Automatically retrieve relevant papers from Semantic Scholar, arXiv and other academic databases
- 🌐 **Citation Network Extension**: Automatically track citation relationships and build complete paper networks
- 🤖 **AI Analysis Scoring**: Use Claude AI to analyze paper relevance and automatically score (Priority 1-5)
- 📊 **Relationship Analysis**: AI identifies relationship types between papers (improvements, builds on, comparisons, etc.)
- 🎨 **Interactive Visualization**: Generate interactive paper relationship networks to intuitively display research context
- 📥 **Multi-format Export**: Support exporting to Excel, BibTeX and other formats
- 🔄 **Multi-round Extension**: Support deep exploration of papers of interest

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Claude API Key 

### Installation Steps

1. **Enter project directory**


2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env file and fill in your Claude API Key
nano .env  # or use other editor
```

5. **Initialize database**
```bash
python -c "from src.models.database import Database; Database('data/blatt.db')"
```

6. **Run application**
```bash
python app.py
```

7. **Access application**

Open browser and visit

## 📖 Usage Guide

### Basic Workflow

1. **Enter research topic**
   - Input research topic in "Keywords" field, e.g. "autonomous driving simulation"
   - Add more context information in "Description" field (optional)

2. **Wait for analysis**
   - System automatically retrieves papers
   - Extends citation network
   - AI analyzes and scores papers
   - Generates interactive visualization

3. **View results**
   - Browse filtered list of relevant papers
   - View interactive paper relationship graph
   - Download Excel or BibTeX format files

4. **Deep exploration (optional)**
   - Select papers of interest
   - Perform second-round expansion search
   - Discover more relevant literature

### Priority Scoring Explanation

- **Priority 5**: Highly relevant, directly solves core problem
- **Priority 4**: Relevant, method variants or extensions
- **Priority 3**: Partially relevant, can serve as background reference
- **Priority 2**: Weakly relevant, only conceptually related
- **Priority 1**: Basically irrelevant

By default, only papers with Priority ≥ 4 are exported.

## 🏗️ Project Structure

```
Blatt/
├── app.py                  # Flask application entry point
├── config.py               # Configuration management
├── requirements.txt        # Dependency list
├── README.md              # User documentation (this file)
│
├── src/                   # Source code
│   ├── api/               # API client wrappers
│   ├── core/              # Core business logic
│   ├── models/            # Data models
│   └── utils/             # Utility functions
│
├── templates/             # HTML templates
├── static/                # Static resources

```

## 📊 Example Screenshots

(TODO: Add actual usage screenshots)


## 🔧 Troubleshooting

### Common Issues

1. **API call failures**
   - Check if `CLAUDE_API_KEY` in `.env` file is correct
   - Confirm your API account has sufficient balance

2. **Papers not found**
   - Try using more generic keywords
   - Check network connectivity
   - View log file 

3. **Database errors**
   - Delete `data/blatt.db` to reinitialize
   - Check permissions for `data/` directory

### Viewing Logs

```bash
tail -f logs/blatt.log
```

## 🛣️ Development Roadmap

- [x] Core search and analysis functionality
- [x] Excel/BibTeX export
- [x] Visualization graph generation
- [x] Multi-round expansion
- [ ] User account system
- [ ] PDF full-text download
- [ ] Support for more data sources (IEEE, PubMed, etc.)
- [ ] Advanced graph editing features

## 🤝 Contributing Guidelines

Contributions to code, bug reports, and suggestions are welcome!

1. Fork this project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


## 📧 Contact

TODO

