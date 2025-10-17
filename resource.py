import asyncio
import os
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Resource
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uvicorn

# Directory where menu files are stored (same directory as this script)
MENU_DIR = os.path.dirname(os.path.abspath(__file__))

# Create MCP server
mcp_server = Server("menu-resources")

# ---------------------------------------------------------------------------
# RESOURCE HANDLERS
# ---------------------------------------------------------------------------

@mcp_server.list_resources()
async def list_resources() -> list[Resource]:
    """List all available menu resources"""
    resources = []

    # Add a 'list' resource
    resources.append(Resource(
        uri="menu://list",
        name="Menu List",
        description="List all available restaurant menus",
        mimeType="text/plain"
    ))

    # Add individual menu resources
    for filename in os.listdir(MENU_DIR):
        if filename.endswith(".txt") and filename.startswith("menu"):
            menu_id = filename.replace(".txt", "")
            resources.append(Resource(
                uri=f"menu://{menu_id}",
                name=f"Restaurant Menu {menu_id}",
                description=f"Japanese restaurant menu - {menu_id}",
                mimeType="text/plain"
            ))

    return resources


@mcp_server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific menu resource - returns the text content"""

    if uri == "menu://list":
        # List all available menus
        menus = []
        for filename in os.listdir(MENU_DIR):
            if filename.endswith(".txt") and filename.startswith("menu"):
                menu_id = filename.replace(".txt", "")
                menus.append(f"- menu://{menu_id}")

        return "Available menus:\n" + "\n".join(menus) if menus else "No menus found in directory"

    if uri.startswith("menu://"):
        menu_name = uri.replace("menu://", "")
        menu_file = os.path.join(MENU_DIR, f"{menu_name}.txt")

        if os.path.exists(menu_file):
            with open(menu_file, "r", encoding="utf-8") as f:
                return f.read()

        available = [f.replace(".txt", "") for f in os.listdir(MENU_DIR)
                     if f.endswith(".txt") and f.startswith("menu")]
        return f"Menu '{menu_name}' not found. Available menus: {', '.join(available)}"

    return f"Invalid URI: {uri}"

# ---------------------------------------------------------------------------
# SSE TRANSPORT HANDLERS
# ---------------------------------------------------------------------------

# The endpoint where clients send messages
sse_transport = SseServerTransport("/message/")

async def handle_sse(request: Request):
    """Handles GET /sse for Server-Sent Events"""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream, write_stream,
            mcp_server.create_initialization_options()
        )
    # Required: return a Response so Starlette doesn't complain
    return Response()

async def handle_messages(scope, receive, send):
    """Handles POST /message/"""
    await sse_transport.handle_post_message(scope, receive, send)

# ---------------------------------------------------------------------------
# OTHER ENDPOINTS
# ---------------------------------------------------------------------------

async def openapi(request):
    """OpenAPI schema for the MCP server"""
    return JSONResponse({
        "openapi": "3.0.0",
        "info": {
            "title": "Menu Resources MCP Server",
            "version": "1.0.0",
            "description": "MCP server for accessing Japanese restaurant menus"
        },
        "servers": [{"url": "http://localhost:8002"}],
        "paths": {
            "/sse": {"get": {"summary": "SSE endpoint for MCP communication"}},
            "/message": {"post": {"summary": "POST messages for MCP"}}
        }
    })

async def health(request):
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "service": "menu-resources"})

async def root(request):
    """Root info endpoint"""
    return JSONResponse({
        "service": "Menu Resources MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "sse": "/sse",
            "message": "/message/",
            "health": "/health",
            "openapi": "/openapi.json"
        },
        "menu_directory": MENU_DIR
    })

# ---------------------------------------------------------------------------
# STARLETTE APP SETUP
# ---------------------------------------------------------------------------

app = Starlette(
    routes=[
        Route("/", endpoint=root),
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/message/", app=sse_transport.handle_post_message),
        Route("/openapi.json", endpoint=openapi),
        Route("/health", endpoint=health),
    ]
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting Menu Resources MCP Server on http://localhost:8002")
    print(f"Menu files will be loaded from: {MENU_DIR}")
    print("Endpoints:")
    print("  - Root: http://localhost:8002")
    print("  - SSE: http://localhost:8002/sse")
    print("  - Message: http://localhost:8002/message/")
    print("  - Health: http://localhost:8002/health")
    print("  - OpenAPI: http://localhost:8002/openapi.json")

    uvicorn.run(app, host="0.0.0.0", port=8002)
