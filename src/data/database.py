import mysql.connector
import yaml
import os

def get_db_config():
    # 获取项目根目录下的 config.yaml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_path = os.path.join(project_root, 'config.yaml')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config['database']

def connect_to_db():
    try:
        config = get_db_config()
        conn = mysql.connector.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database=config['database']
        )
        cursor = conn.cursor(dictionary=True)
        
        # 自动初始化表结构
        _init_db_tables(conn, cursor)
        
        return conn, cursor
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None, None

def _init_db_tables(conn, cursor):
    """初始化数据库表及其结构"""
    try:
        # 1. 监控列表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitored_stocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(50),
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # 2. 信号历史
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10),
                signal_type VARCHAR(50),
                price DECIMAL(10, 2),
                bar_time DATETIME,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # 尝试为可能已经存在的旧表增加 bar_time 字段
        try:
            cursor.execute("SHOW COLUMNS FROM signal_history LIKE 'bar_time'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE signal_history ADD COLUMN bar_time DATETIME AFTER price")
                print("已为 signal_history 表增加 bar_time 字段")
        except:
            pass
            
        conn.commit()
    except Exception as e:
        print(f"初始化表结构失败: {e}")

def init_db():
    mydb, cursor = connect_to_db()
    if not mydb:
        return
    
    try:
        # 创建监控股票表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitored_stocks (
            code VARCHAR(20) PRIMARY KEY,
            name VARCHAR(50),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建信号历史表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20),
            timeframe VARCHAR(10),
            signal_type VARCHAR(20),
            price DECIMAL(10, 2),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        mydb.commit()
        print("MySQL Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        cursor.close()
        mydb.close()

if __name__ == "__main__":
    init_db()
