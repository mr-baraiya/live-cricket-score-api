from app import app

# Export FastAPI instance for Vercel serverless function entrypoint
__all__ = ["app"]
