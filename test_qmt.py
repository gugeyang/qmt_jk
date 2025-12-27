import sys
import os
import yaml
import time

def test_qmt():
    # Load config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    qmt_path = config['qmt']['path']
    print(f"QMT 路径: {qmt_path}")
    
    # 设置环境变量
    os.environ['QMT_USE'] = '1'
    os.environ['QMT_XTQUANT_PATH'] = qmt_path
    xtquant_lib = os.path.join(qmt_path, 'Lib', 'site-packages')
    if xtquant_lib not in sys.path:
        sys.path.insert(0, xtquant_lib)
    
    try:
        from xtquant import xtdata
        print("成功导入 xtdata 模块")
        
        # 尝试获取一些常用股票的数据
        stocks = ['000001.SZ', '600036.SH']
        print(f"正在获取 {stocks} 的全量快照行情...")
        ticks = xtdata.get_full_tick(stocks)
        print(f"获取到的行情 key: {list(ticks.keys())}")
        
        if not ticks:
            print("未直接获取到行情。正在尝试订阅...")
            for stock in stocks:
                xtdata.subscribe_quote(stock)
            
            print("等待 3 秒钟以便数据同步...")
            time.sleep(3)
            ticks = xtdata.get_full_tick(stocks)
            print(f"订阅后的行情 key: {list(ticks.keys())}")
        
        if ticks:
            for stock, data in ticks.items():
                print(f"股票 {stock} 数据: {data}")
                price = data.get('lastPrice')
                last_close = data.get('lastClose')
                print(f"  现价: {price}, 昨收: {last_close}")
        else:
            print("依然没有数据。请确认 MiniQMT 是否正在运行并已登录。")
            
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    test_qmt()
