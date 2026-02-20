#!/usr/bin/env python3
"""Generate an Atom feed of Paged Out! articles from web viewer pages."""

import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


IS_CI = os.environ.get("CI", "").lower() == "true"

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator  # type: ignore[import-untyped]

PAGEDOUT_URL = "https://pagedout.institute"
ATOM_URL = f"{PAGEDOUT_URL}/atom.xml"
WEBVIEW_URL = f"{PAGEDOUT_URL}/webview.php"
SITE_URL = "https://abhin4v.github.io/paged-out-feed"
CACHE_DIR = Path("cache")
STATE_FILE = CACHE_DIR / "state.json"
SITE_DIR = Path("_site")
OUTPUT_FILE = SITE_DIR / "feed.atom"
INDEX_FILE = SITE_DIR / "index.html"


@dataclass
class Article:
    title: str
    url: str
    issue: int
    published: datetime | None = None


@dataclass
class Issue:
    number: int
    title: str
    updated: str


State = dict[str, Any]


def load_state() -> State:
    if not IS_CI and STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"issues": {}}


def save_state(state: State) -> None:
    if not IS_CI:
        CACHE_DIR.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_main_feed() -> list[Issue]:
    """Fetch the main Atom feed and extract issue info."""
    resp = requests.get(ATOM_URL, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    issues: list[Issue] = []
    for entry in root.findall("atom:entry", ns):
        title_elem = entry.find("atom:title", ns)
        updated_elem = entry.find("atom:updated", ns)

        if title_elem is None or title_elem.text is None:
            continue
        if updated_elem is None or updated_elem.text is None:
            continue

        title = title_elem.text
        updated = updated_elem.text

        match = re.search(r"#(\d+)", title)
        if match:
            issue_num = int(match.group(1))
            issues.append(Issue(number=issue_num, title=title, updated=updated))

    return issues


def download_webview(issue_num: int) -> str | None:
    """Download webview HTML for an issue. Returns None if webview doesn't exist."""
    url = f"{WEBVIEW_URL}?issue={issue_num}&page=1"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        if "webview-toc-list" not in resp.text:
            return None
        return resp.text
    except requests.RequestException:
        return None


def parse_articles(html: str, issue_num: int) -> list[Article]:
    """Parse articles from webview HTML."""
    soup = BeautifulSoup(html, "html.parser")
    toc = soup.find("ul", class_="webview-toc-list")
    if not toc:
        raise ValueError(f"TOC not found for issue {issue_num}")

    articles: list[Article] = []
    for item in toc.find_all("li", class_="webview-toc-item"):
        link = item.find("a", class_="webview-toc-link")
        if not link:
            continue

        href = str(link.get("href", ""))
        if f"issue={issue_num}" not in href or "article=" not in href:
            continue

        article_match = re.search(r"article=([^&]+)", href)
        if not article_match:
            continue

        article_title = link.get_text(strip=True)
        page_match = re.search(r"page=(\d+)", href)
        page_num = page_match.group(1) if page_match else "1"

        full_url = f"{PAGEDOUT_URL}/webview.php?issue={issue_num}&page={page_num}&article={article_match.group(1)}"

        articles.append(
            Article(
                title=article_title,
                url=full_url,
                issue=issue_num,
            )
        )

    if not articles:
      raise ValueError(f"No articles found for issue {issue_num}")

    return articles


def generate_feed(all_articles: list[Article]) -> None:
    """Generate Atom feed from all articles."""
    fg = FeedGenerator()
    fg.id(SITE_URL)
    fg.title("Paged Out! Articles")
    fg.subtitle("Individual articles from Paged Out! magazine")
    fg.link(href=PAGEDOUT_URL, rel="alternate")
    fg.link(href=f"{SITE_URL}/feed.atom", rel="self")
    fg.language("en")

    if all_articles:
        latest_date = max(a.published for a in all_articles if a.published)
        fg.updated(latest_date)

    def sort_key(a: Article) -> tuple[int, int]:
        issue = -a.issue
        match = re.match(r"(\d+)\.", a.title)
        article_num = int(match.group(1)) if match else 0
        return (issue, article_num)

    sorted_articles = sorted(all_articles, key=sort_key)
    for article in sorted_articles:
        fe = fg.add_entry(order="append")
        fe.id(article.url)
        title = re.sub(r"^\d+\.\s*", "", article.title)
        fe.title(f"[Issue #{article.issue}] {title}")
        fe.link(href=article.url, rel="alternate")
        fe.published(article.published)
        fe.updated(article.published)
        fe.summary(f"Article from Paged Out! Issue #{article.issue}")

    fg.atom_file(str(OUTPUT_FILE), pretty=True)


def generate_index(article_count: int, issue_count: int) -> None:
    """Generate index.html page."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Paged Out! Articles Feed</title>
    <link rel="alternate" type="application/atom+xml" title="Paged Out! Articles Feed" href="feed.atom">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            color: #1a1a2e;
            background: #f8f9fa;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .container {{
            max-width: 600px;
            background: white;
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: rgb(133, 16, 220);
            margin-bottom: 1.5rem;
            font-size: 1.75rem;
        }}
        p {{ margin-bottom: 1rem; color: #444; }}
        .feed-link {{
            display: inline-block;
            background: rgb(133, 16, 220);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 500;
            margin: 1rem 0;
        }}
        .feed-link:hover {{ background: #4a2590; }}
        .stats {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid #eee;
        }}
        a {{ color: #351c68; }}
        footer {{ padding: 1rem; }}
    </style>
</head>
<body>
    <main class="container">
        <h1>Paged Out! Articles Feed</h1>
        <p>
            Automatically generated Atom feed with entries for each individual article 
            from <a href="{PAGEDOUT_URL}">Paged Out!</a> magazine.
        </p>
        <p>
            <a href="feed.atom" class="feed-link">Subscribe to the Feed</a>
        </p>
        <p>
            Paged Out! is a free experimental technical magazine about programming, hacking, 
            security, retrocomputing, electronics, demoscene, and other similar topics.
        </p>
        <p>        
            This feed generator extracts individual articles from issues that have a web viewer available.
        </p>
        <div class="stats">
            Currently tracking <strong>{article_count}</strong> articles 
            from <strong>{issue_count}</strong> issue(s).
        </div>
    </main>
    <footer>
        Made by <a href="https://abhinavsarkar.net">Abhinav</a>.
    </footer>
</body>
</html>"""
    INDEX_FILE.write_text(html)


def main() -> None:
    SITE_DIR.mkdir(exist_ok=True)
    state = load_state()

    print("Fetching main feed...")
    issues = fetch_main_feed()
    print(f"Found {len(issues)} issues in main feed")

    all_articles: list[Article] = []
    issues_with_articles: set[int] = set()

    for issue in issues:
        issue_num = issue.number
        issue_key = str(issue_num)
        published = datetime.fromisoformat(issue.updated.replace("Z", "+00:00"))

        if issue_key in state["issues"]:
            print(f"Issue #{issue_num}: Using cached articles")
            for article_data in state["issues"][issue_key]["articles"]:
                article = Article(
                    title=article_data["title"],
                    url=article_data["url"],
                    issue=article_data["issue"],
                    published=published,
                )
                all_articles.append(article)
            issues_with_articles.add(issue_num)
            continue

        print(f"Issue #{issue_num}: Downloading webview...")
        html = download_webview(issue_num)
        if html is None:
            print(f"Issue #{issue_num}: No webview available, skipping")
            continue

        articles = parse_articles(html, issue_num)
        print(f"Issue #{issue_num}: Found {len(articles)} articles")

        state["issues"][issue_key] = {
            "articles": [
                {
                    "title": a.title,
                    "url": a.url,
                    "issue": a.issue,
                }
                for a in articles
            ]
        }
        save_state(state)

        for article in articles:
            article.published = published
            all_articles.append(article)
        issues_with_articles.add(issue_num)

    print(f"\nTotal articles: {len(all_articles)}")
    generate_feed(all_articles)
    print(f"Feed written to {OUTPUT_FILE}")

    generate_index(len(all_articles), len(issues_with_articles))
    print(f"Index written to {INDEX_FILE}")


if __name__ == "__main__":
    main()
