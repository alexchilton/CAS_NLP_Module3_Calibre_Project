import asyncio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Prompt, PromptArgument, PromptMessage, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uvicorn

# Create MCP server with prompts capability
mcp_server = Server("restaurant-prompts")


# ---------------------------------------------------------------------------
# PROMPT HANDLERS
# ---------------------------------------------------------------------------

@mcp_server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List all available prompts"""
    return [
        Prompt(
            name="analyze-menu",
            description="Analyze a restaurant menu and provide insights",
            arguments=[
                PromptArgument(
                    name="menu_name",
                    description="Name of the menu to analyze (e.g., 'menu1', 'menu2')",
                    required=True
                ),
                PromptArgument(
                    name="focus",
                    description="What to focus on: 'price', 'variety', 'dietary', or 'all'",
                    required=False
                )
            ]
        ),
        Prompt(
            name="translate-order",
            description="Help translate a customer's order from English to Japanese",
            arguments=[
                PromptArgument(
                    name="order",
                    description="The order in English (e.g., 'I want sushi and miso soup')",
                    required=True
                )
            ]
        ),
        Prompt(
            name="recommend-dish",
            description="Get dish recommendations based on preferences",
            arguments=[
                PromptArgument(
                    name="preference",
                    description="Customer preference (e.g., 'vegetarian', 'spicy', 'light')",
                    required=True
                ),
                PromptArgument(
                    name="budget",
                    description="Budget level: 'low', 'medium', or 'high'",
                    required=False
                )
            ]
        ),
        Prompt(
            name="explain-dish",
            description="Get a detailed explanation of a Japanese dish",
            arguments=[
                PromptArgument(
                    name="dish_name",
                    description="Name of the dish to explain",
                    required=True
                )
            ]
        )
    ]


@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> list[PromptMessage]:
    """Get a specific prompt with its messages"""

    if name == "analyze-menu":
        menu_name = arguments.get("menu_name", "menu1")
        focus = arguments.get("focus", "all")

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Please analyze the menu from {menu_name} and provide insights.

Focus area: {focus}

Please read the menu using the menu://{menu_name} resource and provide:
1. Overview of the menu structure
2. Price range analysis
3. Variety of dishes offered
4. Dietary options available (vegetarian, vegan, etc.)
5. Recommendations for different customer types

Format your response in a clear, organized way."""
                )
            )
        ]

    elif name == "translate-order":
        order = arguments.get("order", "")

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""I need help translating this customer order to Japanese:

"{order}"

Please provide:
1. The Japanese translation
2. Romanization (romaji) for pronunciation
3. Any cultural notes about ordering this in Japan

Be polite and use appropriate restaurant Japanese."""
                )
            )
        ]

    elif name == "recommend-dish":
        preference = arguments.get("preference", "")
        budget = arguments.get("budget", "medium")

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Please recommend dishes based on these criteria:

Customer preference: {preference}
Budget level: {budget}

Use the available menu resources (menu://list to see all menus) and suggest:
1. 3-5 dishes that match the preferences
2. Why each dish is a good fit
3. Price information
4. Any preparation notes or ingredients to be aware of

Be specific and reference actual dishes from the menus."""
                )
            )
        ]

    elif name == "explain-dish":
        dish_name = arguments.get("dish_name", "")

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Please explain the dish: {dish_name}

Provide:
1. What this dish is and its origins
2. Main ingredients and preparation method
3. Flavor profile (taste, texture, temperature)
4. Traditional accompaniments or serving style
5. Cultural significance if any
6. Common variations

Be educational but accessible for someone new to Japanese cuisine."""
                )
            )
        ]

    else:
        raise ValueError(f"Unknown prompt: {name}")


# ---------------------------------------------------------------------------
# SSE TRANSPORT HANDLERS
# ---------------------------------------------------------------------------

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
            "title": "Restaurant Prompts MCP Server",
            "version": "1.0.0",
            "description": "MCP server providing prompt templates for restaurant operations"
        },
        "servers": [{"url": "http://localhost:8003"}],
        "paths": {
            "/sse": {"get": {"summary": "SSE endpoint for MCP communication"}},
            "/message": {"post": {"summary": "POST messages for MCP"}}
        }
    })


async def health(request):
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "service": "restaurant-prompts"})


async def root(request):
    """Root info endpoint"""
    return JSONResponse({
        "service": "Restaurant Prompts MCP Server",
        "version": "1.0.0",
        "description": "Provides prompt templates for menu analysis, translation, and recommendations",
        "endpoints": {
            "sse": "/sse",
            "message": "/message/",
            "health": "/health",
            "openapi": "/openapi.json"
        },
        "available_prompts": [
            "analyze-menu",
            "translate-order",
            "recommend-dish",
            "explain-dish"
        ]
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
    print("Starting Restaurant Prompts MCP Server on http://localhost:8003")
    print("Available Prompts:")
    print("  - analyze-menu: Analyze restaurant menus")
    print("  - translate-order: Translate orders to Japanese")
    print("  - recommend-dish: Get dish recommendations")
    print("  - explain-dish: Learn about Japanese dishes")
    print("\nEndpoints:")
    print("  - Root: http://localhost:8003")
    print("  - SSE: http://localhost:8003/sse")
    print("  - Message: http://localhost:8003/message/")
    print("  - Health: http://localhost:8003/health")
    print("  - OpenAPI: http://localhost:8003/openapi.json")

    uvicorn.run(app, host="0.0.0.0", port=8003)