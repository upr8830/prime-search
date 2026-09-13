"""`python -m prime_search.api [--reload] [--host H] [--port P]` (docs/01 §2; `make dev-api`).

Host and port come from `ServerSettings` (`PRIME_API_HOST`, `PRIME_API_PORT`, default
127.0.0.1:8765), and a flag overrides the setting for one invocation.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from prime_search.config import ServerSettings


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m prime_search.api", description="PRIME Search API")
    parser.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    parser.add_argument("--host", help="overrides PRIME_API_HOST")
    parser.add_argument("--port", type=int, help="overrides PRIME_API_PORT")
    args = parser.parse_args(argv)

    server = ServerSettings()
    uvicorn.run(
        "prime_search.api.main:app",
        host=args.host or server.api_host,
        port=args.port or server.api_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
