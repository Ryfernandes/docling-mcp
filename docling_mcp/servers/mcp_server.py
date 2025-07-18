"""This module initializes and runs the Docling MCP server."""

import enum
import os

import typer

#import docling_mcp.tools.conversion
import docling_mcp.tools.generation
import docling_mcp.tools.manipulation
from docling_mcp.logger import setup_logger
from docling_mcp.shared import mcp
import docling_mcp.shared as shared
from docling_core.types.doc.document import DoclingDocument

from fastapi import Request
from fastapi.responses import JSONResponse

if (
    os.getenv("RAG_ENABLED") == "true"
    and os.getenv("OLLAMA_MODEL") != ""
    and os.getenv("EMBEDDING_MODEL") != ""
):
    from docling_mcp.tools.applications import (
        export_docling_document_to_vector_db,
        search_documents,
    )

app = typer.Typer()

@mcp.custom_route("/document", methods=["POST"])
async def upload_document(request: Request) -> None:
    json_data = await request.json()

    if 'document' in json_data:
        shared.document = DoclingDocument.model_validate(json_data["document"])
        return JSONResponse(
            content={"message": "Document uploaded successfully."},
            status_code=200,
        )
    
    return JSONResponse(
        content={"error": "No document provided in the request."},
        status_code=400,
    )

class TransportType(str, enum.Enum):
    """List of available protocols."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


@app.command()
def main(
    transport: TransportType = TransportType.STDIO,
    http_port: int = 8000,
) -> None:
    """Initialize and run the Docling MCP server."""
    # Create a default project logger
    logger = setup_logger()
    logger.info("starting up Docling MCP-server ...")

    # Initialize and run the server
    mcp.settings.port = http_port
    mcp.run(transport=transport.value)


if __name__ == "__main__":
    main()
