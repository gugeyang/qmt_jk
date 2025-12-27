# QMT 股票实时监控系统

本项目是一个基于 FastAPI 和 QMT (xtquant) 的实时股票监控系统。它能够自动跟踪自选股，计算 TD Sequential (TD9) 和 MACD 顶底背离信号，并通过网页端进行实时预警。

## 功能特点

- **多周期监控**：支持 1m, 5m, 15m, 30m, 1h, 1d 等多种时间周期。
- **技术指标预警**：
  - **MACD 顶底背离**：基于 DEA 勾头确认的背离检测。
  - **TD Sequential (TD9)**：自动识别买入/卖出结构。
- **实时预警界面**：
  - 网页端实时推送信号（WebSocket 支持）。
  - 全中文化界面与信号显示。
  - 信号颜色提醒（底/低报警为红色，顶/高报警为绿色）。
  - 持久化气泡提醒，需手动点击关闭。
- **监控管理**：支持在线添加/删除股票，提供一键启动/停止监控功能。
- **数据库集成**：自动将预警信号保存至 MySQL 数据库，并在同一 K 线周期内自动去重。

## 快速开始

### 1. 环境准备
- Python 3.9+
- MySQL 数据库
- 迅投 MiniQMT 客户端（需保持登录状态）

### 2. 安装依赖
```bash
pip install fastapi uvicorn mysql-connector-python pandas numpy pyyaml websockets
```

### 3. 配置
修改项目根目录下的 `config.yaml`：
- 修改 `qmt.path` 为您的 MiniQMT bin.x64 路径。
- 修改 `database` 为您的 MySQL 连接信息。

### 4. 运行
```bash
python main.py
```
访问 `http://localhost:8000` 即可进入监控界面。

## 目录结构
- `src/data`: 数据采集与数据库管理。
- `src/indicators`: 技术指标算法。
- `src/services`: 监控逻辑。
- `src/web`: Web 接口与前端模板。

## 免责声明
本软件提供的信号仅供参考，不构成任何投资建议。股市有风险，入市需谨慎。
