import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "6020"))
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True
    )