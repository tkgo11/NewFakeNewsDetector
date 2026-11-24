import argparse
import os
import sys

import httpx
import uvicorn
from pydantic import ValidationError

from .engine import Engine, configured_catalog
from .google import GoogleFactChecks
from .models import CheckRequest


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="newfakenews", description="Check a single factual claim."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    server = commands.add_parser("serve", help="Start the local web app and API")
    server.add_argument("--port", type=int, default=8000)

    check = commands.add_parser("check", help="Check a claim and print JSON")
    check.add_argument("claim", help="Quote a claim or pass '-' to read it from stdin")
    check.add_argument("--language", choices=["auto", "ko", "en"], default="auto")
    check.add_argument("--online", action="store_true", help="Send the claim to Google Fact Check")

    args = parser.parse_args()
    if args.command == "serve":
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        uvicorn.run(
            "newfakenewsdetector.server:create_app",
            factory=True,
            host="127.0.0.1",
            port=args.port,
            access_log=False,
        )
        return 0

    try:
        claim = sys.stdin.read(4096) if args.claim == "-" else args.claim
        request = CheckRequest(claim=claim, language=args.language, online=args.online)
        catalog = configured_catalog()
    except (ValidationError, OSError) as exc:
        detail = (
            exc.errors(include_input=False)[0]["msg"] if isinstance(exc, ValidationError) else exc
        )
        parser.exit(2, f"newfakenews: {detail}\n")

    key = os.environ.get("GOOGLE_FACTCHECK_API_KEY", "").strip()
    with httpx.Client(timeout=httpx.Timeout(5, connect=2), trust_env=False) as client:
        provider = GoogleFactChecks(key, client) if key else None
        result = Engine(catalog, provider).check(request)
    print(result.model_dump_json(indent=2))
    return 0
