"""This module initializes and runs a sidecar FastAPI server to deterministically interact with the files in docling-mcp's local cache."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import typer
import uvicorn
import os

from docling_mcp.docling_cache import get_cache_dir

CACHE_DIR = get_cache_dir()

app = typer.Typer()
api_app = FastAPI()

@api_app.get("/cache/{cache_key}", response_class=FileResponse)
def get_markdown(cache_key: str):
    """Serve a markdown file from the cache directory."""
    file_path = CACHE_DIR / f"{cache_key}.md"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File {cache_key}.md not found in cache.")
    
    return FileResponse(path=file_path, media_type="text/markdown")

@api_app.get("/cache")
def list_cache_files():
    """List all markdown files in the cache directory."""
    if not CACHE_DIR.exists():
        raise HTTPException(status_code=404, detail="Cache directory does not exist.")
    
    files = [f.name for f in CACHE_DIR.glob("*.md")]
    
    if not files:
        raise HTTPException(status_code=404, detail=f"No markdown files found in cache at {CACHE_DIR}")
    
    return {"files": files}

@app.command()
def main(port: int = 8080):
    print(f"Starting FastAPI sidecar server on port {port}...")
    uvicorn.run(api_app, host="127.0.0.1", port=port)

if __name__ == "__main__":
    main()