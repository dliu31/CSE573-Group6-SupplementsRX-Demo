import asyncio, json
from pathlib import Path
from typing import List, Dict
from urllib.parse import quote_plus

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

FIELDS = [
    "supplement_name","category","uses","dosage_range","contraindications",
    "interactions","evidence_rating","clinical_refs","source","url"
]

def _writer(path: Path):
    f = open(path, "w", encoding="utf-8")
    def write_row(row: Dict):
        f.write(json.dumps({k: row.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
    return f, write_row

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return await resp.text()

def _parse_article(html: str, url: str, q: str) -> Dict:
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("h1")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("article p")]
    uses = " ".join(paragraphs[:5])[:2000] if paragraphs else None
    return {"supplement_name": q, "uses": uses, "source": "mayo", "url": url}

async def run(queries: List[str], outdir: str, concurrency: int = 50, limit: int = 1000000):
    outpath = Path(outdir) / "mayo.jsonl"
    f, write_row = _writer(outpath)
    sem = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(headers={"User-Agent":"SupplementScraper/1.0"}) as session:
        async def fetch_detail(url, q):
            async with sem:
                html = await _fetch(session, url)
            write_row(_parse_article(html, url, q))

        async def fetch_query(q):
            search_url = f"https://www.mayoclinic.org/search/search-results?q={quote_plus(q)}"
            async with sem:
                html = await _fetch(session, search_url)
            soup = BeautifulSoup(html, "lxml")
            links = []
            for a in soup.select("a"):
                href = a.get("href","")
                if href.startswith("https://www.mayoclinic.org") and "/drugs-supplements" in href:
                    links.append(href)
            links = list(dict.fromkeys(links))[:1000]
            await asyncio.gather(*(fetch_detail(u, q) for u in links))

        await asyncio.gather(*(fetch_query(q) for q in queries))

    f.close()
    return {"source":"mayo","file":str(outpath),"records":"streamed"}