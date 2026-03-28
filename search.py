#!/usr/bin/env python3
"""
search.py - DuckDuckGo search over raw TCP sockets.
Scrapes html.duckduckgo.com/html/ for top 10 results.
"""

import socket
import ssl
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup


SEARCH_HOST = "html.duckduckgo.com"
SEARCH_PATH_TEMPLATE = "/html/?q={query}&kl=us-en"
TIMEOUT = 10


def build_search_request(query: str) -> str:
    """Build a raw HTTP POST-style GET request for DuckDuckGo HTML search."""
    encoded = quote_plus(query)
    path = SEARCH_PATH_TEMPLATE.format(query=encoded)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {SEARCH_HOST}\r\n"
        f"User-Agent: Mozilla/5.0 (compatible; go2web/1.0)\r\n"
        f"Accept: text/html,*/*;q=0.8\r\n"
        f"Accept-Language: en-US,en;q=0.5\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return request


def fetch_search_page(query: str) -> bytes:
    """Open a raw TLS TCP socket to DuckDuckGo and fetch the search results page."""
    request = build_search_request(query)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    sock.connect((SEARCH_HOST, 443))

    context = ssl.create_default_context()
    sock = context.wrap_socket(sock, server_hostname=SEARCH_HOST)

    sock.sendall(request.encode("utf-8"))

    raw = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            raw += chunk
        except socket.timeout:
            break

    sock.close()
    return raw


def parse_raw_response(raw: bytes) -> bytes:
    """Strip HTTP headers and return just the body bytes."""
    if b"\r\n\r\n" in raw:
        _, body = raw.split(b"\r\n\r\n", 1)
    else:
        body = raw

    # Handle chunked transfer encoding
    header_part = raw.split(b"\r\n\r\n")[0].decode("utf-8", errors="replace")
    if "transfer-encoding: chunked" in header_part.lower():
        body = decode_chunked(body)

    return body


def decode_chunked(data: bytes) -> bytes:
    """Decode HTTP chunked transfer encoding."""
    result = b""
    while data:
        crlf = data.find(b"\r\n")
        if crlf == -1:
            break
        try:
            chunk_size = int(data[:crlf].split(b";")[0].strip(), 16)
        except ValueError:
            break
        if chunk_size == 0:
            break
        result += data[crlf + 2 : crlf + 2 + chunk_size]
        data = data[crlf + 2 + chunk_size + 2 :]
    return result


def parse_results(html: bytes) -> list[dict]:
    """
    Parse DuckDuckGo HTML search results page.
    Returns a list of dicts with 'title', 'url', 'snippet'.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for result in soup.select(".result"):
        # Skip ads
        if "result--ad" in result.get("class", []):
            continue

        title_tag = result.select_one(".result__title a")
        snippet_tag = result.select_one(".result__snippet")

        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)

        # DuckDuckGo wraps URLs in a redirect — extract the real URL
        raw_href = title_tag.get("href", "")
        url = extract_real_url(raw_href)

        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

        if len(results) >= 10:
            break

    return results


def extract_real_url(href: str) -> str:
    """
    DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<encoded_url>.
    Extract the real destination URL.
    """
    if href.startswith("//duckduckgo.com/l/"):
        from urllib.parse import parse_qs
        parsed = urlparse("https:" + href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return params["uddg"][0]
    if href.startswith("http"):
        return href
    return href


def format_results(results: list[dict]) -> str:
    """Format search results for human-readable CLI output."""
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        lines.append("")

    return "\n".join(lines).strip()


def search(query: str) -> tuple[str, list[dict]]:
    """
    Main entry point: search DuckDuckGo and return (formatted_text, results_list).
    The results list is returned so go2web can offer follow-up URL access.
    """
    raw = fetch_search_page(query)
    body = parse_raw_response(raw)
    results = parse_results(body)
    formatted = format_results(results)
    return formatted, results
