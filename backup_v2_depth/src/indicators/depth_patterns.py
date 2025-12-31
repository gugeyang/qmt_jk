def detect_depth_patterns(tick_data: Dict, target_numbers: List[int] = [777, 888, 999], big_order_threshold: float = 10.0) -> List[Dict]:
    """
    1. 寻找特殊数字挂单
    2. 检测买卖档位是否存在显著的失衡 (主力偏好)
    """
    signals = []
    if not tick_data:
        return signals

    bid_vols = tick_data.get('bidVol', [])
    ask_vols = tick_data.get('askVol', [])
    bid_prices = tick_data.get('bidPrice', [])
    ask_prices = tick_data.get('askPrice', [])

    # --- A. 特殊数字检测 ---
    for i, vol in enumerate(bid_vols):
        if int(vol) in target_numbers:
            signals.append({'type': 'depth', 'desc': f'买{i+1}挂单{int(vol)}', 'side': '买', 'price': bid_prices[i]})
    for i, vol in enumerate(ask_vols):
        if int(vol) in target_numbers:
            signals.append({'type': 'depth', 'desc': f'卖{i+1}挂单{int(vol)}', 'side': '卖', 'price': ask_prices[i]})

    # --- B. 买卖失衡检测 (Order Flow Imbalance) - 客观描述 ---
    sum_bid = sum(bid_vols)
    sum_ask = sum(ask_vols)
    if sum_ask > 0 and sum_bid > 0:
        ratio = sum_bid / sum_ask
        if ratio > 3.0:
            signals.append({'type': 'imbalance', 'desc': f'买盘显著聚集(托盘 {ratio:.1f}倍)', 'side': '买', 'price': bid_prices[0]})
        elif ratio < 0.33:
            signals.append({'type': 'imbalance', 'desc': f'卖盘显著压力(压盘 {1/ratio:.1f}倍)', 'side': '卖', 'price': ask_prices[0]})

    # --- C. 单档异常大单检测 (Single Level Wall) ---
    all_vols = bid_vols + ask_vols
    if all_vols:
        avg_vol = sum(all_vols) / len(all_vols)
        for i, vol in enumerate(bid_vols):
            if vol > avg_vol * 5 and vol > 100:
                signals.append({'type': 'wall', 'desc': f'买{i+1}档显著巨单({int(vol)}手)', 'side': '买', 'price': bid_prices[i]})
        for i, vol in enumerate(ask_vols):
            if vol > avg_vol * 5 and vol > 100:
                signals.append({'type': 'wall', 'desc': f'卖{i+1}档显著巨单({int(vol)}手)', 'side': '卖', 'price': ask_prices[i]})

    # --- D. 成交价/卖一背离检测 (Price-Ask Divergence) ---
    last_price = tick_data.get('lastPrice', 0)
    if last_price > 0 and len(ask_prices) > 0:
        ask1 = ask_prices[0]
        # 计算背离比例：(卖一 - 成交价) / 成交价
        gap_ratio = (ask1 - last_price) / last_price
        if gap_ratio > 0.015: # 差价超过 1.5% 认为存在显著背离
            signals.append({
                'type': 'divergence', 
                'desc': f'价量背离(成交{last_price}/卖一{ask1}, 差{gap_ratio*100:.1f}%)', 
                'side': '买', # 暗示可能是拉升前的蓄势
                'price': last_price
            })

    return signals
