import os
import sys
from pathlib import Path

# Ensure all internal packages are on sys.path
REPO_ROOT = Path(__file__).resolve().parent
PACKAGE_PATHS = [
    REPO_ROOT / "packages" / "schemas",
    REPO_ROOT / "packages" / "planning",
    REPO_ROOT / "packages" / "metrics",
    REPO_ROOT / "packages" / "benchmark",
    REPO_ROOT / "packages" / "decision",
    REPO_ROOT / "packages" / "explanation",
    REPO_ROOT / "packages" / "plugin_sdk",
    REPO_ROOT / "services" / "simulator",
    REPO_ROOT / "services" / "tracking",
    REPO_ROOT / "services" / "agent_service",
    REPO_ROOT / "ml",
    REPO_ROOT / "apps" / "api",
]

for p in PACKAGE_PATHS:
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

# ZeroGPU requirement: Hugging Face ZeroGPU checks for at least one @spaces.GPU function on startup
try:
    import spaces

    @spaces.GPU
    def gpu_compute(fn, *args, **kwargs):
        """ZeroGPU executor for GPU-accelerated computing."""
        return fn(*args, **kwargs)

except (ImportError, Exception):
    def gpu_compute(fn, *args, **kwargs):
        return fn(*args, **kwargs)

import gradio as gr
from planbench_api.main import create_app

# 1. Create the PlanBench FastAPI application
fastapi_app = create_app()

# 2. Patch Gradio's create_app to inject an ASGI router middleware.
# ZeroGPU spaces intercepts demo.launch() and creates its own Gradio ASGI app.
# By patching create_app, we ensure our API routes take precedence without stripping prefixes.
original_create_app = gr.routes.App.create_app

class AsgiRouterMiddleware:
    def __init__(self, gradio_app, fastapi_app):
        self.gradio_app = gradio_app
        self.fastapi_app = fastapi_app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] == "http":
            # Route API, docs and OpenAPI paths to FastAPI
            if path.startswith("/api/") or path.startswith("/docs") or path.startswith("/openapi.json"):
                await self.fastapi_app(scope, receive, send)
                return
        elif scope["type"] == "websocket":
            # WebSocket connections for simulation streaming must reach
            # FastAPI — the /ws/ prefix is registered on the FastAPI router
            # (routers/ws.py), and Gradio has no WebSocket handler for it.
            # Without this branch every "Run one episode" click on the Test
            # Bench page silently fails with "WebSocket connection failed"
            # because the connection is accepted by Gradio and immediately
            # closed with no protocol handler.
            if path.startswith("/ws/"):
                await self.fastapi_app(scope, receive, send)
                return
        # Everything else (Gradio UI, static assets, lifespan) goes to Gradio
        await self.gradio_app(scope, receive, send)

def patched_create_app(*args, **kwargs):
    gradio_app = original_create_app(*args, **kwargs)
    return AsgiRouterMiddleware(gradio_app, fastapi_app)

gr.routes.App.create_app = patched_create_app

# 3. Create Gradio Blocks
with gr.Blocks(title="PlanBench API") as demo:
    gr.Markdown(
        """
        # 🚀 PlanBench Backend API

        The PlanBench FastAPI backend is active and running on Hugging Face Spaces (ZeroGPU).

        - **Health Check**: [`/api/v1/health`](/api/v1/health)
        - **Interactive API Docs**: [`/docs`](/docs)
        - **OpenAPI Schema**: [`/openapi.json`](/openapi.json)
        """
    )

if __name__ == "__main__":
    # Launch without hardcoding ports so Hugging Face ZeroGPU proxy can assign PORT automatically
    demo.launch()
