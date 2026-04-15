import uvicorn
from app.main import app

# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug --access-log
# 
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="debug",
        access_log=True,
    )
