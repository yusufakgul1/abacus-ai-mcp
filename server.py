import os
import secrets
import httpx
import jwt
from jwt import PyJWKClient
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

BASE = "https://routellm.abacus.ai/v1"
RESOURCE = "https://abacus-ai-mcp.onrender.com"
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "").strip().removeprefix("https://").rstrip("/")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", RESOURCE)
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
            return "\\n".join(str(m["id"]) for m in r.json().get("data", []) if "id" in m) or "No models returned."
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

def valid_auth0_token(token: str) -> bool:
    if not AUTH0_DOMAIN:
        return False
    try:
        signing_key = PyJWKClient("https://" + AUTH0_DOMAIN + "/.well-known/jwks.json").get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256"],
                            audience=AUTH0_AUDIENCE, issuer="https://" + AUTH0_DOMAIN + "/")
        return "mcp:tools" in claims.get("scope", "").split()
    except (jwt.PyJWTError, ValueError, KeyError, Exception):
        return False

@app.middleware("http")
async def auth(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        authorization = request.headers.get("authorization", "")
        legacy = os.getenv("MCP_ACCESS_TOKEN", "")
        valid_legacy = bool(legacy) and secrets.compare_digest(authorization, "Bearer " + legacy)
        bearer = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not (valid_legacy or (bearer and valid_auth0_token(bearer))):
            return JSONResponse(
                {"error": "Unauthorized"}, status_code=401,
                headers={"WWW-Authenticate": 'Bearer resource_metadata="' + RESOURCE + '/.well-known/oauth-protected-resource"'}
            )
    return await call_next(request)

@app.get("/.well-known/oauth-protected-resource")
async def oauth_resource_metadata():
    if not AUTH0_DOMAIN:
        return JSONResponse({"error": "AUTH0_DOMAIN not configured"}, status_code=503)
    return {"resource": RESOURCE, "authorization_servers": ["https://" + AUTH0_DOMAIN + "/"],
            "scopes_supported": ["mcp:tools"], "bearer_methods_supported": ["header"]}

@app.get("/health")
async def health():
    return {"ok": True}

app.mount("/mcp", mcp.streamable_http_app())
