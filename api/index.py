import os
import sys

# Add root directory to sys.path so app.py and root modules can be imported in Vercel serverless environment
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

__all__ = ["app"]


