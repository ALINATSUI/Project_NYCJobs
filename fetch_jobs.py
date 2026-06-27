#!/usr/bin/env python3
"""
Fetches NYC job posting data and dumps it to JSON files for later processing.

Outputs:
  public-sector-raw.json   — NYC government jobs from NYC OpenData
  private-sector-raw.json  — NYC private-sector jobs from Bluedoor

Required env vars:
  NYC_APP_TOKEN    — NYC OpenData app token (optional but avoids rate limits)
  BLUEDOOR_API_KEY — Bluedoor API key (jobs_live_*); omit to use anonymous tier
"""

import json
import os
import time
from collections.abc import Iterator

import requests

# ── Configuration ──────────────────────────────────────────────────────────────
NYC_APP_TOKEN = os.environ.get("NYC_APP_TOKEN", "")
BLUEDOOR_API_KEY = os.environ.get("BLUEDOOR_API_KEY", "")

NYC_OPENDATA_URL = "https://data.cityofnewyork.us/resource/kpav-sd4t.json"
BLUEDOOR_BASE_URL = "https://api.bluedoor.sh/job-postings"

NYC_PAGE_SIZE = 1000
BLUEDOOR_PAGE_SIZE = 100
REQUEST_DELAY = 0.25  # seconds between requests
MAX_RETRIES = 5
MAX_RETRY_WAIT = 120  # seconds; abort if the API demands a longer backoff


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _http(method: str, url: str, **kwargs) -> requests.Response:
    """Request with automatic retry for rate limits, transient errors, and 5xx."""
    retries = 0
    while True:
        try:
            resp = requests.request(method, url, timeout=30, **kwargs)
        except requests.exceptions.RequestException as exc:
            retries += 1
            if retries >= MAX_RETRIES:
                raise
            wait = 2 ** (retries - 1)
            print(f"  Network error ({exc}). Retrying in {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 10))
            if retry_after > MAX_RETRY_WAIT:
                raise RuntimeError(
                    f"Rate limited. API requested a {retry_after}s wait "
                    f"(>{MAX_RETRY_WAIT}s limit). Re-run the script later."
                )
            print(f"  Rate limited — waiting {retry_after}s before retrying...")
            time.sleep(retry_after)
            continue  # 429s don't count against the retry budget

        if 500 <= resp.status_code < 600:
            retries += 1
            if retries >= MAX_RETRIES:
                resp.raise_for_status()
            wait = 30 * (2 ** (retries - 1))
            print(f"  Server error {resp.status_code}. Retrying in {wait}s...")
            time.sleep(wait)
            continue

        resp.raise_for_status()
        return resp


def _json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError as exc:
        raise ValueError(f"Non-JSON response ({resp.status_code}): {resp.text[:200]}") from exc


# ── Fetchers ───────────────────────────────────────────────────────────────────

def fetch_nyc_public_jobs() -> Iterator[tuple[list[dict], str]]:
    headers = {}
    if NYC_APP_TOKEN:
        headers["X-App-Token"] = NYC_APP_TOKEN

    offset = 0

    while True:
        resp = _http(
            "GET",
            NYC_OPENDATA_URL,
            headers=headers,
            params={
                "$limit": NYC_PAGE_SIZE,
                "$offset": offset,
                "$order": ":id",
            },
        )

        page: list[dict] = _json(resp)
        if not page:
            break

        yield page, "?"

        if len(page) < NYC_PAGE_SIZE:
            break

        offset += NYC_PAGE_SIZE
        time.sleep(REQUEST_DELAY)


def fetch_bluedoor_nyc_jobs() -> Iterator[tuple[list[dict], int | str]]:
    headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    if BLUEDOOR_API_KEY:
        headers["Authorization"] = f"Bearer {BLUEDOOR_API_KEY}"

    cursor: str | None = None
    total: int | str = "?"

    while True:
        payload: dict[str, object] = {
            "city": "New York",
            "limit": BLUEDOOR_PAGE_SIZE,
            "include": "description",
        }
        if cursor:
            payload["cursor"] = cursor

        resp = _http("POST", f"{BLUEDOOR_BASE_URL}/v1/jobs/search", headers=headers, json=payload)
        result = _json(resp)
        page: list[dict] = result.get("data", [])

        meta = result.get("meta", {})
        if "total_matching" in meta:
            total = meta["total_matching"]

        yield page, total

        cursor = meta.get("next_cursor")
        if not cursor or not page:
            break

        time.sleep(REQUEST_DELAY)


# ── Main ───────────────────────────────────────────────────────────────────────

def save_incrementally(
    pages: Iterator[tuple[list[dict], int | str]], path: str, label: str
) -> None:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("[")
        first = True
        for page, total in pages:
            for record in page:
                if not first:
                    f.write(",")
                f.write("\n")
                json.dump(record, f, ensure_ascii=False)
                first = False
                count += 1
            f.flush()
            print(f"  {label}: {count} / {total} records saved...")
        f.write("\n]")
    size_mb = os.path.getsize(path) / 1_048_576
    print(f"  Saved {path} ({count} records, {size_mb:.1f} MB)")


def confirm_replace(path: str) -> bool:
    size_mb = os.path.getsize(path) / 1_048_576
    while True:
        answer = input(f"  {path} already exists ({size_mb:.1f} MB). Replace it? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False


def main() -> None:
    print("Fetching public-sector jobs from NYC OpenData...")
    if os.path.exists("public-sector-raw.json") and not confirm_replace("public-sector-raw.json"):
        print("  Skipping public-sector fetch.")
    else:
        save_incrementally(fetch_nyc_public_jobs(), "public-sector-raw.json", "NYC OpenData")

    print("\nFetching private-sector NYC jobs from Bluedoor...")
    if os.path.exists("private-sector-raw.json") and not confirm_replace("private-sector-raw.json"):
        print("  Skipping private-sector fetch.")
    else:
        save_incrementally(fetch_bluedoor_nyc_jobs(), "private-sector-raw.json", "Bluedoor")

    print("\nDone.")


if __name__ == "__main__":
    main()
