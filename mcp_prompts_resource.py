# Add these NEW tools to expose your resources:

@mcp.tool()
def get_server_info() -> str:
    """Get information about this MCP server including available tools and capabilities."""
    return """
    Open WebUI MCP Server
    =====================
    Version: 1.0.0
    Port: 8005
    Transport: Streamable HTTP

    Available Tools: 4
    - calculator: Basic arithmetic operations
    - text_analyzer: Text statistics and analysis
    - string_transformer: String transformations
    - list_operations: List processing operations

    Available Resources: 3
    - server://info
    - docs://readme
    - docs://api/{tool_name}

    Available Prompts: 3
    - code_review
    - data_analysis
    - writing_assistant
    """


@mcp.tool()
def get_readme() -> str:
    """Get comprehensive server documentation and usage guide."""
    return """
    # MCP Server Documentation

    ## Overview
    This MCP server provides tools for mathematical operations, text processing,
    and list manipulations that can be used by LLMs through Open WebUI.

    ## Available Tools

    ### calculator(num1, num2, operator)
    Performs basic arithmetic: +, -, *, /

    ### text_analyzer(text)
    Returns statistics: word count, character count, sentence count, etc.

    ### string_transformer(text, operation)
    Transforms text: uppercase, lowercase, reverse, title, capitalize, snake_case, camel_case

    ### list_operations(items, operation)
    List operations: sum, average, min, max, sort, reverse, unique

    ## Usage
    Configure this server in Open WebUI by pointing to:
    http://localhost:8005
    """


@mcp.tool()
def get_tool_documentation(tool_name: str) -> str:
    """
    Get detailed documentation for a specific tool.

    Parameters
    ----------
    tool_name : str
        The name of the tool: "calculator", "text_analyzer", "string_transformer", or "list_operations"
    """
    docs = {
        "calculator": """
        # Calculator Tool

        Performs basic arithmetic operations.

        **Parameters:**
        - num1 (float): First number
        - num2 (float): Second number
        - operator (str): One of "+", "-", "*", "/"

        **Example:**
        calculator(10, 5, "+") -> 15.0
        """,

        "text_analyzer": """
        # Text Analyzer Tool

        Analyzes text and returns comprehensive statistics.

        **Parameters:**
        - text (str): The text to analyze

        **Returns:**
        Dictionary with character_count, word_count, sentence_count, 
        average_word_length, and longest_word.
        """,

        "string_transformer": """
        # String Transformer Tool

        Transforms strings in various ways.

        **Parameters:**
        - text (str): Text to transform
        - operation (str): Transformation type

        **Operations:**
        uppercase, lowercase, reverse, title, capitalize, snake_case, camel_case
        """,

        "list_operations": """
        # List Operations Tool

        Performs operations on lists of numbers.

        **Parameters:**
        - items (list): List of numbers
        - operation (str): Operation to perform

        **Operations:**
        sum, average, min, max, sort, reverse, unique
        """
    }

    return docs.get(tool_name, f"No documentation found for tool: {tool_name}")