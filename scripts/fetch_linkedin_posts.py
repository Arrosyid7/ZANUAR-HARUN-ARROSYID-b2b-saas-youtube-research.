"""
Fetch content from specific LinkedIn post URLs.

This does NOT scrape LinkedIn's feed/search — it only fetches individual
post URLs you've already collected (e.g. from creator profiles you visited
manually). LinkedIn often serves limited/og-meta content to unauthenticated
requests, so this script extracts what's available (title, description,
og:description) and falls back gracefully when blocked.

Requirements:
    pip install requests beautifulsoup4 --break-system-packages

Usage:
    1. Add post URLs to post_urls.txt (one per line), grouped by author
       using "# author-slug" comment lines as section headers.
    2. python fetch_linkedin_posts.py
"""

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
URL_LIST_FILE = SCRIPT_DIR / "post_urls.txt"
OUT_DIR = SCRIPT_DIR.parent / "research" / "linkedin-posts"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def slugify(text, max_len=60):
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text[:max_len]


def parse_url_list(path):
    """Returns dict: author_slug -> [urls]"""
    groups = {}
    current = "uncategorized"
    if not path.exists():
        return groups
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = slugify(line.lstrip("#").strip())
            groups.setdefault(current, [])
            continue
        groups.setdefault(current, []).append(line)
    return groups


def fetch_post(url):
    """Fetch a single LinkedIn post URL and extract available metadata."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    def meta(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag["content"].strip() if tag and tag.get("content") else None

    title = meta("og:title") or (soup.title.string.strip() if soup.title else None)
    description = meta("og:description")
    author = meta("og:site_name") or meta("article:author")

    return {
        "title": title,
        "description": description,
        "author": author,
        "raw_status": resp.status_code,
    }


def main():
    groups = parse_url_list(URL_LIST_FILE)
    if not groups:
        print(f"No URLs found. Add post URLs to {URL_LIST_FILE} first.")
        print("Format:\n# author-slug\nhttps://www.linkedin.com/posts/...\n")
        return

    for author_slug, urls in groups.items():
        author_dir = OUT_DIR / author_slug
        author_dir.mkdir(parents=True, exist_ok=True)

        for url in urls:
            print(f"Fetching: {url}")
            data = fetch_post(url)
            post_id = urlparse(url).path.strip("/").split("/")[-1] or "post"
            out_file = author_dir / f"{slugify(post_id)}.md"

            if "error" in data:
                content = (
                    f"# [Fetch failed]\n\n"
                    f"- URL: {url}\n"
                    f"- Error: {data['error']}\n\n"
                    f"## Notes\n\n"
                    f"LinkedIn blocked or limited this request. Open the URL "
                    f"manually and paste the post content below, or use "
                    f"`_template.md` as a starting point.\n\n"
                    f"## Content\n\n[Paste manually here]\n"
                )
            else:
                description = data.get("description") or (
                    "[No description extracted — LinkedIn may require login. "
                    "Paste post content manually below.]"
                )
                content = (
                    f"# {data.get('title') or '[Untitled]'}\n\n"
                    f"- URL: {url}\n"
                    f"- Author/site: {data.get('author') or 'unknown'}\n"
                    f"- HTTP status: {data.get('raw_status')}\n\n"
                    f"## Description (from page metadata)\n\n"
                    f"{description}\n\n"
                    f"## Content\n\n[Paste full post text here if needed]\n\n"
                    f"## Notes\n\n[Why relevant — hook style, topic angle, etc.]\n"
                )
            out_file.write_text(content, encoding="utf-8")
            print(f"  Saved: {out_file}")
            time.sleep(1)  # be polite


if __name__ == "__main__":
    main()
