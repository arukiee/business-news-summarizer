# Business News Summarizer
An automated pipeline that scrapes daily business news from top Indian financial sources and generates AI-powered summaries using Claude AI.

## Features
- Scrapes news from Economic Times, Moneycontrol, Business Standard
- Extracts clean article text automatically
- Summarizes each article into 3 bullet points using Claude AI
- Saves all articles to a structured CSV database
- Prints a clean daily report in the terminal
- Works without API key using built-in simple summarizer

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the summarizer
```bash
python news_summarizer.py
```

### 3. Choose a mode
```
1 — Scrape + summarize with Claude AI (recommended)
2 — Scrape + simple summarizer (no API needed)
3 — Print today's saved report
```

## Output
- `news_report.csv` — structured database of all scraped articles with summaries

## Tech Stack
- Python
- BeautifulSoup4 — web scraping
- newspaper3k — article text extraction
- Claude AI (Anthropic API) — text summarization
- pandas — data storage and analysis

## Project Structure
```
business_news_summarizer/
├── news_summarizer.py   # Main pipeline
├── requirements.txt     # Dependencies
└── news_report.csv      # Generated output (created on first run)
```
