import os
import sys
import time
import pandas as pd
import yaml

def test_depth_data():
    # 1. 加载配置获取路径
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return

    # 获取 QMT 路径 (适配不同的键名)
    # 0. 环境诊断
    print(f"当前 Python 版本: {sys.version}")
    py_major = sys.version_info.major
    py_minor = sys.version_info.minor
    if py_major != 3 or py_minor > 11:
        print("【警告】QMT 官方目前主要适配 Python 3.7 - 3.11。")
        print(f"您当前使用的是 3.{py_minor}，可能会因为二进制兼容性问题导致导入失败。")
        print("建议使用 run.bat 中配置的 Python 3.9 环境运行此脚本。\n")

    # 1. 加载配置
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return

    # 获取 QMT 路径 (适配不同的键名)
    xtquant_path = config['qmt'].get('xtquant_path') or config['qmt'].get('path')
    if not xtquant_path:
        print("错误: 在 config.yaml 的 qmt 节中未找到 path 配置。")
        return

    # 2. 尝试寻找真正的 xtquant 所在位置
    search_paths = [
        xtquant_path,
        os.path.join(xtquant_path, 'Lib', 'site-packages'),
        os.path.join(os.path.dirname(xtquant_path), 'Lib', 'site-packages')
    ]
    
    found = False
    for p in search_paths:
        if os.path.exists(os.path.join(p, 'xtquant')):
            if p not in sys.path:
                sys.path.insert(0, p)
            print(f"找到库路径: {p}")
            found = True
            break
            
    if not found:
        print(f"【诊断】在以下路径均未发现 xtquant 文件夹:")
        for p in search_paths: print(f" - {p}")
        # 保底尝试添加用户定义的路径
        if base_path not in sys.path: sys.path.insert(0, base_path)
    
    # 延迟导入
    try:
        from xtquant import xtdata
        print("xtquant 库导入成功！")
    except ImportError as e:
        print(f"\n【导入失败原因】: {e}")
        print("-" * 30)
        print("当前 Python 查找路径 (sys.path):")
        for p in sys.path: print(f"  {p}")
        print("-" * 30)
        print("建议操作：")
        print(f"1. 确认 {base_path} 目录下是否存在 xtquant 文件夹（或在子目录 Lib/site-packages 下）。")
        print("2. 强烈建议改用 Python 3.9 运行：")
        print("   C:\\Users\\admin\\AppData\\Local\\Programs\\Python\\Python39\\python.exe test_depth.py")
        return
    
    # 2. 连接 QMT
    print(f"正在连接 QMT (路径: {xtquant_path})...")
    # 尝试连接，如果连接失败会报错
    try:
        # XTData 初始化
        pass 
    except:
        pass

    # 3. 订阅并获取数据
    # 测试一只活跃股，比如宁德时代
    test_stocks = ['600354.SH', '000019.SZ']
    
    print("正在订阅全市场行情...")
    xtdata.subscribe_whole_quote(test_stocks)
    time.sleep(2) # 等待数据同步
    
    print("\n" + "="*50)
    print("盘口数据获取测试")
    print("="*50)
    
    for stock in test_stocks:
        print(f"\n正在尝试获取 {stock} 的全量 Tick 数据...")
        data = xtdata.get_full_tick([stock])
        
        if not data or stock not in data:
            print(f"未能获取到 {stock} 的数据，请确保 QMT 已登录且包含该品种行情。")
            continue
            
        tick = data[stock]
        
        # 打印基础字段
        print(f"最新价: {tick.get('lastPrice')}")
        
        # 处理买卖盘
        # QMT 的 get_full_tick 返回的字典里 bidPrice/askPrice 通常是列表
        bid_prices = tick.get('bidPrice', [])
        bid_vols = tick.get('bidVol', [])
        ask_prices = tick.get('askPrice', [])
        ask_vols = tick.get('askVol', [])
        
        print("-" * 30)
        print(f"{'档位':<6} | {'卖价':<10} | {'卖量':<10}")
        # 卖盘从高到低排列
        for i in range(len(ask_prices)-1, -1, -1):
            print(f"卖{i+1:<4} | {ask_prices[i]:<10.2f} | {ask_vols[i]:<10.0f}")
            
        print("-" * 30)
        print(f"{'档位':<6} | {'买价':<10} | {'买量':<10}")
        # 买盘从高到低排列
        for i in range(len(bid_prices)):
            print(f"买{i+1:<4} | {bid_prices[i]:<10.2f} | {bid_vols[i]:<10.0f}")
            
        print("-" * 30)
        print(f"共发现 {len(bid_prices)} 档有效买单。")
        
    print("\n测试完成。")

if __name__ == "__main__":
    test_depth_data()
