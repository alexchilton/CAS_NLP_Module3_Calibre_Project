import asyncio
from fastmcp import Client


async def test():
    async with Client("http://127.0.0.1:8000") as client:
        # List available tools
        tools = await client.list_tools()
        print("Available tools:", tools)

        # Call get_current_time
        result = await client.call_tool("get_current_time", {"timezone": "UTC"})
        print("Result:", result)


asyncio.run(test())