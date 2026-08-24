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

# 2. Create Gradio Blocks
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

# 3. Mount Gradio onto the FastAPI app (FastAPI becomes the ASGI host)
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

# 4. Provide the host app back to Gradio so demo.launch() serves the FastAPI app
demo.app = app

if __name__ == "__main__":
    # 5. Launch without hardcoding ports so Hugging Face ZeroGPU proxy can assign PORT automatically
    demo.launch()
