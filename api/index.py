import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI

error_detail = None

try:
    from perplexity_mcp.http_server import app
except Exception:
    error_detail = traceback.format_exc()
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "error", "traceback": error_detail}

    @app.get("/")
    def root():
        return {"status": "error", "traceback": error_detail}