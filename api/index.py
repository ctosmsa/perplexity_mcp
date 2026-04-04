import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI

app = FastAPI()
error_detail = None

try:
    from perplexity_mcp.http_server import app
except Exception:
    error_detail = traceback.format_exc()

@app.get("/health")
def health():
    if error_detail:
        return {"status": "error", "traceback": error_detail}
    return {"status": "ok", "service": "perplexity-mcp-server"}