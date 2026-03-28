#!/usr/bin/env python3
"""
http_client.py - Raw TCP socket HTTP/HTTPS client.
No requests, no urllib.request — just sockets.
"""

import socket
import ssl
from urllib.parse import urlparse  # only used for URL string parsing, not for HTTP
from bs4 import BeautifulSoup


DEFAULT_TIMEOUT = 10
MAX_REDIRECTS = 10


def parse_url(url: str) -> dict:
    """Parse a URL into components."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    parsed = urlparse(url)
    scheme = parsed.scheme
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    return {"scheme": scheme, "host": host, "port": port, "path": path, "url": url}


ACCEPT_HEADERS = {
    "html": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "json": "application/json,application/vnd.api+json;q=0.9,*/*;q=0.8",
    "auto": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def build_request(host: str, path: str, extra_headers: dict = None, prefer: str = "auto") -> str:
    """
    Build a raw HTTP/1.1 GET request string.
    prefer: 'html', 'json', or 'auto' (default) — sets the Accept header.
    """
    accept = ACCEPT_HEADERS.get(prefer, ACCEPT_HEADERS["auto"])
    headers = {
        "Host": host,
        "User-Agent": "go2web/1.0",
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "close",
    }
    if extra_headers:
        headers.update(extra_headers)

    request = f"GET {path} HTTP/1.1\r\n"
    for key, value in headers.items():
        request += f"{key}: {value}\r\n"
    request += "\r\n"
    return request


def create_connection(scheme: str, host: str, port: int) -> socket.socket:
    """Open a TCP socket, wrapping with TLS for HTTPS."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(DEFAULT_TIMEOUT)
    sock.connect((host, port))

    if scheme == "https":
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=host)

    return sock


def send_request(sock: socket.socket, request: str) -> bytes:
    """Send the request and read the full raw response."""
    sock.sendall(request.encode("utf-8"))

    response = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    return response


def parse_response(raw: bytes) -> dict:
    """Split raw HTTP response into status, headers, and body."""
    # Split headers from body on the first blank line
    if b"\r\n\r\n" in raw:
        header_part, body = raw.split(b"\r\n\r\n", 1)
    else:
        header_part, body = raw, b""

    header_lines = header_part.decode("utf-8", errors="replace").split("\r\n")
    status_line = header_lines[0]
    status_code = int(status_line.split(" ")[1]) if len(status_line.split(" ")) > 1 else 0

    headers = {}
    for line in header_lines[1:]:
        if ": " in line:
            key, _, value = line.partition(": ")
            headers[key.lower()] = value.strip()

    # Handle chunked transfer encoding
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = decode_chunked(body)

    return {"status_code": status_code, "headers": headers, "body": body}


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


def render_response(body: bytes, content_type: str, prefer: str = "auto") -> str:
    """
    Convert response body to human-readable text.
    Respects both the server's Content-Type and the caller's preference.
    """
    import json

    is_json = "json" in content_type
    is_html = "html" in content_type or "text/plain" in content_type

    # If server returned JSON (or we asked for it), pretty-print it
    if is_json or prefer == "json":
        try:
            parsed = json.loads(body.decode("utf-8", errors="replace"))
            output = json.dumps(parsed, indent=2, ensure_ascii=False)
            if prefer == "json" and not is_json:
                output = f"[Note: server returned {content_type}, rendered as text]\n\n" + output
            return output
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # Fall through to HTML/text handling

    # HTML or plain text: strip tags and clean up
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript", "head", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)

    if prefer == "html" and not is_html:
        cleaned = f"[Note: server returned {content_type}, rendered as text]\n\n" + cleaned

    return cleaned


def fetch(url: str, redirect_count: int = 0, use_cache: bool = True, prefer: str = "auto") -> str:
    """
    Main entry point: fetch a URL over raw TCP and return human-readable text.
    Follows redirects up to MAX_REDIRECTS. Uses file-based cache by default.
    prefer: 'html', 'json', or 'auto' — controls Accept header and rendering.
    """
    if redirect_count > MAX_REDIRECTS:
        raise Exception("Too many redirects")

    # Check cache on first request (not on redirect hops)
    if use_cache and redirect_count == 0:
        try:
            import cache
            cached = cache.get(url)
            if cached is not None:
                print("  [cache hit]")
                return cached
        except ImportError:
            pass

    parts = parse_url(url)
    request = build_request(parts["host"], parts["path"], prefer=prefer)

    try:
        sock = create_connection(parts["scheme"], parts["host"], parts["port"])
        raw = send_request(sock, request)
        sock.close()
    except Exception as e:
        raise Exception(f"Connection error: {e}")

    response = parse_response(raw)
    status = response["status_code"]
    headers = response["headers"]

    # Handle redirects
    if status in (301, 302, 303, 307, 308) and "location" in headers:
        new_url = headers["location"]
        if new_url.startswith("/"):
            new_url = f"{parts['scheme']}://{parts['host']}{new_url}"
        print(f"  → Redirect {status}: {new_url}")
        return fetch(new_url, redirect_count + 1, use_cache=use_cache, prefer=prefer)

    if status < 200 or status >= 400:
        raise Exception(f"HTTP error {status}")

    content_type = headers.get("content-type", "text/html")
    result = render_response(response["body"], content_type, prefer=prefer)

    # Save to cache (only on original request, not redirect hops)
    if use_cache and redirect_count == 0:
        try:
            import cache
            cache.set(url, result)
        except ImportError:
            pass

    return result