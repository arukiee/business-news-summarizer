import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import os
import threading
import schedule
from textblob import TextBlob
from collections import Counter
import re

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

NEWS_SOURCES = [
    {"name": "BBC Business",       "rss": "http://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "Yahoo Finance",      "rss": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Reuters",            "rss": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "CNBC Business",      "rss": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"},
    {"name": "MarketWatch",        "rss": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "Forbes Business",    "rss": "https://www.forbes.com/business/feed/"},
    {"name": "Harvard Biz Review", "rss": "https://feeds.hbr.org/harvardbusiness"},
    {"name": "Inc Magazine",       "rss": "https://www.inc.com/rss"},
]

OUTPUT_FILE = "news_report.csv"

STOP_WORDS = {"the","a","an","is","in","on","at","to","for","of","and","or","but",
              "it","its","as","by","be","was","are","were","has","have","had","this",
              "that","with","from","will","not","been","after","about","said","says"}

# ─────────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────────

def get_article_links(rss_url, max_articles=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(rss_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:max_articles]
        links = []
        for item in items:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")
            if title and link:
                links.append({
                    "title": title.text.strip(),
                    "url": link.text.strip() if link.text else link.next_sibling.strip(),
                    "description": desc.text.strip() if desc else ""
                })
        return links
    except:
        return []

def extract_article_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text() for p in paragraphs if len(p.get_text()) > 40)
        return text[:3000] if text else None
    except:
        return None

def get_sentiment(text):
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity > 0.05:
            return "Positive", "🟢"
        elif polarity < -0.05:
            return "Negative", "🔴"
        else:
            return "Neutral", "🟡"
    except:
        return "Neutral", "🟡"

def summarize_with_groq(text, title):
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 300,
                "messages": [{
                    "role": "user",
                    "content": f"Summarize this business news in exactly 3 bullet points. Each should be one clear sentence.\nFormat:\n• point 1\n• point 2\n• point 3\n\nTitle: {title}\nText: {text}"
                }]
            },
            timeout=30
        )
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except:
        sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 40]
        return '\n'.join([f"• {s}." for s in sentences[:3]]) if sentences else "Summary unavailable."

def simple_summarize(text):
    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 40]
    return '\n'.join([f"• {s}." for s in sentences[:3]]) if sentences else "Summary unavailable."

def get_trending_keywords(df, top_n=15):
    all_words = []
    for title in df["title"].dropna():
        words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
        all_words.extend([w for w in words if w not in STOP_WORDS])
    return Counter(all_words).most_common(top_n)

def run_pipeline(selected_sources, max_articles, use_ai, progress_bar=None, status_text=None):
    all_articles = []
    total = max(len(selected_sources) * max_articles, 1)
    done = 0

    for source in NEWS_SOURCES:
        if source["name"] not in selected_sources:
            continue
        links = get_article_links(source["rss"], max_articles)
        for item in links:
            if status_text:
                status_text.text(f"Processing: {item['title'][:60]}...")
            text = extract_article_text(item["url"])
            if not text or len(text) < 100:
                text = item.get("description", "")
            if not text or len(text) < 30:
                done += 1
                if progress_bar:
                    progress_bar.progress(min(done / total, 1.0))
                continue

            summary = summarize_with_groq(text, item["title"]) if use_ai else simple_summarize(text)
            sentiment, sentiment_icon = get_sentiment(text)

            all_articles.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": source["name"],
                "title": item["title"],
                "url": item["url"],
                "summary": summary,
                "sentiment": sentiment,
                "sentiment_icon": sentiment_icon,
            })
            done += 1
            if progress_bar:
                progress_bar.progress(min(done / total, 1.0))
            time.sleep(0.5)

    if all_articles:
        df = pd.DataFrame(all_articles)
        if os.path.exists(OUTPUT_FILE):
            existing = pd.read_csv(OUTPUT_FILE)
            df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["title"])
        df.to_csv(OUTPUT_FILE, index=False)

    return all_articles

# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

def scheduled_fetch():
    run_pipeline(["BBC Business", "Yahoo Finance", "CNBC Business"], max_articles=5, use_ai=True)

def run_scheduler(fetch_time):
    schedule.clear()
    schedule.every().day.at(fetch_time).do(scheduled_fetch)
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────

st.set_page_config(page_title="Business News Summarizer", page_icon="📰", layout="wide")

st.title("📰 Business News Summarizer")
st.markdown("*AI-powered news scraper with sentiment analysis, trend charts & auto-scheduling*")
st.divider()

with st.sidebar:
    st.header("⚙️ Settings")
    selected_sources = st.multiselect("News Sources", ["BBC Business", "Yahoo Finance", "Reuters", "CNBC Business", "MarketWatch", "Forbes Business", "Harvard Biz Review", "Inc Magazine"], default=["BBC Business", "Yahoo Finance"])
    max_articles = st.slider("Articles per source", 1, 10, 5)
    use_ai = st.toggle("Use AI Summarization", value=True)
    st.divider()
    st.subheader("⏰ Auto-Scheduler")
    scheduler_on = st.toggle("Enable daily auto-fetch", value=False)
    fetch_time = st.time_input("Fetch time", value=datetime.strptime("08:00", "%H:%M").time())
    if scheduler_on:
        fetch_time_str = fetch_time.strftime("%H:%M")
        if "scheduler_thread" not in st.session_state or not st.session_state["scheduler_thread"].is_alive():
            t = threading.Thread(target=run_scheduler, args=(fetch_time_str,), daemon=True)
            t.start()
            st.session_state["scheduler_thread"] = t
        st.success(f"Auto-fetch ON at {fetch_time_str} daily")
    else:
        schedule.clear()
        st.caption("Auto-fetch is off")
    st.divider()
    st.caption("Built by K Arukshithaaw")
    st.caption("Python • Streamlit • Groq AI")

tab1, tab2, tab3, tab4 = st.tabs(["📰 Today's News", "📊 Analytics", "🗄️ Database", "🗑️ Manage"])

# ── TAB 1 ──
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        fetch_btn = st.button("🔍 Fetch & Summarize", type="primary", use_container_width=True)
    with col2:
        if os.path.exists(OUTPUT_FILE):
            df_existing = pd.read_csv(OUTPUT_FILE)
            st.caption(f"📊 {len(df_existing)} total articles in database")
    st.divider()

    if fetch_btn:
        if not selected_sources:
            st.error("Select at least one source.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            with st.spinner("Fetching and summarizing..."):
                articles = run_pipeline(selected_sources, max_articles, use_ai, progress_bar, status_text)
            status_text.empty()
            progress_bar.empty()
            if articles:
                st.success(f"✅ Fetched {len(articles)} articles!")
                st.session_state["articles"] = articles
            else:
                st.warning("No articles found.")

    articles_to_show = st.session_state.get("articles", [])
    if not articles_to_show and os.path.exists(OUTPUT_FILE):
        df_load = pd.read_csv(OUTPUT_FILE)
        today = datetime.now().strftime("%Y-%m-%d")
        today_df = df_load[df_load["date"] == today]
        if not today_df.empty:
            articles_to_show = today_df.to_dict("records")

    if articles_to_show:
        sentiments = [a.get("sentiment", "Neutral") for a in articles_to_show]
        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 Positive", sentiments.count("Positive"))
        c2.metric("🔴 Negative", sentiments.count("Negative"))
        c3.metric("🟡 Neutral",  sentiments.count("Neutral"))
        st.divider()

        for source in list(dict.fromkeys(a["source"] for a in articles_to_show)):
            st.subheader(f"📡 {source}")
            for article in [a for a in articles_to_show if a["source"] == source]:
                icon = article.get("sentiment_icon", "🟡")
                with st.expander(f"{icon} {article['title']}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        summary = article.get("summary", "Summary unavailable.")
                        bullets = [l.strip() for l in summary.split("\n") if l.strip().startswith("•")]
                        for bullet in (bullets or [summary]):
                            st.markdown(bullet)
                    with col_b:
                        sentiment = article.get("sentiment", "Neutral")
                        st.markdown(f"**Sentiment:**\n\n{icon} {sentiment}")
                    st.markdown(f"[Read full article →]({article['url']})")
            st.divider()

        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "rb") as f:
                st.download_button("⬇️ Download CSV", f, file_name="news_report.csv", mime="text/csv")
    else:
        st.info("Click **Fetch & Summarize** to get started!")

# ── TAB 2: ANALYTICS ──
with tab2:
    if not os.path.exists(OUTPUT_FILE):
        st.info("No data yet. Fetch some news first!")
    else:
        df_chart = pd.read_csv(OUTPUT_FILE)
        st.subheader("📊 Analytics Dashboard")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Articles", len(df_chart))
        m2.metric("Sources", df_chart["source"].nunique())
        m3.metric("Days Tracked", df_chart["date"].nunique())
        if "sentiment" in df_chart.columns:
            pos_pct = round(len(df_chart[df_chart["sentiment"] == "Positive"]) / len(df_chart) * 100)
            m4.metric("Positive News %", f"{pos_pct}%")

        st.divider()
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Articles by Source**")
            source_counts = df_chart["source"].value_counts().reset_index()
            source_counts.columns = ["Source", "Count"]
            st.bar_chart(source_counts.set_index("Source"))
        with col_right:
            st.markdown("**Articles per Day**")
            daily_counts = df_chart.groupby("date").size().reset_index(name="Count")
            st.bar_chart(daily_counts.set_index("date"))

        st.divider()
        if "sentiment" in df_chart.columns:
            st.markdown("**Sentiment Breakdown**")
            sentiment_counts = df_chart["sentiment"].value_counts().reset_index()
            sentiment_counts.columns = ["Sentiment", "Count"]
            st.bar_chart(sentiment_counts.set_index("Sentiment"))
            st.divider()

        st.markdown("**🔥 Trending Keywords**")
        keywords = get_trending_keywords(df_chart)
        if keywords:
            kw_df = pd.DataFrame(keywords, columns=["Keyword", "Count"])
            st.bar_chart(kw_df.set_index("Keyword"))

# ── TAB 3: DATABASE ──
with tab3:
    if not os.path.exists(OUTPUT_FILE):
        st.info("No data yet. Fetch some news first!")
    else:
        df_db = pd.read_csv(OUTPUT_FILE)
        st.markdown(f"**{len(df_db)} total articles saved**")
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            selected_date = st.selectbox("Filter by date", ["All dates"] + sorted(df_db["date"].unique(), reverse=True))
        with col2:
            selected_source = st.selectbox("Filter by source", ["All sources"] + sorted(df_db["source"].unique()))
        with col3:
            search_query = st.text_input("Search keyword", placeholder="e.g. oil, stocks...")

        sentiment_filter = "All"
        if "sentiment" in df_db.columns:
            sentiment_filter = st.selectbox("Filter by sentiment", ["All", "Positive", "Negative", "Neutral"])

        filtered_df = df_db.copy()
        if selected_date != "All dates":
            filtered_df = filtered_df[filtered_df["date"] == selected_date]
        if selected_source != "All sources":
            filtered_df = filtered_df[filtered_df["source"] == selected_source]
        if search_query:
            filtered_df = filtered_df[
                filtered_df["title"].str.contains(search_query, case=False, na=False) |
                filtered_df["summary"].str.contains(search_query, case=False, na=False)
            ]
        if sentiment_filter != "All" and "sentiment" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["sentiment"] == sentiment_filter]

        st.caption(f"Showing {len(filtered_df)} articles")
        st.divider()

        if filtered_df.empty:
            st.warning("No articles match your filters.")
        else:
            for _, row in filtered_df.iterrows():
                icon = row.get("sentiment_icon", "🔹")
                with st.expander(f"{icon} [{row['source']}] {row['title']} — {row['date']}"):
                    summary = row.get("summary", "Summary unavailable.")
                    bullets = [l.strip() for l in str(summary).split("\n") if l.strip().startswith("•")]
                    for bullet in (bullets or [summary]):
                        st.markdown(bullet)
                    if "sentiment" in row:
                        st.caption(f"Sentiment: {row.get('sentiment_icon','')} {row['sentiment']}")
                    st.markdown(f"[Read full article →]({row['url']})")

        st.divider()
        with open(OUTPUT_FILE, "rb") as f:
            st.download_button("⬇️ Download Full Database", f, file_name="news_report.csv", mime="text/csv")

# ── TAB 4: MANAGE ──
with tab4:
    st.subheader("🗑️ Manage Database")
    if not os.path.exists(OUTPUT_FILE):
        st.info("No database found yet.")
    else:
        df_manage = pd.read_csv(OUTPUT_FILE)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Articles", len(df_manage))
        m2.metric("Sources", df_manage["source"].nunique())
        m3.metric("Days of Data", df_manage["date"].nunique())
        st.divider()

        st.markdown("**Clear articles by date:**")
        dates_to_clear = st.multiselect("Select dates to delete", sorted(df_manage["date"].unique(), reverse=True))
        if st.button("🗑️ Delete Selected Dates", type="secondary"):
            if dates_to_clear:
                df_manage = df_manage[~df_manage["date"].isin(dates_to_clear)]
                df_manage.to_csv(OUTPUT_FILE, index=False)
                st.success(f"Deleted: {', '.join(dates_to_clear)}")
                st.rerun()
            else:
                st.warning("Select at least one date.")

        st.divider()
        st.markdown("**Clear entire database:**")
        st.warning("⚠️ This will permanently delete ALL saved articles.")
        confirm = st.checkbox("I understand, delete everything")
        if st.button("🔴 Clear All Articles", type="primary", disabled=not confirm):
            os.remove(OUTPUT_FILE)
            st.session_state.pop("articles", None)
            st.success("Database cleared!")
            st.rerun()
