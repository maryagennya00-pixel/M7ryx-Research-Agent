# research_agent/tools.py
import warnings
warnings.filterwarnings("ignore")

from langchain_community.tools.tavily_search import TavilySearchResults
from config import DEPTH_CONFIGS, MIN_RELEVANCE_SCORE
from utils import llm_fast, safe_invoke
import re, hashlib, time


def generate_queries(topic: str, depth: str = "Standard",
                     progress_callback=None) -> list:
    """Stage 1: Generate multiple search queries - fast model is fine here"""
    n = DEPTH_CONFIGS[depth]["queries"]
    prompt = f"""Generate {n} different search queries for: "{topic}"
Cover different angles: overview, statistics, challenges, recent news, expert views.
One query per line. 4-8 words each. No numbering."""
    text = safe_invoke(llm_fast, prompt, progress_callback=progress_callback)
    lines = text.strip().split("\n")
    return [l.strip() for l in lines if l.strip()][:n]


def collect_results(queries: list, results_per_query: int = 5) -> list:
    """Stage 2: Search the web"""
    all_results = []
    search = TavilySearchResults(max_results=results_per_query)
    for query in queries:
        try:
            results = search.invoke(query)
            for r in results:
                if isinstance(r, dict) and r.get("content"):
                    all_results.append({
                "query": query,
                "url":     r.get("url", ""),
                "title":   r.get("title", ""),
                "content": r.get("content", ""),
            })
            time.sleep(0.3)
        except Exception:
            continue
    return all_results


def deduplicate(results: list) -> list:
    """Stage 3: Remove duplicates"""
    seen = {}
    for r in results:
        key = hashlib.md5(r["content"][:200].lower().encode()).hexdigest()
        if key not in seen:
            seen[key] = r
    return list(seen.values())


def chunk_text(results: list, max_words: int = 400) -> list:
    """Stage 3b: Split long results into chunks"""
    chunks = []
    for r in results:
        words = r["content"].split()
        if len(words) <= max_words:
            chunks.append(r)
        else:
            for start in range(0, len(words), max_words - 30):
                chunk = dict(r)
                chunk["content"] = " ".join(words[start:start + max_words])
                chunks.append(chunk)
    return chunks


def filter_relevant(chunks: list, topic: str,
                    threshold: float = MIN_RELEVANCE_SCORE,
                    max_chunks: int = 20,
                    progress_callback=None) -> list:
    """Stage 4: Score and filter by relevance - fast model, batched"""
    scored = []
    batch_size = 8
    for i in range(0, min(len(chunks), max_chunks * 2), batch_size):
        batch = chunks[i:i + batch_size]
        excerpts = "\n\n---\n\n".join([
            f"[{j}] {c['content'][:250]}" for j, c in enumerate(batch)
        ])
        prompt = f"""Rate each excerpt's relevance to: "{topic}"
Excerpts:
{excerpts}
Format: 0: 0.8, 1: 0.3, 2: 0.9 (one line, comma-separated)"""
        try:
            resp = safe_invoke(llm_fast, prompt, progress_callback=progress_callback)
            pairs = re.findall(r'(\d+):\s*([\d.]+)', resp)
            scores = {int(k): float(v) for k, v in pairs}
        except Exception:
            scores = {j: 0.5 for j in range(len(batch))}

        for j, chunk in enumerate(batch):
            score = scores.get(j, 0.5)
            if score >= threshold:
                chunk["relevance"] = score
                scored.append(chunk)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:max_chunks]


def run_pipeline(topic: str, depth: str = "Standard",
                 progress_callback=None) -> dict:
    """Run the complete data pipeline"""
    config = DEPTH_CONFIGS[depth]

    def update(msg):
        if progress_callback:
            progress_callback(msg)

    update("🔍 Generating search queries...")
    queries = generate_queries(topic, depth, progress_callback=progress_callback)

    update(f"🌐 Searching the web ({len(queries)} queries)...")
    raw = collect_results(queries, config["results_per_query"])
    
    update("🧹 Cleaning and deduplicating...")
    unique = deduplicate(raw)
    chunks = chunk_text(unique)

    update("🎯 Filtering for relevance...")
    relevant = filter_relevant(
        chunks, topic,
        max_chunks=config["chunks"] * 2,
        progress_callback=progress_callback
    )
    final = relevant[:config["chunks"]]

    sources = list({c["url"]: c["title"] for c in final}.items())

    return {
        "topic":        topic,
        "depth":        depth,
        "queries":      queries,
        "chunks":       final,
        "sources":      sources,
        "source_count": len(sources),
        "total_words":  sum(len(c["content"].split()) for c in final),
    }

