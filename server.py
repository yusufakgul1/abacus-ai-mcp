import os
import secrets
import httpx
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

BASE = "https://routellm.abacus.ai/v1"
app = FastAPI(title="Abacus MCP Bridge")
mcp = FastMCP("Abacus AI", stateless_http=True, json_response=True, streamable_http_path="/")

def headers():
    key = os.getenv("ABACUS_API_KEY", "")
    if not key:
        raise ValueError("ABACUS_API_KEY is missing")
    return {"Authorization": "Bearer " + key}

@mcp.tool()
async def list_abacus_models() -> str:
    """List model identifiers available through Abacus RouteLLM."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            r = await client.get(BASE + "/models", headers=headers())
            r.raise_for_status()
            models = r.json().get("data", [])
            return "\n".join(str(m["id"]) for m in models if "id" in m) or "No models returned."
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return "Could not list models: " + type(exc).__name__

@mcp.tool()
async def ask_abacus(prompt: str, model: str) -> str:
    """Ask Abacus RouteLLM using a selected model ID from list_abacus_models."""
    if not model.strip():
        return "Specify a model ID from list_abacus_models."
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            r = await client.post(BASE + "/chat/completions", headers=headers(),
                json={"model": model, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return str(r.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        return "Abacus request failed: " + type(exc).__name__

@app.middleware("http")
async def auth(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        token = os.getenv("MCP_ACCESS_TOKEN")
        if not token:
            return JSONResponse({"error": "MCP_ACCESS_TOKEN missing"}, status_code=503)
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

@app.get("/health")
async def health():
    return {"ok": True}

app.mount("/mcp", mcp.streamable_http_app())
