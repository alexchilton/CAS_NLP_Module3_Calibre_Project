#!/bin/bash

# Your actual library path
MAIN_LIBRARY="$HOME/Calibre Library"

# Verify it works first
echo "Testing library access..."
book_count=$(calibredb list --library-path "$MAIN_LIBRARY" --fields id | tail -n +2 | wc -l)
echo "Found $book_count books in library"

if [ "$book_count" -lt 100 ]; then
  echo "Error: Library not found or has fewer than 100 books"
  exit 1
fi

# Create export directories
mkdir -p ~/semantic_export
mkdir -p ~/mcp_export

# Export 100 books for semantic search (preferring books with descriptions)
echo ""
echo "=== Exporting books for SEMANTIC SEARCH database ==="
count=0
for id in $(calibredb list --library-path "$MAIN_LIBRARY" \
  --fields id --limit 200 | tail -n +2 | awk '{print $1}'); do

  if [ $count -ge 100 ]; then break; fi

  if calibredb export --library-path "$MAIN_LIBRARY" \
    --dont-save-cover \
    --single-dir "$id" --to-dir ~/semantic_export 2>/dev/null; then
    printf "\r✓ Exported book $id ($((count+1))/100)"
    ((count++))
  fi
done
echo ""
echo "Semantic export complete: $count books"

# Export 100 DIFFERENT books for MCP testing (skip first 100, get next 100)
echo ""
echo "=== Exporting books for MCP TEST database ==="
count=0
for id in $(calibredb list --library-path "$MAIN_LIBRARY" \
  --fields id --limit 300 | tail -n +2 | awk '{print $1}' | tail -n +101); do

  if [ $count -ge 100 ]; then break; fi

  if calibredb export --library-path "$MAIN_LIBRARY" \
    --dont-save-cover \
    --single-dir "$id" --to-dir ~/mcp_export 2>/dev/null; then
    printf "\r✓ Exported book $id ($((count+1))/100)"
    ((count++))
  fi
done
echo ""
echo "MCP export complete: $count books"

# Create the new database directories
mkdir -p ~/calibre_semantic_test
mkdir -p ~/calibre_mcp_test

# Import to new databases
echo ""
echo "=== Creating SEMANTIC SEARCH database ==="
calibredb add --library-path ~/calibre_semantic_test --recurse ~/semantic_export

echo ""
echo "=== Creating MCP TEST database ==="
calibredb add --library-path ~/calibre_mcp_test --recurse ~/mcp_export

echo ""
echo "========================================="
echo "✓ All done! Your test databases are ready:"
echo "  - Semantic search: ~/calibre_semantic_test"
echo "  - MCP testing: ~/calibre_mcp_test"
echo ""
echo "Verify with:"
echo "  calibredb list --library-path ~/calibre_semantic_test | wc -l"
echo "  calibredb list --library-path ~/calibre_mcp_test | wc -l"