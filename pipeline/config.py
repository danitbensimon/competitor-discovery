# config.py — Loads environment variables from .env file.
# All other modules import keys from here.

import os
from dotenv import load_dotenv

load_dotenv()

# Web-search provider for the external signal groups (customer signals, job
# postings, tech-stack DBs, review sites, LinkedIn, blog/press). search.py reads
# BRAVE_API_KEY directly; it is mirrored here so validate() can flag its absence.
# NOTE: the pipeline migrated from SerpAPI to Brave — SERPAPI_KEY is no longer used.
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def validate():
    """Fail loudly on missing keys. Called by the CLI / batch entrypoints — NOT at
    web-server import time, so a missing key surfaces as a clear error in a run
    rather than silently collapsing 11 of the 12 sources to zero results."""
    missing = []
    if not BRAVE_API_KEY:
        missing.append("BRAVE_API_KEY")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your keys."
        )
