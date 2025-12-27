import pandas as pd
import numpy as np
from typing import Dict

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
    close = df['close']
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    df['diff'] = ema_fast - ema_slow
    df['dea'] = df['diff'].ewm(span=signal, adjust=False).mean()
    df['macd'] = (df['diff'] - df['dea']) * 2
    return df

def detect_divergence(df: pd.DataFrame) -> Dict[str, bool]:
    """
    检测顶底背离 (基于 DEA 拐头)
    """
    if 'diff' not in df.columns:
        df = calculate_macd(df)
    
    # 辅助指标
    df['gj'] = df[['close', 'open']].max(axis=1)
    df['l4'] = df['gj'].rolling(window=4).min()
    df['h4'] = df['gj'].rolling(window=4).max()
    
    dea = df['dea']
    dea_shift1 = dea.shift(1)
    dea_shift2 = dea.shift(2)
    
    # DEA 拐头
    df['gt'] = (dea > dea_shift1) & (dea_shift1 < dea_shift2)  # 向上拐头
    df['gt2'] = (dea < dea_shift1) & (dea_shift1 > dea_shift2) # 向下拐头
    
    gt_indices = df[df['gt']].index.tolist()
    gt2_indices = df[df['gt2']].index.tolist()
    
    bull_div = False
    bear_div = False
    
    # 底背离 (Bullish)
    if len(gt_indices) >= 2:
        last_gt = gt_indices[-1]
        prev_gt = gt_indices[-2]
        if last_gt == df.index[-1] or last_gt == df.index[-2]: # 最近发生
            if df.loc[last_gt, 'close'] < df.loc[prev_gt, 'l4'] and \
               df.loc[last_gt, 'diff'] > df.loc[prev_gt, 'diff']:
                bull_div = True
                
    # 顶背离 (Bearish)
    if len(gt2_indices) >= 2:
        last_gt2 = gt2_indices[-1]
        prev_gt2 = gt2_indices[-2]
        if last_gt2 == df.index[-1] or last_gt2 == df.index[-2]: # 最近发生
            if df.loc[last_gt2, 'close'] > df.loc[prev_gt2, 'h4'] and \
               df.loc[last_gt2, 'diff'] < df.loc[prev_gt2, 'diff']:
                bear_div = True
                
    return {
        'bull_div': bull_div,
        'bear_div': bear_div
    }
