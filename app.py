"""Lambda entry point — wraps the FastMCP ASGI app with Mangum."""

from __future__ import annotations

import os

from mangum import Mangum

from promptweave.server import mcp

# FastMCP exposes a Starlette ASGI app for HTTP/SSE transport
_asgi_app = mcp.http_app(path="/mcp")

# Lambda handler; lifespan="off" avoids startup/shutdown lifecycle issues on Lambda
handler = Mangum(_asgi_app, lifespan="off")

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(_asgi_app, host="0.0.0.0", port=port)
