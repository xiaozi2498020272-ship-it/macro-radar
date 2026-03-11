import os
import time
import requests
import pandas as pd
import akshare as ak
from datetime import datetime, timezone, timedelta

# ================= 新增：免疫本地 VPN 代理干扰 =================
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'
# ===============================================================

# ================= 核心铁律配置区 =================
PUSHPLUS_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
BJ_TZ = timezone(timedelta(hours=8))
# ==================================================

# ...(下方的代码完全保持不变)
def wait_for_market_time(target_hour, target_minute, target_second):
    now = datetime.now(BJ_TZ)
    is_scheduled_action = os.getenv('GITHUB_EVENT_NAME') == 'schedule'
    
    if not is_scheduled_action:
        print(f"[{now.strftime('%H:%M:%S')}] 侦测到【手动/本地触发】，解除时间锁，立即扫描盘面！")
        return

    target_time = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)
    
    if now > target_time:
        print(f"[{now.strftime('%H:%M:%S')}] 触发时间已过预定节点，直接拉取数据。")
        return

    sleep_seconds = (target_time - now).total_seconds()
    print(f"[{now.strftime('%H:%M:%S')}] 排队成功，休眠 {sleep_seconds:.0f} 秒，等待 {target_time.strftime('%H:%M:%S')} 唤醒...")
    time.sleep(sleep_seconds)

def fetch_data_with_retry(retries=3, delay=2):
    for i in range(retries):
        try:
            print(f"[{datetime.now(BJ_TZ).strftime('%H:%M:%S')}] 获取早盘竞价切片 (第 {i+1} 次)...")
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                return df
        except Exception as e:
            print(f"获取异常: {e}")
        time.sleep(delay)
    return pd.DataFrame()

def get_qinlong_targets():
    df_spot = fetch_data_with_retry()
    if df_spot.empty:
        return pd.DataFrame(), True # 返回空表和错误标志
    
    # 1. 基础过滤
    df_spot = df_spot[~df_spot['名称'].str.contains('ST')]
    df_spot = df_spot[~df_spot['代码'].str.startswith(('8', '688', '4'))]
    
    # 将缺失值填充为0以防报错
    df_spot['流通市值'] = pd.to_numeric(df_spot['流通市值'], errors='coerce').fillna(0)
    df_spot['涨跌幅'] = pd.to_numeric(df_spot['涨跌幅'], errors='coerce').fillna(0)
    
    # 2. 游资擒龙因子过滤
    # 流通市值 10亿(1,000,000,000) - 150亿(15,000,000,000)
    # 早盘 09:25 的 '涨跌幅' 即为高开幅度：2% - 6% 弱转强确认
    targets = df_spot[
        (df_spot['流通市值'] >= 1_000_000_000) & 
        (df_spot['流通市值'] <= 15_000_000_000) & 
        (df_spot['涨跌幅'] >= 2.0) & 
        (df_spot['涨跌幅'] <= 6.0)
    ].copy()
    
    # 早盘换手率通常极低，若强行叠加 >= 5% 容易错过，这里保留排序展示
    targets = targets.sort_values(by='涨跌幅', ascending=False).head(15)
    return targets, False

def push_qinlong_results(df, is_error=False):
    url = "http://www.pushplus.plus/send"
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    
    if is_error:
        content = "<h3>🚨 早盘擒龙异常</h3><p>竞价数据获取失败，由于GitHub海外IP限制，建议空仓观察。</p>"
    elif df.empty:
        content = "<h3>🐉 早盘擒龙 09:25</h3><p>今日集合竞价无符合【10-150亿流通盘 + 高开2%-6%】弱转强标的。严格空仓。</p>"
    else:
        content = f"""
        <html><body>
        <h3 style='color:#c62828; text-align:center;'>🐉 早盘擒龙 09:25 弱转强</h3>
        <table style='width:100%; border-collapse:collapse; font-size:14px;'>
        <tr style='background-color:#f5f5f5;'><th>代码</th><th>名称</th><th>高开幅度</th><th>流通市值(亿)</th></tr>
        """
        for _, row in df.iterrows():
            market_cap_yi = round(row['流通市值'] / 100_000_000, 2)
            content += f"<tr><td style='text-align:center;'>{row['代码']}</td><td style='text-align:center;'><b>{row['名称']}</b></td><td style='color:#e53935; text-align:center;'>+{row['涨跌幅']}%</td><td style='text-align:center;'>{market_cap_yi}</td></tr>"
        content += "</table><p style='font-size:12px; color:#888; margin-top:15px;'>风控提示：高开须结合前几日涨停记录确认主力意图，谨防骗炮。</p></body></html>"

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": f"游资擒龙决策 - {date_str} {'异常' if is_error else '09:25'}",
        "content": content,
        "template": "html"
    }
    requests.post(url, json=payload)

def main():
    # 智能休眠：09:25:05 (集合竞价数据确立)
    wait_for_market_time(9, 25, 5)
    targets, is_error = get_qinlong_targets()
    push_qinlong_results(targets, is_error)

if __name__ == "__main__":
    main()