import uvicorn
from src.web.app import app

if __name__ == "__main__":
    print("正在启动 QMT 股票监控系统...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
