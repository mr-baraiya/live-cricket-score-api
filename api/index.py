import os
import sys

# Add root directory to sys.path so app.py and root modules can be imported in Vercel serverless environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Export FastAPI instance for Vercel serverless function entrypoint
app = app

__all__ = ["app"]

