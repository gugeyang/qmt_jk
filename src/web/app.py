from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
import os
from src.services.monitor import MonitorService
from src.data.database import connect_to_db

app = FastAPI()

# 获取基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
DB_PATH = os.path.join(BASE_DIR, "data", "qmt_jk.db")

# 初始化监控服务
monitor = MonitorService(CONFIG_PATH, DB_PATH)
monitor.start()

# 静态文件
STATIC_DIR = os.path.join(BASE_DIR, "src", "web", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
        # 使用副本迭代，防止在广播过程中连接列表发生变化
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                # 如果发送失败，说明连接已失效，移除它
                self.disconnect(connection)

manager = ConnectionManager()

# 背景任务：定期检查并广播预警
async def alert_broadcaster():
    while True:
        try:
            if monitor.alerts:
                alert = monitor.alerts.pop(0)
                await manager.broadcast(json.dumps(alert))
        except Exception as e:
            print(f"广播预警异常: {e}")
        await asyncio.sleep(0.5) # 提高检查频率到 0.5 秒

@app.get("/api/stocks")
async def get_stocks():
    mydb, cursor = connect_to_db()
    if not mydb:
        return []
    try:
        cursor.execute("SELECT * FROM monitored_stocks ORDER BY added_at DESC")
        stocks = cursor.fetchall()
        
        # 获取实时行情
        codes = [s['code'] for s in stocks]
        rt_data = monitor.client.get_realtime_data(codes)
        
        for s in stocks:
            data = rt_data.get(s['code'], {'price': 0, 'change_pct': 0})
            s['price'] = data['price']
            s['change_pct'] = data['change_pct']
            
        return stocks
    finally:
        cursor.close()
        mydb.close()

@app.post("/api/stocks")
async def add_stock(stock: dict):
    input_str = stock.get('code', '').strip()
    if not input_str:
        return {"status": "error", "message": "Input is required"}
    
    # 使用 QMTClient 解析代码和名称
    resolved = monitor.client.resolve_stock_code(input_str)
    if not resolved:
        return {"status": "error", "message": f"无法识别股票: {input_str}"}
    
    code = resolved['code']
    name = resolved['name']
    
    mydb, cursor = connect_to_db()
    if not mydb:
        return {"status": "error", "message": "DB connection failed"}
    try:
        cursor.execute("INSERT INTO monitored_stocks (code, name) VALUES (%s, %s)", (code, name))
        mydb.commit()
        return {"status": "success", "data": resolved}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        mydb.close()

@app.delete("/api/stocks/{code}")
async def delete_stock(code: str):
    mydb, cursor = connect_to_db()
    if not mydb:
        return {"status": "error", "message": "DB connection failed"}
    try:
        cursor.execute("DELETE FROM monitored_stocks WHERE code = %s", (code,))
        mydb.commit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        mydb.close()

@app.get("/api/signals")
async def get_signals():
    mydb, cursor = connect_to_db()
    if not mydb:
        return []
    try:
        # 关联监控表以获取名称
        cursor.execute("""
            SELECT s.*, m.name 
            FROM signal_history s
            LEFT JOIN monitored_stocks m ON s.stock_code = m.code 
            ORDER BY s.timestamp DESC 
            LIMIT 100
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        mydb.close()

@app.get("/api/status")
async def get_status():
    return {
        "status": monitor.status,
        "last_scan_time": monitor.last_scan_time,
        "stock_count": len(monitor.get_monitored_stocks())
    }

@app.post("/api/monitor/start")
async def start_monitor():
    monitor.start()
    return {"status": "success"}

@app.post("/api/monitor/stop")
async def stop_monitor():
    monitor.stop()
    return {"status": "success"}

@app.get("/")
async def get():
    template_path = os.path.join(BASE_DIR, "src", "web", "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，监听可能的客户端消息（虽然目前不需要）
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    # 启动背景广播任务
    asyncio.create_task(alert_broadcaster())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
