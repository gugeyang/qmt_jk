import sys
import os
import yaml
import time

# 加载配置
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

qmt_path = config['qmt']['path']
xtquant_lib = os.path.join(qmt_path, 'Lib', 'site-packages')
sys.path.insert(0, xtquant_lib)

from xtquant import xtdata

def test_leading_index_simulation():
    print("\n--- 正在为您模拟计算‘领先指数（黄线）’ ---")
    
    index_code = '000001.SH'
    detail = xtdata.get_instrument_detail(index_code)
    if not detail:
        print("获取指数信息失败")
        return
        
    last_close = detail['PreClose']
    index_name = detail['InstrumentName']
    
    # 1. 获取所有上证 A 股代码
    sector_name = '上证A股'
    stock_list = xtdata.get_stock_list_in_sector(sector_name)
    if not stock_list:
        print(f"获取 {sector_name} 列表失败")
        return
        
    print(f"正在分析 {sector_name} 的 {len(stock_list)} 只成分股报价...")
    
    # 2. 批量获取行情快照
    ticks = xtdata.get_full_tick(stock_list)
    
    total_change = 0
    valid_count = 0
    up_count = 0
    down_count = 0
    
    for code, tick in ticks.items():
        pre_close = tick.get('lastClose', 0)
        price = tick.get('lastPrice', 0)
        
        if pre_close > 0 and price > 0:
            change_pct = (price - pre_close) / pre_close
            total_change += change_pct
            valid_count += 1
            if change_pct > 0: up_count += 1
            elif change_pct < 0: down_count += 1
            
    if valid_count > 0:
        avg_change = total_change / valid_count
        # 领先指数公式：昨收 * (1 + 平均涨幅)
        leading_price = last_close * (1 + avg_change)
        
        # 获取当前加权价（白线）
        index_tick = xtdata.get_full_tick([index_code])
        white_price = index_tick[index_code]['lastPrice'] if index_code in index_tick else 0
        
        print(f"\n【实时对比结果】")
        print(f"指数名称: {index_name} ({index_code})")
        print(f"白线（最新加权）: {white_price:.2f}")
        print(f"黄线（模拟领先）: {leading_price:.2f}  <-- 基于 {valid_count} 只个股等权计算")
        print(f"市场冷热: 涨 {up_count} / 跌 {down_count}")
        print(f"当前背离: {white_price - leading_price:.2f} 点")
    else:
        print("无有效数据进行计算")

if __name__ == "__main__":
    test_leading_index_simulation()
