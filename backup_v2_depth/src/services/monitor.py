import time
import threading
from datetime import datetime
import numpy as np
from typing import List, Dict
from src.data.qmt_client import QMTClient
from src.indicators.td_sequential import calculate_td_sequential
from src.indicators.divergence import detect_divergence
from src.indicators.depth_patterns import detect_depth_patterns
from src.data.database import connect_to_db

class MonitorService:
    def __init__(self, config_path: str, db_path: str):
        self.client = QMTClient(config_path)
        self.db_path = db_path
        self.config_path = config_path
        self.config = self.client.config
        self.running = False
        self.alerts = []
        self.last_scan_time = None
        self.status = "Stopped"

    def _save_signal(self, stock_code: str, timeframe: str, signal_type: str, price: float, bar_time: str):
        mydb, cursor = connect_to_db()
        if not mydb:
            return
            
        stock_name = ""
        try:
            # 周期内去重检查
            if timeframe == 'tick':
                # 盘口信号去重：同一只票同一个信号类型在 1 分钟内不重复报（防止 Tick 快速刷新导致的重复）
                check_sql = "SELECT id FROM signal_history WHERE stock_code=%s AND signal_type=%s AND timestamp > DATE_SUB(NOW(), INTERVAL 1 MINUTE)"
                cursor.execute(check_sql, (stock_code, signal_type))
            else:
                # K线信号去重：基于 K 线时间戳
                check_sql = "SELECT id FROM signal_history WHERE stock_code=%s AND timeframe=%s AND signal_type=%s AND bar_time=%s"
                cursor.execute(check_sql, (stock_code, timeframe, signal_type, bar_time))
            
            if cursor.fetchone():
                return
                
            # 获取股票名称
            cursor.execute("SELECT name FROM monitored_stocks WHERE code = %s", (stock_code,))
            res = cursor.fetchone()
            if res:
                stock_name = res['name']
                
            cursor.execute('''
                INSERT INTO signal_history (stock_code, timeframe, signal_type, price, bar_time)
                VALUES (%s, %s, %s, %s, %s)
            ''', (stock_code, timeframe, signal_type, price, bar_time))
            mydb.commit()
        except Exception as e:
            print(f"保存信号异常: {e}")
            return # 报错也不推送
        finally:
            cursor.close()
            mydb.close()
        
        alert = {
            'stock_code': stock_code,
            'name': stock_name,
            'timeframe': timeframe,
            'signal_type': signal_type,
            'price': float(price),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.alerts.append(alert)
        print(f"【新信号】: {alert}")

    def get_monitored_stocks(self) -> List[str]:
        mydb, cursor = connect_to_db()
        if not mydb:
            return []
        try:
            cursor.execute("SELECT code FROM monitored_stocks")
            rows = cursor.fetchall()
            return [row['code'] for row in rows]
        except Exception as e:
            print(f"获取股票列表异常: {e}")
            return []
        finally:
            cursor.close()
            mydb.close()

    def scan_stock(self, stock_code: str):
        timeframes = self.config['monitor']['timeframes']
        for tf in timeframes:
            try:
                df = self.client.get_kline(stock_code, tf)
                if df.empty:
                    continue
                
                # 获取当前最后一根 K 线的时间戳作为该周期的“指纹”
                # 注意：get_kline 已经做过 reset_index，时间戳现在在 'time' 列中
                raw_time = df['time'].iloc[-1]
                if isinstance(raw_time, (int, float, np.integer)):
                    ts = raw_time / 1000 if raw_time > 1e11 else raw_time
                    current_bar_time = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    current_bar_time = str(raw_time)
                
                # TD9
                td_signals = calculate_td_sequential(df)
                if td_signals['buy_9']:
                    self._save_signal(stock_code, tf, 'TD低9', df['close'].iloc[-1], current_bar_time)
                if td_signals['sell_9']:
                    self._save_signal(stock_code, tf, 'TD高9', df['close'].iloc[-1], current_bar_time)
                
                # Divergence
                div_signals = detect_divergence(df)
                if div_signals['bull_div']:
                    self._save_signal(stock_code, tf, 'MACD底背离', df['close'].iloc[-1], current_bar_time)
                if div_signals['bear_div']:
                    self._save_signal(stock_code, tf, 'MACD顶背离', df['close'].iloc[-1], current_bar_time)
            except Exception as e:
                print(f"扫描 {stock_code} {tf} 周期异常: {e}")
        
        # 扫描盘口异动 (Tick 级别)
        try:
            self._scan_depth_patterns(stock_code)
        except Exception as e:
            print(f"扫描 {stock_code} 盘口异常: {e}")

    def _scan_depth_patterns(self, stock_code: str):
        """扫描盘口特殊数字与失衡"""
        # 获取全量 Tick
        ticks = self.client.xt_data.get_full_tick([stock_code])
        if not ticks or stock_code not in ticks:
            return
            
        tick = ticks[stock_code]
        # 从配置中读取目标数字
        target_nums = self.config['monitor'].get('special_numbers', [777, 888, 999])
        
        patterns = detect_depth_patterns(tick, target_nums)
        for p in patterns:
            # 信号类型直接使用算法返回的描述 (如: 盘口-买1挂单777 或 多头强势)
            signal_type = p['desc']
            # 盘口信号使用当前时间作为标记
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 信号去重和保存
            self._save_signal(stock_code, 'tick', signal_type, p['price'], current_time)

    def run(self):
        self.running = True
        self.status = "Running"
        print("监控服务已启动...")
        while self.running:
            # 每轮扫描检查一次 running 状态
            if not self.running:
                break
                
            self.last_scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            stocks = self.get_monitored_stocks()
            if not stocks:
                print("未发现监控中的股票，等待中...")
                time.sleep(10)
                continue
                
            for stock in stocks:
                if not self.running: # 在循环内部也检查，提高响应速度
                    break
                try:
                    self.scan_stock(stock)
                except Exception as e:
                    print(f"扫描 {stock} 异常: {e}")
            
            # 这里的时延也要能被中断
            interval = self.config['monitor'].get('interval', 5)
            for _ in range(int(interval)):
                if not self.running: break
                time.sleep(1)

    def start(self):
        if self.running:
            return
        self.status = "Running"
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.status = "Stopped"
        print("监控服务已停止")

    def update_config(self, updates: dict):
        """更新配置并保存到磁盘"""
        import yaml
        
        # 1. 更新内存
        if 'interval' in updates:
            self.config['monitor']['interval'] = updates['interval']
            
        # 2. 持久化到磁盘
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
            
            if 'interval' in updates:
                if 'monitor' not in full_config:
                    full_config['monitor'] = {}
                full_config['monitor']['interval'] = updates['interval']
                
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(full_config, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
