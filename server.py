import os
import secrets
import httpx
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

app = FastAPI(title="Abacus MCP Bridge")
mcp = FastMCP("Abacus AI", stateless_http=True, json_response=True, streamable_http_path="/")

@mcp.tool()
async def ask_abacus(prompt: str) -> str:
    """Ask a model through Abacus RouteLLM API."""
    key = os.getenv("ABACUS_API_KEY")
    model = os.getenv("ABACUS_MODEL")
    endpoint = os.getenv("ABACUS_CHAT_ENDPOINT", "https://routellm.abacus.ai/v1/chat/completions")
    if not key or not model:
        return "ABACUS_API_KEY and ABACUS_MODEL must be configured in Render."
    if not endpoint.startswith("https://"):
        return "Endpoint must use HTTPS."
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            resp = await client.post(endpoint,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]})
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        return "Abacus API call failed: " + type(e).__name__

@app.middleware("http")
async def auth(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        token = os.getenv("MCP_ACCESS_TOKEN")
        provided = request.headers.get("authorization", "")
        if not token:
            return JSONResponse({"error": "MCP_ACCESS_TOKEN is not configured"}, status_code=503)
        if not secrets.compare_digest(provided, "Bearer " + token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

@app.get("/health")
async def health():
    return {"ok": True}

app.mount("/mcp", mcp.streamable_http_app())
