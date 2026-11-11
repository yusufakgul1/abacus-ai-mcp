# Setup notes

This is an **unverified starter**, not a completed ChatGPT integration.

1. Deploy Render Blueprint from this repository.
2. Enter ABACUS_API_KEY privately in Render, never in GitHub or chat.
3. Set ABACUS_MODEL to a model ID supported by your RouteLLM account.
4. Test /health, then the authenticated /mcp endpoint.
5. ChatGPT may require OAuth-based remote MCP authentication. This server currently uses a static bearer token and **does not implement OAuth**. Do not claim ChatGPT compatibility without testing.
6. The RouteLLM chat endpoint and model availability must be confirmed against your Abacus account. AI Brain, images and videos are not implemented.
7. This is a public repository: never commit credentials.
