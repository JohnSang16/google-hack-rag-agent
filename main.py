import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.api.server import app
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
