# Claude Desktop MCP Server Configuration

This document explains how to configure the Calibre Tools MCP server for use with Claude Desktop.

## What is MCP?

MCP (Model Context Protocol) is Anthropic's protocol that allows Claude to interact with external tools and data sources. The MCP server runs automatically in the background and communicates with Claude Desktop via stdio (standard input/output).

**Important:** You do NOT need to manually run the MCP server. Claude Desktop automatically starts and stops it as needed.

---

## Prerequisites

1. **Claude Desktop** installed on macOS
2. **Python 3.11+** with a virtual environment
3. **Calibre** installed at `/Applications/calibre.app/`
4. **This project** installed with dependencies:
   ```bash
   cd /path/to/calibre-tools
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   pip install fastmcp
   ```

---

## Installation Steps

### 1. Locate the Claude Desktop Configuration File

The configuration file is located at:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 2. Edit the Configuration File

Open the file in your text editor:
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Or with any text editor:
```bash
open -a "TextEdit" ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### 3. Add the Calibre MCP Server Configuration

Add the following configuration to the `mcpServers` section. If the file doesn't exist or is empty, create it with this structure:

```json
{
  "mcpServers": {
    "calibre": {
      "command": "/Users/YOUR_USERNAME/path/to/project/venv/bin/python",
      "args": ["-m", "calibre_mcp.app"],
      "cwd": "/Users/YOUR_USERNAME/path/to/project",
      "env": {
        "CALIBRE_LIBRARY_PATH": "/Users/YOUR_USERNAME/Calibre Library",
        "PYTHONPATH": "/Users/YOUR_USERNAME/path/to/project",
        "PATH": "/Applications/calibre.app/Contents/MacOS:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

### 4. Customize the Paths

Replace the following placeholders with your actual paths:

**`command`:** Path to your project's venv Python interpreter
```bash
# To find this path, activate your venv and run:
which python
# Example: /Users/alexchilton/Downloads/Current_Learning/uni/BERN/CAS_NLP_M3-main/untitled/venv/bin/python
```

**`cwd`:** Path to your project root directory
```bash
# This is the directory containing calibre_tools/ and calibre_mcp/
# Example: /Users/alexchilton/Downloads/Current_Learning/uni/BERN/CAS_NLP_M3-main/untitled
```

**`CALIBRE_LIBRARY_PATH`:** Path to your Calibre library
```bash
# Usually ~/Calibre Library or a custom path
# Example: /Users/alexchilton/Calibre Library
```

**`PYTHONPATH`:** Same as `cwd` - your project root directory

### 5. Example Configuration

Here's a real example from this project:

```json
{
  "mcpServers": {
    "calibre": {
      "command": "/Users/alexchilton/Downloads/Current_Learning/uni/BERN/CAS_NLP_M3-main/untitled/venv/bin/python",
      "args": ["-m", "calibre_mcp.app"],
      "cwd": "/Users/alexchilton/Downloads/Current_Learning/uni/BERN/CAS_NLP_M3-main/untitled",
      "env": {
        "CALIBRE_LIBRARY_PATH": "/Users/alexchilton/Calibre Library",
        "PYTHONPATH": "/Users/alexchilton/Downloads/Current_Learning/uni/BERN/CAS_NLP_M3-main/untitled",
        "PATH": "/Applications/calibre.app/Contents/MacOS:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

### 6. Restart Claude Desktop

After saving the configuration file, completely quit and restart Claude Desktop:
1. Quit Claude Desktop (Cmd+Q)
2. Relaunch Claude Desktop

---

## How It Works

### Automatic Server Startup

When Claude Desktop starts, it:
1. Reads `claude_desktop_config.json`
2. For each MCP server, runs the specified `command` with `args`
3. Establishes a stdio connection to communicate with the server
4. The server runs in the background as long as Claude Desktop is open

### The Server Entry Point

The server is started via:
```bash
python -m calibre_mcp.app
```

This runs `calibre_mcp/app.py`, which:
- Imports all tool modules to register them with the MCP server
- Starts the MCP server with stdio transport (default)
- Listens for requests from Claude Desktop

### Available Tools

Once configured, Claude Desktop will have access to 22 Calibre tools:

**Search & Discovery:**
- `calibre_semantic_search` - Search using natural language
- `calibre_list_books` - List books with filters
- `calibre_search_library` - Search using Calibre syntax
- `calibre_get_book_details` - Get complete metadata
- `calibre_sql` - Execute read-only SQL queries

**Metadata Enrichment:**
- `calibre_fetch_metadata_by_identifier` - Fetch by ISBN/ASIN
- `calibre_fetch_metadata_by_title` - Fetch by title/author
- `calibre_enrich_book_metadata` - Auto-detect and enrich
- `calibre_apply_metadata_updates` - Apply suggested updates
- `calibre_find_books_needing_enrichment` - Find books needing metadata
- `calibre_batch_enrich_books` - Batch process multiple books
- `calibre_enrich_identifier_titles` - Enrich books with ISBN/ASIN as title

**Duplicate Detection:**
- `calibre_find_duplicates` - Find duplicate books

**ISBN Tools:**
- `calibre_isbn_extract_from_text` - Extract ISBNs from text
- `calibre_isbn_validate` - Validate ISBN
- `calibre_isbn_find_books` - Find books by ISBN

**Library Management:**
- `calibre_add_book` - Add book to library
- `calibre_remove_book` - Remove book from library
- `calibre_set_book_metadata` - Update book metadata
- `calibre_bulk_update_comments` - Bulk update descriptions
- `calibre_convert_format` - Convert book formats
- `calibre_export_book` - Export book files

---

## Verification

### Check if the Server is Configured

After restarting Claude Desktop, you can verify the MCP server is working by asking Claude:

```
"What Calibre tools do you have access to?"
```

Claude should list the 22 available tools.

### Test a Simple Query

Try a simple search:
```
"Search my Calibre library for science fiction books"
```

This should trigger the `calibre_semantic_search` or `calibre_search_library` tool.

### Check Server Logs (Optional)

When the MCP server starts, it writes to stderr. To see startup messages, you can temporarily run it manually:

```bash
cd /path/to/project
source venv/bin/activate
python -m calibre_mcp.app
```

You should see:
```
Starting Calibre MCP Server with stdio transport
```

Press Ctrl+C to stop. Claude Desktop will handle this automatically.

---

## Troubleshooting

### Claude Desktop doesn't see the tools

**Check the config file syntax:**
- Ensure the JSON is valid (no trailing commas, proper quotes)
- Use a JSON validator: https://jsonlint.com/

**Check file paths:**
- Verify all paths in the config are absolute (not relative)
- Ensure the venv Python path is correct: `ls -la /path/to/venv/bin/python`
- Check the project directory exists: `ls -la /path/to/project/calibre_mcp`

**Restart Claude Desktop completely:**
- Quit (Cmd+Q), don't just close the window
- Relaunch from Applications

### "calibredb not found" errors

Ensure the `PATH` environment variable includes Calibre's CLI tools:
```json
"PATH": "/Applications/calibre.app/Contents/MacOS:/usr/local/bin:/usr/bin:/bin"
```

Test manually:
```bash
/Applications/calibre.app/Contents/MacOS/calibredb --version
```

### "Module not found" errors

**Check PYTHONPATH:**
```json
"PYTHONPATH": "/full/path/to/project"
```

**Verify the project structure:**
```bash
ls -la /path/to/project/calibre_mcp/
ls -la /path/to/project/calibre_tools/
```

**Ensure dependencies are installed:**
```bash
source venv/bin/activate
pip list | grep fastmcp
pip list | grep sentence-transformers
```

### Server crashes or doesn't respond

**Check the Calibre library path:**
```bash
ls -la "/Users/YOUR_USERNAME/Calibre Library/metadata.db"
```

**Test the server manually:**
```bash
cd /path/to/project
source venv/bin/activate
python -m calibre_mcp.app
```

Look for error messages in the output.

### Multiple MCP Servers

If you have other MCP servers configured, ensure the JSON structure is correct:

```json
{
  "mcpServers": {
    "calibre": {
      "command": "...",
      "args": [...],
      "cwd": "...",
      "env": {...}
    },
    "another-server": {
      "command": "...",
      "args": [...],
      "env": {...}
    }
  }
}
```

---

## Configuration Reference

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `command` | Path to Python interpreter | `/path/to/venv/bin/python` |
| `args` | Arguments to pass to Python | `["-m", "calibre_mcp.app"]` |
| `cwd` | Working directory (project root) | `/path/to/project` |
| `env.CALIBRE_LIBRARY_PATH` | Path to Calibre library | `/Users/name/Calibre Library` |
| `env.PYTHONPATH` | Python module search path | `/path/to/project` |
| `env.PATH` | System PATH with calibredb | `/Applications/calibre.app/Contents/MacOS:...` |

### Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `env.FORCE_REFRESH` | Force cache refresh | `0` (disabled) |
| `env.CACHE_EXPIRY_DAYS` | Days before cache expires | `7` |
| `env.USE_CUDA` | Force CUDA (vs MPS on Mac) | `0` (auto-detect) |

### Environment Variables

You can add additional environment variables to the `env` section:

```json
"env": {
  "CALIBRE_LIBRARY_PATH": "/path/to/library",
  "PYTHONPATH": "/path/to/project",
  "PATH": "/Applications/calibre.app/Contents/MacOS:/usr/local/bin:/usr/bin:/bin",
  "FORCE_REFRESH": "1",
  "CACHE_EXPIRY_DAYS": "30"
}
```

---

## Advanced: HTTP Transport (Optional)

By default, the MCP server uses stdio transport for Claude Desktop. For development/testing, you can use HTTP transport:

```bash
python -m calibre_mcp.app --http
```

This starts an HTTP server at:
```
http://127.0.0.1:8765/mcp
```

**Note:** Claude Desktop does NOT support HTTP transport. This is only for testing with other MCP clients.

---

## Updating the Server

### After making code changes:

1. **No need to restart if using development mode:**
   ```bash
   pip install -e .
   ```

2. **For Claude Desktop to pick up changes:**
   - Quit and restart Claude Desktop (Cmd+Q, then relaunch)
   - The server will restart automatically with your changes

### After updating dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Then restart Claude Desktop.

---

## Security Considerations

### File Permissions

The configuration file may contain sensitive paths. Ensure proper permissions:
```bash
chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Read-Only SQL Tool

The `calibre_sql` tool is read-only and cannot modify your library. It only allows SELECT queries for safety.

### Destructive Operations

Tools like `calibre_remove_book` and `calibre_set_book_metadata` can modify your library. Claude will typically ask for confirmation before using these tools.

**Recommendation:** Always backup your Calibre library before batch operations:
```bash
cp -r ~/Calibre\ Library ~/Calibre\ Library.backup
```

---

## Uninstalling

To remove the MCP server from Claude Desktop:

1. **Edit the config file:**
   ```bash
   nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. **Remove the "calibre" section:**
   ```json
   {
     "mcpServers": {
       // Remove the entire "calibre": {...} section
     }
   }
   ```

3. **Restart Claude Desktop**

The server will no longer be loaded.

---

## Additional Resources

- **MCP Documentation:** https://modelcontextprotocol.io/
- **FastMCP Library:** https://github.com/jlowin/fastmcp
- **Calibre CLI Documentation:** https://manual.calibre-ebook.com/generated/en/cli-index.html
- **Project README:** See `README.md` for tool usage and examples

---

**Last Updated:** 2025-11-03
