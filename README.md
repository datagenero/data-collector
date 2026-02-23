# Data Collector

A web scraper application for collecting and managing documents from various sources.

## Setup

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

1. Install dependencies and create virtual environment:
```bash
uv sync
```

2. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env to customize DATABASE_PATH
```

3. Initialize the database:
```bash
python scripts/init_db.py
# Or with custom path:
python scripts/init_db.py --db-path /path/to/database.db
```

### Run the app

If you prefer using pip:
```bash
python main.py
```
The application will be available at `http://localhost:8000`
