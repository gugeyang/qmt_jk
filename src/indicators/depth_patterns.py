from typing import List, Dict

def detect_depth_patterns(
    tick_data: Dict, 
    target_numbers: List[int] = [777, 888, 999], 
    gap_ratio_threshold: float = 0.01,
    min_vol_threshold: float = 50.0
) -> List[Dict]:
    """
    1. 寻找特殊数字挂单
    2. 基于价差与成交放量识别盘口异动 (参数可调)
    """
    signals = []
    if not tick_data:
        return signals

    bid_vols = tick_data.get('bidVol', [])
    ask_vols = tick_data.get('askVol', [])
    bid_prices = tick_data.get('bidPrice', [])
    ask_prices = tick_data.get('askPrice', [])

    # --- A. 特殊数字检测 (保留) ---
    # 根据用户实战反馈：买一卖一变动过快噪音大，从二档(索引1)开始监控
    for i in range(1, len(bid_vols)):
        vol = bid_vols[i]
        if int(vol) in target_numbers:
            signals.append({'type': 'depth', 'desc': f'买{i+1}挂单{int(vol)}', 'side': '买', 'price': bid_prices[i]})
            
    for i in range(1, len(ask_vols)):
        vol = ask_vols[i]
        if int(vol) in target_numbers:
            signals.append({'type': 'depth', 'desc': f'卖{i+1}挂单{int(vol)}', 'side': '卖', 'price': ask_prices[i]})

    # --- B. 强力压单博弈 (Wall Detection) ---
    # 策略逻辑：卖盘有重兵压境 (挂单 > 平均5倍)，且价格与成交价形成断层，主力意图压价吸筹
    last_price = tick_data.get('lastPrice', 0)
    last_vol = tick_data.get('lastVol', 0)
    all_vols = bid_vols + ask_vols
    
    if last_price > 0 and all_vols and len(ask_prices) > 0:
        avg_vol = sum(all_vols) / len(all_vols)
        ask1 = ask_prices[0]
        gap_ratio = abs(ask1 - last_price) / last_price

        for i, vol in enumerate(ask_vols):
            # 满足三个条件：1.大单压盘(5倍均值) 2.价差明显(超过设定比例) 3.成交放量(相对于挂单均值有明显成交)
            if vol > avg_vol * 5 and gap_ratio > gap_ratio_threshold and last_vol > avg_vol * 0.5:
                signals.append({
                    'type': 'wall', 
                    'desc': f'强力压盘博弈(卖{i+1}档{int(vol)}手, 价差{gap_ratio*100:.1f}%)', 
                    'side': '卖', 
                    'price': ask_prices[i]
                })

    # --- C. 蓄势压跳检测 (Price-Quote Divergence) ---
    # 策略逻辑：成交价远低于卖一价 (>设定比例)，且底部成交异常活跃 (成交量 > 设定门槛)，拉升前兆
    if last_price > 0 and len(ask_prices) > 0:
        ask1 = ask_prices[0]
        gap_ratio = (ask1 - last_price) / last_price
        
        # 只要价差超过设定阈值 且最新一笔成交达到门槛，即视为具备端倪
        if gap_ratio > gap_ratio_threshold and last_vol > min_vol_threshold:
            signals.append({
                'type': 'divergence', 
                'desc': f'变盘蓄势(价差{gap_ratio*100:.1f}%, 底部放量{int(last_vol)}手)', 
                'side': '买', 
                'price': last_price
            })

    return signals
