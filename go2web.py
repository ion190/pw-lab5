#!/usr/bin/env python3

import argparse
import sys


def show_help():
    print("""go2web - HTTP over TCP Sockets

Usage:
  go2web -u <URL> [-f json|html]   Make an HTTP request and print the response
  go2web -s <search-term>          Search DuckDuckGo and print top 10 results
  go2web -h                        Show this help message

Options:
  -f <format>   Preferred content type: 'json' or 'html' (default: auto-detect)

Examples:
  go2web -u http://example.com
  go2web -u https://httpbin.org/get -f json
  go2web -u https://example.com -f html
  go2web -s "python socket programming"
  go2web -s python tutorial
""")


def handle_url(url: str, prefer: str = "auto"):
    from http_client import fetch
    try:
        result = fetch(url, prefer=prefer)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_search(search_term: str):
    from search import search
    from http_client import fetch
    try:
        formatted, results = search(search_term)
        print(f"Top results for: \"{search_term}\"\n")
        print(formatted)

        if not results:
            return

        # Interactive: let user open any result by number
        print("-" * 40)
        print(f"Open a result? Enter 1-{len(results)} or press Enter to exit: ", end="", flush=True)
        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not choice:
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                url = results[idx]["url"]
                print(f"\nFetching: {url}\n")
                print("=" * 40)
                content = fetch(url)
                print(content)
            else:
                print(f"Invalid choice. Enter a number between 1 and {len(results)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-u", metavar="URL", help="Make an HTTP request to the URL")
    parser.add_argument("-s", metavar="SEARCH_TERM", nargs="+", help="Search term")
    parser.add_argument("-f", metavar="FORMAT", choices=["json", "html", "auto"],
                        default="auto", help="Preferred content type: json, html, or auto")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")

    args = parser.parse_args()

    if args.help or len(sys.argv) == 1:
        show_help()
        sys.exit(0)

    if args.u:
        handle_url(args.u, prefer=args.f)
    elif args.s:
        search_term = " ".join(args.s)
        handle_search(search_term)
    else:
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
