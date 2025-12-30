<?php
/**
 * QMT 股票监控系统 - 极简 PHP 展示端 (宝塔专供版)
 * 只要把此文件和 config.yaml 放在一起即可使用。
 */

/*
// --- 1. 访问安全保护 ---
session_start();
define('VIEW_PASSWORD', 'admin888'); // [请修改此密码] 访问网页时需要输入的密码

if (isset($_GET['logout'])) {
    session_destroy();
    header("Location: ?");
    exit;
}

if (!isset($_SESSION['auth']) || $_SESSION['auth'] !== true) {
    if (isset($_POST['password']) && $_POST['password'] === VIEW_PASSWORD) {
        $_SESSION['auth'] = true;
    } else {
        // 显示一个简单的登录界面
        die('
        <div style="text-align:center;margin-top:100px;font-family:sans-serif;">
            <h2>QMT 远程监控节点</h2>
            <form method="POST">
                <input type="password" name="password" placeholder="请输入访问密码" style="padding:10px;border-radius:4px;border:1px solid #ccc;">
                <button type="submit" style="padding:10px 20px;background:#00adb5;color:white;border:none;border-radius:4px;cursor:pointer;">进入系统</button>
            </form>
            ' . (isset($_POST['password']) ? '<p style="color:red;">密码错误</p>' : '') . '
        </div>');
    }
}
*/

// --- 2. 配置加载与数据库连接 ---
$config_path = __DIR__ . '/config.yaml';

// 默认配置
$db_config = [
    'host' => '127.0.0.1',
    'port' => 3306,
    'user' => 'qmt_db',
    'pass' => '',
    'name' => 'qmt_db'
];

// 自动从 config.yaml 提取 (精准区域识别)
if (file_exists($config_path)) {
    $content = file_get_contents($config_path);

    // 1. 先锁定 database 这一整块内容 (从 database: 开始到下一个顶行 key 结束)
    if (preg_match('/^database:.*?(?=^\S+:|\z)/ms', $content, $section)) {
        $db_block = $section[0];
        // 2. 在锁定的区域内寻找字段
        if (preg_match('/^\s+host:\s*([^\r\n]+)/m', $db_block, $m))
            $db_config['host'] = trim($m[1]);
        if (preg_match('/^\s+port:\s*([^\r\n]+)/m', $db_block, $m))
            $db_config['port'] = trim($m[1]);
        if (preg_match('/^\s+user:\s*([^\r\n]+)/m', $db_block, $m))
            $db_config['user'] = trim($m[1]);
        if (preg_match('/^\s+password:\s*([^\r\n]+)/m', $db_block, $m))
            $db_config['pass'] = trim($m[1]);
        if (preg_match('/^\s+database:\s*([^\r\n]+)/m', $db_block, $m))
            $db_config['name'] = trim($m[1]);
    }
}

// 如果自动提取还是失败，您可以在这里手动写死测试：
// $db_config['host'] = '127.0.0.1'; 
// $db_config['pass'] = '您的真实密码';

try {
    // 检查端口是否包含非数字字符 (处理类似 3306 #注释 的情况)
    $port = preg_replace('/[^0-9]/', '', $db_config['port']);
    $dsn = "mysql:host={$db_config['host']};port={$port};dbname={$db_config['name']};charset=utf8mb4";
    $pdo = new PDO($dsn, $db_config['user'], $db_config['pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (Exception $e) {
    echo "<div style='background:#fee;color:#c00;padding:20px;border:1px solid #c00;'>";
    echo "<h3>数据库连接失败</h3>";
    echo "<p>当前尝试连接的参数：</p>";
    echo "<ul><li>Host: {$db_config['host']}</li><li>DB Name: {$db_config['name']}</li><li>User: {$db_config['user']}</li></ul>";
    echo "<p>错误详情: " . $e->getMessage() . "</p>";
    echo "<p>提示：请检查 config.yaml 中数据库密码是否正确，且缩进是否规范。</p>";
    echo "</div>";
    exit;
}

// --- 2. 处理 AJAX 请求 ---
$action = $_GET['action'] ?? '';

if ($action === 'get_stocks') {
    $stmt = $pdo->query("SELECT * FROM monitored_stocks ORDER BY added_at DESC");
    echo json_encode($stmt->fetchAll());
    exit;
}

if ($action === 'get_signals') {
    $stmt = $pdo->query("SELECT s.*, m.name FROM signal_history s LEFT JOIN monitored_stocks m ON s.stock_code = m.code ORDER BY s.timestamp DESC LIMIT 100");
    echo json_encode($stmt->fetchAll());
    exit;
}

if ($action === 'sync_new') {
    $last_id = (int) ($_GET['last_id'] ?? 0);
    $stmt = $pdo->prepare("SELECT s.*, m.name FROM signal_history s LEFT JOIN monitored_stocks m ON s.stock_code = m.code WHERE s.id > ? ORDER BY s.id ASC");
    $stmt->execute([$last_id]);
    echo json_encode($stmt->fetchAll());
    exit;
}

// --- 3. HTML 页面内容 ---
?>
<!DOCTYPE html>
<html lang="zh-CN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>QMT 监控展示端 (PHP版)</title>
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1e1e1e;
            --text-color: #ffffff;
            --text-secondary: #aaaaaa;
            --accent-color: #00adb5;
            --buy-color: #ff5252;
            --sell-color: #4caf50;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 12px;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            max-width: 600px;
            margin: 0 auto;
        }

        header {
            margin-bottom: 20px;
            border-bottom: 1px solid #333;
            padding-bottom: 15px;
        }

        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .header-title {
            font-size: 24px;
            font-weight: bold;
            margin: 0;
            line-height: 1.2;
        }

        .status-badge {
            text-align: right;
            font-size: 12px;
        }

        .status-dot {
            color: #4caf50;
            display: block;
            margin-bottom: 2px;
        }

        .divider {
            height: 2px;
            background: var(--accent-color);
            width: 80px;
            margin-top: 10px;
        }

        .note-card {
            background: #252526;
            border-left: 4px solid #444;
            padding: 12px;
            font-size: 13px;
            color: var(--text-secondary);
            border-radius: 4px;
            margin-bottom: 20px;
            line-height: 1.5;
        }

        .section-title {
            font-size: 18px;
            font-weight: bold;
            margin: 20px 0 15px 0;
        }

        /* 列表式响应表格 */
        .list-card {
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }

        .row {
            display: grid;
            grid-template-columns: 80px 1fr 40px 80px 60px;
            padding: 12px 4px;
            border-bottom: 1px solid #333;
            align-items: center;
            font-size: 14px;
        }

        .row:last-child {
            border-bottom: none;
        }

        .row-header {
            font-size: 12px;
            color: var(--accent-color);
            padding-bottom: 8px;
            border-bottom: 1px solid #444;
            font-weight: bold;
        }

        .cell-time {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.2;
        }

        .cell-stock {
            font-weight: 500;
        }

        .cell-stock span {
            display: block;
            font-size: 11px;
            color: var(--text-secondary);
        }

        .cell-period {
            text-align: center;
            color: var(--text-secondary);
        }

        .cell-signal {
            font-weight: bold;
            text-align: center;
            line-height: 1.2;
        }

        .cell-price {
            text-align: right;
            font-family: monospace;
        }

        #alert-toast {
            position: fixed;
            top: 15px;
            right: 15px;
            left: 15px;
            z-index: 1000;
        }

        .toast {
            background-color: var(--card-bg);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.8);
            border-left: 4px solid var(--accent-color);
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from {
                transform: translateY(-20px);
                opacity: 0;
            }

            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        /* 隐藏 PC 端不需要的部分 */
        .pc-only {
            display: none;
        }
    </style>
</head>

<body>
    <div class="container">
        <header>
            <div class="header-top">
                <div class="header-title">QMT 信号展示端<br>(PHP 远程版)</div>
                <div class="status-badge">
                    <span id="status" class="status-dot">● 远程连接已开启</span>
                    <span style="color: #666;">(轮询模式)</span><br>
                    <span style="color: #666;">数据源: Windows 采集端</span>
                </div>
            </div>
            <div class="divider"></div>
        </header>

        <div class="note-card">
            节点说明：此页面仅做展示，如需修改配置或添加股票，请在 Windows 本地端操作。
        </div>

        <div class="section-title">实时预警信号</div>
        <div class="list-card">
            <div class="row row-header">
                <div>时间</div>
                <div>股票</div>
                <div style="text-align:center">周期</div>
                <div style="text-align:center">信号类型</div>
                <div style="text-align:right">价格</div>
            </div>
            <div id="signal-list">
                <!-- 信号动态插入 -->
            </div>
        </div>

        <div class="section-title" style="font-size:15px; color:#888;">监控列表</div>
        <div class="list-card" style="margin-bottom: 40px; opacity: 0.7;">
            <div id="stock-list"></div>
        </div>
    </div>

    <div id="alert-toast"></div>
    <audio id="alert-sound" src="https://assets.mixkit.co/sfx/preview/mixkit-software-interface-start-2574.mp3"></audio>

    <script>
        let lastSignalId = 0;
        const signalList = document.getElementById('signal-list');
        const stockList = document.getElementById('stock-list');
        const alertToast = document.getElementById('alert-toast');
        const alertSound = document.getElementById('alert-sound');

        async function sync() {
            try {
                const res = await fetch(`?action=sync_new&last_id=${lastSignalId}`);
                const news = await res.json();
                news.forEach(sig => {
                    const isBuy = addSignalToRow(sig, true);
                    showToast(sig, isBuy);
                    alertSound.play();
                    if (parseInt(sig.id) > lastSignalId) lastSignalId = parseInt(sig.id);
                });
            } catch (e) { console.error("Sync error", e); }
        }

        async function init() {
            const sRes = await fetch('?action=get_stocks');
            const stocks = await sRes.json();
            stocks.forEach(s => {
                const div = document.createElement('div');
                div.className = 'row';
                div.style.gridTemplateColumns = '1fr 1fr';
                div.innerHTML = `<div>${s.name} (${s.code})</div><div style="text-align:right; font-size:12px; color:#666;">添加: ${s.added_at.split(' ')[0]}</div>`;
                stockList.appendChild(div);
            });

            const sigRes = await fetch('?action=get_signals');
            const signals = await sigRes.json();
            signals.forEach(sig => {
                addSignalToRow(sig, false);
                if (parseInt(sig.id) > lastSignalId) lastSignalId = parseInt(sig.id);
            });

            setInterval(sync, 3000);
        }

        function addSignalToRow(sig, isNew) {
            const row = document.createElement('div');
            row.className = 'row';

            // 颜色逻辑：买入/看多信号 -> 红色, 卖出/看空信号 -> 绿色
            const isBuy = /买|低|底|托盘|价量背离|BULL|BUY/.test(sig.signal_type);
            const isSell = /卖|高|顶|压盘|BEAR|SELL/.test(sig.signal_type);
            const color = isBuy ? '#ff4d4d' : (isSell ? '#2ecc71' : '#ff4d4d');

            // 格式化时间：分两行显示
            const timeParts = sig.timestamp.split(' ');
            const dateStr = timeParts[0];
            const timeStr = timeParts[1];

            row.innerHTML = `
                <div class="cell-time">${dateStr}<br>${timeStr}</div>
                <div class="cell-stock">${sig.name}<span>(${sig.stock_code})</span></div>
                <div class="cell-period">${sig.timeframe}</div>
                <div class="cell-signal" style="color: ${color}">${sig.signal_type.replace('MACD', 'MACD<br>').replace('TD', 'TD')}</div>
                <div class="cell-price">${sig.price}</div>
            `;

            if (isNew) {
                signalList.insertBefore(row, signalList.firstChild);
            } else {
                signalList.appendChild(row);
            }
            return isBuy;
        }

        function showToast(sig, isBuy) {
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.style.backgroundColor = isBuy ? '#d32f2f' : '#27ae60';
            toast.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 5px; font-size: 1.1em;">新信号提醒</div>
                <div>${sig.name} (${sig.timeframe}) - ${sig.signal_type}</div>
                <div style="font-size: 0.8em; margin-top: 8px; opacity: 0.7; text-align: right;">点击关闭</div>
            `;
            toast.onclick = () => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            };
            alertToast.appendChild(toast);
            // 取消自动消失，直到手动关闭
        }

        init();
    </script>
</body>

</html>