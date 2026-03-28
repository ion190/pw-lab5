#!/usr/bin/env python3
"""
cache.py - File-based HTTP cache for go2web.
Stores responses in ~/.go2web_cache/ with a configurable TTL.
"""

import hashlib
import json
import os
import time


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".go2web_cache")
DEFAULT_TTL = 300  # seconds (5 minutes)


def _ensure_cache_dir():
    """Create the cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(url: str) -> str:
    """Generate a safe filename from a URL using MD5."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _cache_path(url: str) -> str:
    return os.path.join(CACHE_DIR, _cache_key(url) + ".json")


def get(url: str, ttl: int = DEFAULT_TTL) -> str | None:
    """
    Return cached response text for a URL if it exists and is fresh.
    Returns None on cache miss or stale entry.
    """
    path = _cache_path(url)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        age = time.time() - entry["timestamp"]
        if age > ttl:
            os.remove(path)
            return None
        return entry["content"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def set(url: str, content: str):
    """Save a response to the cache."""
    _ensure_cache_dir()
    path = _cache_path(url)
    entry = {
        "url": url,
        "timestamp": time.time(),
        "content": content,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
    except OSError:
        pass  # cache write failure is non-fatal


def clear(url: str = None):
    """
    Clear the cache. If url is given, remove only that entry.
    Otherwise clear all cached entries.
    """
    if url:
        path = _cache_path(url)
        if os.path.exists(path):
            os.remove(path)
    else:
        if os.path.isdir(CACHE_DIR):
            for fname in os.listdir(CACHE_DIR):
                if fname.endswith(".json"):
                    os.remove(os.path.join(CACHE_DIR, fname))


def status() -> dict:
    """Return info about the current cache state."""
    _ensure_cache_dir()
    entries = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    total_size = sum(
        os.path.getsize(os.path.join(CACHE_DIR, f)) for f in entries
    )
    return {
        "entries": len(entries),
        "size_kb": round(total_size / 1024, 2),
        "location": CACHE_DIR,
    }
