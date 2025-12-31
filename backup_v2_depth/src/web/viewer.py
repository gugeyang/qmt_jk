from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import os
import mysql.connector
import yaml

app = FastAPI()

# 基础路径适配：自动识别平铺或嵌套部署
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 优先查找当前目录
if os.path.exists(os.path.join(CURRENT_DIR, "config.yaml")):
    BASE_DIR = CURRENT_DIR
    CONFIG_PATH = os.path.join(CURRENT_DIR, "config.yaml")
else:
    # 兼容本地开发时的嵌套结构 (src/web/viewer.py)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
    CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

def get_db_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config['database']

def connect_to_db():
    try:
        db_cfg = get_db_config()
        mydb = mysql.connector.connect(
            host=db_cfg['host'],
            port=db_cfg['port'],
            user=db_cfg['user'],
            password=db_cfg['password'],
            database=db_cfg['database']
        )
        return mydb, mydb.cursor(dictionary=True)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None, None

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

# 背景任务：Linux 端由于没有 QMT 推送，改为轮询数据库最新信号进行播放
async def db_poller():
    last_id = 0
    # 先获取当前最大的 ID，防止启动时刷出一堆旧信号
    mydb, cursor = connect_to_db()
    if cursor:
        cursor.execute("SELECT MAX(id) as max_id FROM signal_history")
        res = cursor.fetchone()
        if res and res['max_id']:
            last_id = res['max_id']
        cursor.close()
        mydb.close()

    while True:
        try:
            mydb, cursor = connect_to_db()
            if cursor:
                # 获取比上次 ID 更大的新信号
                cursor.execute("""
                    SELECT s.*, m.name 
                    FROM signal_history s
                    LEFT JOIN monitored_stocks m ON s.stock_code = m.code 
                    WHERE s.id > %s
                    ORDER BY s.id ASC
                """, (last_id,))
                new_signals = cursor.fetchall()
                for sig in new_signals:
                    # 格式化时间
                    if 'timestamp' in sig and sig['timestamp']:
                        sig['timestamp'] = str(sig['timestamp'])
                    await manager.broadcast(json.dumps(sig))
                    last_id = sig['id']
                cursor.close()
                mydb.close()
        except Exception as e:
            print(f"轮询异常: {e}")
        await asyncio.sleep(2) # 每 2 秒查一次库

@app.get("/api/signals")
async def get_signals():
    mydb, cursor = connect_to_db()
    if not mydb: return []
    try:
        cursor.execute("SELECT s.*, m.name FROM signal_history s LEFT JOIN monitored_stocks m ON s.stock_code = m.code ORDER BY s.timestamp DESC LIMIT 100")
        return cursor.fetchall()
    finally:
        cursor.close()
        mydb.close()

@app.get("/api/stocks")
async def get_stocks():
    mydb, cursor = connect_to_db()
    if not mydb: return []
    try:
        cursor.execute("SELECT * FROM monitored_stocks")
        stocks = cursor.fetchall()
        for s in stocks:
            s['price'] = 0.0 # Linux 端无法获取实时行情，设为 0
            s['change_pct'] = 0.0
        return stocks
    finally:
        cursor.close()
        mydb.close()

@app.get("/api/status")
async def get_status():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return {
        "status": "Remote Worker Mode",
        "last_scan_time": "See Windows Client",
        "stock_count": 0,
        "interval": cfg.get('monitor', {}).get('interval', 5)
    }

@app.get("/")
async def get():
    # 优先在当前目录查找 index.html
    local_path = os.path.join(CURRENT_DIR, "index.html")
    if os.path.exists(local_path):
        template_path = local_path
    else:
        template_path = os.path.join(BASE_DIR, "src", "web", "templates", "index.html")
        
    if not os.path.exists(template_path):
        return HTMLResponse(f"<h3>错误：找不到网页模板</h3><p>请确保 index.html 存在。当前查找路径：{template_path}</p>")
        
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup():
    asyncio.create_task(db_poller())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
