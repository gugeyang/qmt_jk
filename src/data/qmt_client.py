import sys
import os
import pandas as pd
import yaml
from typing import List, Dict, Optional

class QMTClient:
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.qmt_path = self.config['qmt']['path']
        self.xt_data = None
        self._connect()

    def _connect(self):
        try:
            # 设置环境变量
            os.environ['QMT_USE'] = '1'
            os.environ['QMT_XTQUANT_PATH'] = self.qmt_path
            
            # 添加 xtquant 路径
            xtquant_lib = os.path.join(self.qmt_path, 'Lib', 'site-packages')
            if xtquant_lib not in sys.path:
                sys.path.insert(0, xtquant_lib)
            
            from xtquant import xtdata
            self.xt_data = xtdata
            print("成功连接到 QMT (xtquant)")
        except Exception as e:
            print(f"连接 QMT 失败: {e}")

    def get_kline(self, stock_code: str, period: str, count: int = 200) -> pd.DataFrame:
        if not self.xt_data:
            return pd.DataFrame()
            
        # 预检合法周期，防止底层报错刷屏
        valid_periods = ['tick', '1m', '5m', '15m', '30m', '1h', '1d', '1w', '1mon', '1q', '1hy', '1y']
        if period not in valid_periods:
            print(f"警告: 周期 '{period}' 不受 QMT 官方支持，已跳过。请使用: {', '.join(valid_periods)}")
            return pd.DataFrame()
        
        try:
            # 统一转为大写，防止大小写错误导致获取失败
            stock_code = stock_code.upper()
            
            # 根据周期智能计算下载深度，确保足够的技术指标计算数据
            from datetime import datetime, timedelta
            now = datetime.now()
            if period.endswith('m') or period == '1h':
                days = 30  # 分钟线下载最近 30 天足以满足 200 根
            elif period == '1d':
                days = 365 * 2 # 日线下载 2 年
            elif period == '1w':
                days = 365 * 10 # 周线下载 10 年
            elif period == '1mon':
                days = 365 * 20 # 月线下载 20 年
            else:
                days = 5
                
            start_date = (now - timedelta(days=days)).strftime('%Y%m%d')
            # 开启异步下载模式，QMT 内部会处理增量
            self.xt_data.download_history_data(stock_code, period, start_date)
            
            # 获取市场数据
            data = self.xt_data.get_market_data(
                field_list=['open', 'high', 'low', 'close', 'volume'],
                stock_list=[stock_code],
                period=period,
                count=count
            )
            
            if not data or not isinstance(data, dict):
                print(f"未能获取到 {stock_code} 的市场数据")
                return pd.DataFrame()
            
            # 格式转换 (QMT 返回的是 {field: DataFrame})
            # DataFrame 的 Index 是时间戳，Columns 是股票代码
            result_data = {}
            for field in ['open', 'high', 'low', 'close', 'volume']:
                if field in data:
                    field_df = data[field]
                    
                    # 某些版本的 QMT 可能直接返回 Series 或数组，这里做健壮性处理
                    if isinstance(field_df, pd.DataFrame):
                        if stock_code in field_df.columns:
                            result_data[field] = field_df[stock_code]
                        elif stock_code in field_df.index: 
                            result_data[field] = field_df.loc[stock_code]
                    elif hasattr(field_df, '__getitem__') and stock_code in field_df:
                        result_data[field] = field_df[stock_code]
            
            if not result_data:
                # 尝试查找有没有类似的代码（比如大小写混合的）
                available_cols = []
                for f in data.values():
                    if isinstance(f, pd.DataFrame):
                        available_cols.extend(f.columns.tolist())
                print(f"无法在返回数据中找到 {stock_code}。可用列: {list(set(available_cols))}")
                return pd.DataFrame()
                
            df = pd.DataFrame(result_data)
            # 处理时间索引
            if not df.empty:
                df.index.name = 'time'
                return df.reset_index()
            return pd.DataFrame()
        except Exception as e:
            print(f"获取 {stock_code} K线异常: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def subscribe(self, stock_list: List[str], callback=None):
        if not self.xt_data:
            return
        
        for stock in stock_list:
            self.xt_data.subscribe_quote(stock, period='tick', callback=callback)

    def resolve_stock_code(self, input_str: str) -> Optional[Dict]:
        """
        解析输入的代码或名称，返回标准代码和名称
        """
        if not self.xt_data:
            return None
            
        # 1. 如果输入已经是标准代码 (带后缀)
        if '.' in input_str:
            detail = self.xt_data.get_instrument_detail(input_str.upper())
            if detail:
                return {
                    'code': input_str.upper(),
                    'name': detail.get('InstrumentName', '')
                }
        
        # 2. 如果输入是纯数字 (尝试补全后缀)
        if input_str.isdigit():
            for suffix in ['.SH', '.SZ', '.BJ']:
                code = input_str + suffix
                detail = self.xt_data.get_instrument_detail(code)
                if detail:
                    return {
                        'code': code,
                        'name': detail.get('InstrumentName', '')
                    }
        
        # 3. 如果输入是名称 (尝试搜索)
        # 注意：xtquant 没有直接的名称搜索 API，通常需要遍历全市场或使用本地缓存
        # 这里简单处理：如果不是数字且不带点，尝试在全市场中匹配
        all_stocks = self.xt_data.get_stock_list_in_sector('沪深A股')
        for code in all_stocks:
            detail = self.xt_data.get_instrument_detail(code)
            if detail and detail.get('InstrumentName') == input_str:
                return {
                    'code': code,
                    'name': input_str
                }
                
        return None

    def get_realtime_data(self, stock_list: List[str]) -> Dict[str, Dict]:
        """
        获取实时价格和涨跌幅
        """
        if not self.xt_data:
            print("QMT 未连接，无法获取实时行情")
            return {}
            
        if not stock_list:
            return {}
            
        try:
            # 订阅行情确保有实时数据流
            for stock in stock_list:
                self.xt_data.subscribe_quote(stock, period='tick', count=-1)
            
            res = {}
            ticks = self.xt_data.get_full_tick(stock_list)
            
            if not ticks:
                print(f"未获取到股票行情快照: {stock_list}")
                return {}
                
            for stock in stock_list:
                if stock in ticks:
                    tick = ticks[stock]
                    # lastClose 通常是昨收盘价
                    last_close = tick.get('lastClose', 0)
                    # 如果 lastClose 为 0，尝试获取 preClose (某些版本可能用这个)
                    if last_close == 0:
                        last_close = tick.get('preClose', 0)
                        
                    price = tick.get('lastPrice', 0)
                    change_pct = 0
                    if last_close > 0:
                        change_pct = (price - last_close) / last_close * 100
                    
                    res[stock] = {
                        'price': round(price, 2),
                        'change_pct': round(change_pct, 2)
                    }
                else:
                    print(f"在返回数据中未找到股票 {stock}")
            return res
        except Exception as e:
            print(f"获取实时数据异常: {e}")
            return {}
