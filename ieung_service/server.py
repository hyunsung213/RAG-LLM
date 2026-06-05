from __future__ import annotations

import os

from api_server import create_app


app = create_app()


def to_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    host = os.getenv("IEUNG_API_HOST", "127.0.0.1")
    port = int(os.getenv("IEUNG_API_PORT", "8080"))
    debug = to_bool(os.getenv("IEUNG_API_DEBUG", "false"))
    app.run(host=host, port=port, debug=debug)
