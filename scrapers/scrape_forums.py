# scrape_forums.py
import os, re, json, time, argparse, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Dict, Any, List, Tuple

import requests
from bs4 import BeautifulSoup as BS
from tenacity import retry, wait_fixed, stop_after_attempt
from dateutil import parser as dtparse

# Load .env 
from dotenv import load_dotenv
DOTENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)


try:
    import praw
except Exception:
    praw = None


# Utils
def utc_iso(ts) -> str:
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(ts, str):
        try:
            return dtparse.parse(ts).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return ts
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return ""

def clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()

def make_id(*parts) -> str:
    h = hashlib.md5(("|".join([str(p) for p in parts])).encode("utf-8")).hexdigest()
    return h

def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def keyword_hit(text: str, kws: List[str]) -> List[str]:
    t = text.lower()
    return [k for k in kws if k.lower() in t]


# Reddit
def reddit_client(args=None):
    if praw is None:
        raise RuntimeError("praw not installed. Run: pip install praw")

    cid  = (getattr(args, "reddit_client_id", None)     or os.getenv("REDDIT_CLIENT_ID"))
    csec = (getattr(args, "reddit_client_secret", None) or os.getenv("REDDIT_CLIENT_SECRET"))
    ua   = (getattr(args, "reddit_user_agent", None)    or os.getenv("REDDIT_USER_AGENT"))

    if not cid or not csec or not ua:
        raise RuntimeError(
            f"Missing Reddit creds. CID={bool(cid)} SECRET={bool(csec)} UA={bool(ua)}. "
            f"Check .env at {DOTENV_PATH.resolve()} or pass --reddit-client-id/--reddit-client-secret/--reddit-user-agent"
        )
    r = praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua, check_for_async=False)
    return r

def scrape_reddit(subs: List[str], limit_per_sub: int, keywords: List[str], args=None) -> Iterable[Dict[str, Any]]:
    r = reddit_client(args)
    # optional sanity print (normal for script apps to show None)
    try:
        print("user.me():", r.user.me())
    except Exception:
        pass

    for sub in subs:
        subr = r.subreddit(sub)
        # split limit between hot/new for diversity
        lim_hot = max(1, (limit_per_sub // 2) or 50)
        lim_new = max(1, limit_per_sub - lim_hot)

        streams = [
            ("hot", subr.hot(limit=lim_hot)),
            ("new", subr.new(limit=lim_new)),
        ]
        for label, stream in streams:
            for post in stream:
                title = clean_text(post.title)
                body  = clean_text(post.selftext or "")
                hits  = keyword_hit(f"{title}\n{body}", keywords) if keywords else []
                yield {
                    "source": "reddit",
                    "forum": f"r/{sub}",
                    "thread_id": post.id,
                    "post_id": post.id,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "title": title,
                    "author": f"u/{post.author.name}" if post.author else None,
                    "created_utc": utc_iso(post.created_utc),
                    "body": body,
                    "score": int(post.score or 0),
                    "reply_to": None,
                    "keywords_matched": hits
                }

                # comments
                try:
                    post.comments.replace_more(limit=0)
                    for c in post.comments.list():
                        cbody = clean_text(getattr(c, "body", "") or "")
                        chits = keyword_hit(cbody, keywords) if keywords else []
                        yield {
                            "source": "reddit",
                            "forum": f"r/{sub}",
                            "thread_id": post.id,
                            "post_id": make_id(post.id, c.id),
                            "url": f"https://www.reddit.com{post.permalink}{c.id}/",
                            "title": None,
                            "author": f"u/{c.author.name}" if c.author else None,
                            "created_utc": utc_iso(getattr(c, "created_utc", None)),
                            "body": cbody,
                            "score": int(getattr(c, "score", 0) or 0),
                            "reply_to": post.id,
                            "keywords_matched": chits
                        }
                except Exception:
                    # keep going if a comment fetch glitches
                    continue


# Discourse
# Many forums run Discourse and expose JSON:
#   search:  https://forums.example.com/search.json?q=magnesium
#   topic:   https://forums.example.com/t/<slug>/<id>.json

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def _get_json(url, params=None, headers=None):
    headers = headers or {"User-Agent": "supplementsrx-scraper/0.1"}
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()

def discourse_search(base_url: str, query: str, pages: int = 3) -> List[Tuple[str, int]]:
    out = []
    for p in range(1, pages + 1):
        data = _get_json(f"{base_url}/search.json", params={"q": query, "page": p})
        for t in data.get("topics", []):
            out.append((t.get("slug"), t.get("id")))
        time.sleep(1.0)
    # dedupe by topic id
    seen, uniq = set(), []
    for slug, tid in out:
        if tid not in seen:
            uniq.append((slug, tid)); seen.add(tid)
    return uniq

def discourse_topic(base_url: str, slug: str, tid: int) -> Dict[str, Any]:
    return _get_json(f"{base_url}/t/{slug}/{tid}.json")

def scrape_discourse(base_url: str, forum_label: str, query: str, max_topics: int, keywords: List[str]) -> Iterable[Dict[str, Any]]:
    topics = discourse_search(base_url, query, pages=5)
    if max_topics:
        topics = topics[:max_topics]
    for slug, tid in topics:
        try:
            tjson = discourse_topic(base_url, slug, tid)
        except Exception:
            continue
        title = clean_text(tjson.get("title", ""))

        for p in tjson.get("post_stream", {}).get("posts", []):
            body_raw = p.get("cooked", "")
            body_txt = clean_text(BS(body_raw, "html.parser").get_text(" "))
            hits = keyword_hit(f"{title}\n{body_txt}", keywords) if keywords else []
            url = f"{base_url}/t/{slug}/{tid}/{p.get('post_number')}"
            yield {
                "source": "discourse",
                "forum": forum_label,
                "thread_id": str(tid),
                "post_id": make_id(tid, p.get("id")),
                "url": url,
                "title": title if p.get("post_number") == 1 else None,
                "author": p.get("username"),
                "created_utc": utc_iso(p.get("created_at")),
                "body": body_txt,
                "score": int(p.get("like_count", 0)),
                "reply_to": None if p.get("post_number") == 1 else make_id(tid, 1),
                "keywords_matched": hits
            }
        time.sleep(1.0)

# Known Discourse site(s) you asked for:
DISCOURSE_SITES = {
    "t-nation": "https://forums.t-nation.com",
    # add more Discourse forums here
}


# CLI
def parse_args():
    ap = argparse.ArgumentParser(description="Scrape discussions for SupplementsRx AI")
    # sources
    ap.add_argument("--reddit", action="store_true", help="include Reddit (r/Supplements, r/Nutrition by default)")
    ap.add_argument("--discourse", action="store_true", help="include Discourse forums (e.g., T-Nation)")

    # reddit options
    ap.add_argument("--subreddits", nargs="*", default=["Supplements", "Nutrition"], help="subreddit names (without r/)")
    ap.add_argument("--reddit-limit", type=int, default=300, help="posts per subreddit (comments fetched separately)")
    ap.add_argument("--reddit-client-id")
    ap.add_argument("--reddit-client-secret")
    ap.add_argument("--reddit-user-agent")

    # discourse options
    ap.add_argument("--topics-per-forum", type=int, default=120, help="max topics per Discourse forum")
    ap.add_argument("--query", default="vitamin OR supplement OR creatine OR magnesium OR melatonin",
                    help="search query for Discourse forums")

    # filtering
    ap.add_argument("-k", "--keywords", nargs="*", default=[], help="optional keywords to tag matches")

    return ap.parse_args()


# Main
def main():
    args = parse_args()
    outdir = Path("data"); outdir.mkdir(exist_ok=True)

    if args.reddit:
        print("▶ Scraping Reddit…")
        rows = list(scrape_reddit(args.subreddits, args.reddit_limit, args.keywords, args))
        out = outdir / "reddit.jsonl"
        write_jsonl(out, rows)
        print(f"Reddit: wrote {len(rows)} rows → {out}")

    if args.discourse:
        print("▶ Scraping Discourse forums…")
        total = 0
        for label, base in DISCOURSE_SITES.items():
            rows = list(scrape_discourse(base, label, args.query, args.topics_per_forum, args.keywords))
            out = outdir / f"{label}.jsonl"
            write_jsonl(out, rows)
            print(f"{label}: wrote {len(rows)} rows → {out}")
            total += len(rows)
        if total == 0:
            print("No Discourse rows collected (try a broader --query).")

    if not args.reddit and not args.discourse:
        # convenience: quick connectivity test
        if praw is None:
            print("Install praw to test Reddit connectivity: pip install praw")
        else:
            try:
                r = reddit_client(args)
                print("user.me():", r.user.me())
                sub = r.subreddit("Supplements")
                for i, post in enumerate(sub.hot(limit=5), start=1):
                    print(f"{i}. {post.title}  ({post.score} upvotes)")
            except Exception as e:
                print("Reddit test failed:", e)

    print("🎉 Done.")

if __name__ == "__main__":
    main()
