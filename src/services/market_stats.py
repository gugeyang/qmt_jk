import time
from datetime import datetime
from typing import Dict, List
import pandas as pd

class MarketStatsService:
    def __init__(self, qmt_client):
        self.client = qmt_client
        self.last_stats = {}
        # 板块定义
        self.sectors = {
            'ALL': '沪深京A股',
            'SH': '上证A股',
            'SZ': '深证A股',
            'CYB': '创业板',
            'KCB': '科创板',
            'BJ': '北证A股'
        }
        # 指数定义：代码 -> {名称, 板块}
        self.indices = {
            '000001.SH': {'name': '上证指数', 'sector': 'SH'},
            '399001.SZ': {'name': '深证成指', 'sector': 'SZ'},
            '399006.SZ': {'name': '创业板指', 'sector': 'CYB'},
            '000688.SH': {'name': '科创50', 'sector': 'KCB'},
            '899050.BJ': {'name': '北证50', 'sector': 'BJ'}
        }
        # 内部状态记录
        self._market_subscribed = False
        self._indices_subscribed = set()
        self._sector_cache = {} # 缓存各板块股票列表

    def update_stats(self):
        """核心统计逻辑，每15秒调用一次"""
        try:
            results = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'distribution': {
                    'up_limit': 0, 'up_7_10': 0, 'up_5_7': 0, 'up_2_5': 0, 'up_0_2': 0,
                    'zero': 0,
                    'down_0_2': 0, 'down_2_5': 0, 'down_5_7': 0, 'down_7_10': 0, 'down_limit': 0
                },
                'counts': {'up': 0, 'down': 0, 'flat': 0},
                'leading': [] # 存储各大指数的对比与信号
            }

            # 1. 获取全市场快照 (使用缓存降低频率)
            if 'ALL' not in self._sector_cache:
                self._sector_cache['ALL'] = self.client.xt_data.get_stock_list_in_sector(self.sectors['ALL'])
            
            all_stocks = self._sector_cache['ALL']
            if not all_stocks:
                return self.last_stats

            if not self._market_subscribed:
                self.client.xt_data.subscribe_whole_quote(['SH', 'SZ', 'BJ'])
                self._market_subscribed = True
                
            ticks = self.client.xt_data.get_full_tick(all_stocks)
            
            # 2. 统计分布
            for code, tick in ticks.items():
                pre_close = tick.get('lastClose', 0)
                price = tick.get('lastPrice', 0)
                if pre_close <= 0 or price <= 0: continue
                change_pct = (price - pre_close) / pre_close * 100
                if change_pct > 0.01: results['counts']['up'] += 1
                elif change_pct < -0.01: results['counts']['down'] += 1
                else: results['counts']['flat'] += 1
                
                if change_pct >= 9.9: results['distribution']['up_limit'] += 1
                elif change_pct >= 7: results['distribution']['up_7_10'] += 1
                elif change_pct >= 5: results['distribution']['up_5_7'] += 1
                elif change_pct >= 2: results['distribution']['up_2_5'] += 1
                elif change_pct > 0: results['distribution']['up_0_2'] += 1
                elif change_pct == 0: results['distribution']['zero'] += 1
                elif change_pct > -2: results['distribution']['down_0_2'] += 1
                elif change_pct > -5: results['distribution']['down_2_5'] += 1
                elif change_pct > -7: results['distribution']['down_5_7'] += 1
                elif change_pct > -9.9: results['distribution']['down_7_10'] += 1
                else: results['distribution']['down_limit'] += 1

            # 3. 计算多指数领先对比与信号
            from src.indicators.td_sequential import calculate_td_sequential
            from src.indicators.divergence import detect_divergence
            
            for idx_code, info in self.indices.items():
                s_key = info['sector']
                if s_key not in self._sector_cache:
                    self._sector_cache[s_key] = self.client.xt_data.get_stock_list_in_sector(self.sectors[s_key])
                
                sector_stocks = self._sector_cache[s_key]
                # 优化：直接在全量 ticks 中迭代计算，不构建中间子字典副本以节约内存
                total_change = 0
                valid_count = 0
                for s_code in sector_stocks:
                    if s_code in ticks:
                        t = ticks[s_code]
                        pc = t.get('lastClose', 0)
                        lp = t.get('lastPrice', 0)
                        if pc > 0 and lp > 0:
                            total_change += (lp - pc) / pc
                            valid_count += 1
                
                if valid_count > 0:
                        avg_chg = total_change / valid_count
                        idx_detail = self.client.xt_data.get_instrument_detail(idx_code)
                        
                        if idx_code not in self._indices_subscribed:
                            self.client.xt_data.subscribe_quote(idx_code)
                            self._indices_subscribed.add(idx_code)
                            
                        idx_ticks = self.client.xt_data.get_full_tick([idx_code])
                        
                        if idx_detail and idx_code in idx_ticks:
                            pre_close_idx = idx_detail['PreClose']
                            white_price = idx_ticks[idx_code]['lastPrice']
                            yellow_price = pre_close_idx * (1 + avg_chg)
                            
                            # 指数信号探测 (探测 1m, 5m 两个主要活跃周期)
                            idx_signals = []
                            for tf in ['1m', '5m']:
                                df = self.client.get_kline(idx_code, tf)
                                if not df.empty and len(df) >= 13:
                                    # 改用全量数据，确时信号实时展现（即使未完全收盘也提示）
                                    td = calculate_td_sequential(df)
                                    div = detect_divergence(df)
                                    if td['buy_9']: idx_signals.append(f"{tf}低9")
                                    if td['sell_9']: idx_signals.append(f"{tf}高9")
                                    if div['bull_div']: idx_signals.append(f"{tf}底背离")
                                    if div['bear_div']: idx_signals.append(f"{tf}顶背离")
                            
                            if idx_signals:
                                print(f"【指数信号探测】{info['name']} ({idx_code}): {idx_signals}")

                            results['leading'].append({
                                'name': info['name'],
                                'white': round(white_price, 2),
                                'yellow': round(yellow_price, 2),
                                'diff_pct': round((yellow_price - white_price) / white_price * 100, 2), # 改为 (黄-白)/白
                                'dir': 'up' if yellow_price > white_price else 'down',
                                'signals': idx_signals
                            })

            self.last_stats = results
            # 显式清理大型变量，帮助 GC 及时回收
            del ticks
            return results
        except Exception as e:
            print(f"统计全市场数据异常: {e}")
            import traceback
            traceback.print_exc()
            return self.last_stats
