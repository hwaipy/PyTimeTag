#!/usr/bin/env python3
"""Download a file from a URL to a local path."""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def infer_output_path(url: str) -> pathlib.Path:
    parsed = urllib.parse.urlparse(url)
    name = pathlib.Path(parsed.path).name
    if not name:
        name = "downloaded_file"
    return pathlib.Path(name)


def download_file(url: str, output: pathlib.Path, timeout: float, retries: int) -> None:
    last_error: Exception | None = None
    output.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                if response.status >= 400:
                    raise urllib.error.HTTPError(
                        url=url,
                        code=response.status,
                        msg=f"HTTP error {response.status}",
                        hdrs=response.headers,
                        fp=None,
                    )
                data = response.read()
            output.write_bytes(data)
            print(f"Downloaded: {url}")
            print(f"Saved to : {output.resolve()}")
            print(f"Bytes    : {len(data)}")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt > retries:
                break
            wait_seconds = min(2 ** (attempt - 1), 8)
            print(
                f"Attempt {attempt} failed ({exc}). Retrying in {wait_seconds}s...",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Failed to download after {retries + 1} attempt(s): {last_error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download a file from a URL.")
    parser.add_argument("url", help="Direct URL of the file to download")
    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        help="Output file path (default: infer from URL filename)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Network timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry count on failure (default: 2)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing output file",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_path = args.output or infer_output_path(args.url)
    if output_path.exists() and not args.overwrite:
        print(
            f"Output file already exists: {output_path}. "
            "Use --overwrite to replace it.",
            file=sys.stderr,
        )
        return 2

    if args.retries < 0:
        print("--retries must be >= 0", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be > 0", file=sys.stderr)
        return 2

    try:
        download_file(args.url, output_path, args.timeout, args.retries)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
