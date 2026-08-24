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

from planbench_api.main import create_app

# Create the PlanBench FastAPI application
fastapi_app = create_app()

try:
    import gradio as gr

    # Simple Gradio landing status page
    with gr.Blocks(title="PlanBench API") as demo:
        gr.Markdown(
            """
            # 🚀 PlanBench Backend API

            The PlanBench FastAPI backend is active and running on Hugging Face Spaces.

            - **Health Check**: [`/api/v1/health`](/api/v1/health)
            - **Interactive API Docs**: [`/docs`](/docs)
            - **OpenAPI Schema**: [`/openapi.json`](/openapi.json)
            """
        )

    # Mount FastAPI application with Gradio
    app = gr.mount_gradio_app(fastapi_app, demo, path="/")

    if __name__ == "__main__":
        demo.launch(
            server_name="0.0.0.0",
            server_port=int(os.environ.get("PORT", 7860)),
            app=fastapi_app,
        )
except ImportError:
    app = fastapi_app

    if __name__ == "__main__":
        import uvicorn

        port = int(os.environ.get("PORT", 7860))
        uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
