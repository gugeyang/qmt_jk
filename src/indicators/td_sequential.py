import pandas as pd
import numpy as np
from typing import Dict

def calculate_td_sequential(df: pd.DataFrame, price_col: str = 'close') -> Dict[str, bool]:
    """
    计算TD序列信号 (TD9)
    """
    if len(df) < 13:
        return {'buy_9': False, 'sell_9': False}
        
    close_prices = df[price_col].values
    n = len(close_prices)
    lookback = 4
    
    current_up_count = 0
    current_down_count = 0
    
    # 我们只关心最后一根K线的状态
    for i in range(lookback, n):
        if close_prices[i] > close_prices[i - lookback]:
            current_up_count += 1
            current_down_count = 0
        elif close_prices[i] < close_prices[i - lookback]:
            current_down_count += 1
            current_up_count = 0
        else:
            current_up_count = 0
            current_down_count = 0
            
    return {
        'buy_9': current_down_count == 9,
        'sell_9': current_up_count == 9
    }
