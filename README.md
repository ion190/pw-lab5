# go2web

A command-line HTTP client built over raw TCP sockets — no `requests` library, no `urllib` for HTTP. Just sockets.

## Usage

```
go2web -u <URL>          # Make an HTTP request and print human-readable response
go2web -s <search-term>  # Search DuckDuckGo and print top 10 results
go2web -h                # Show help
```

## Setup

```bash
pip install -r requirements.txt
chmod +x go2web
```

Then run directly:
```bash
./go2web -h
./go2web -u https://example.com
./go2web -s python sockets
```

Or add to PATH:
```bash
export PATH="$PATH:/path/to/this/repo"
go2web -h
```

## Demo

> GIF coming soon

## Features

- [x] `-h` help flag
- [x] `-u` HTTP/HTTPS requests via raw TCP socket
- [x] `-s` DuckDuckGo search, top 10 results
- [x] HTTP redirect following (301, 302, 303, 307, 308)
- [x] Search result links accessible via CLI (interactive prompt)
- [x] HTTP cache (file-based, 5 min TTL, stored in `~/.go2web_cache/`)
- [x] Content negotiation — sends typed `Accept` headers, handles JSON + HTML (`-f json|html|auto`)

## Tech

- Raw TCP sockets: `socket` + `ssl` (stdlib)
- CLI: `argparse` (stdlib)
- HTML parsing: `beautifulsoup4` (3rd party)
