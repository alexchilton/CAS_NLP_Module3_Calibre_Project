# setup.py
from setuptools import setup, find_packages

setup(
    name="calibre-tools",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "sentence-transformers>=2.2.0",
        "scikit-learn>=1.0.0",
        "numpy>=1.20.0",
        "fastmcp>=0.1.0",  # Ensure correct version
    ],
    entry_points={
        "console_scripts": [
            "calibre-semantic-search=calibre_tools.semantic_search:main",
            "calibre-duplicate-finder=calibre_tools.duplicate_finder:main",
            "calibre-isbn-tools=calibre_tools.isbn_tools:main",
            "calibre-mcp-server=calibre_mcp.app:main",
        ],
    },
)