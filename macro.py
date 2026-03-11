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
    """智能时间控制中枢：分离 GitHub 定时调度与手动触发"""
    now = datetime.now(BJ_TZ)
    
    # 侦测是否为 GitHub 的定时调度触发 (schedule)
    is_scheduled_action = os.getenv('GITHUB_EVENT_NAME') == 'schedule'
    
    if not is_scheduled_action:
        print(f"[{now.strftime('%H:%M:%S')}] 侦测到【手动/本地触发】，解除时间锁，立即扫描盘面！")
        return

    target_time = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)
    
    if now > target_time:
        print(f"[{now.strftime('%H:%M:%S')}] 触发时间已过预定节点，直接拉取数据。")
        return

    sleep_seconds = (target_time - now).total_seconds()
    print(f"[{now.strftime('%H:%M:%S')}] 定时排队成功，系统休眠 {sleep_seconds:.0f} 秒，等待 {target_time.strftime('%H:%M:%S')} 唤醒...")
    time.sleep(sleep_seconds)

def fetch_data_with_retry(retries=3, delay=2):
    """网络容错装甲：应对海外 IP 间歇性被拦截"""
    for i in range(retries):
        try:
            print(f"[{datetime.now(BJ_TZ).strftime('%H:%M:%S')}] 尝试获取 A 股全市场切片数据 (第 {i+1} 次)...")
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                return df
        except Exception as e:
            print(f"[{datetime.now(BJ_TZ).strftime('%H:%M:%S')}] 数据获取异常: {e}")
        time.sleep(delay)
    return pd.DataFrame() # 重试彻底失败返回空表

def get_market_data_and_filter():
    """拉取全市场数据并进行双层梯队筛选"""
    df_spot = fetch_data_with_retry()
    
    if df_spot.empty:
        print("致命错误：无法获取行情数据。")
        return pd.DataFrame(), pd.DataFrame()
    
    # 基础过滤：剔除ST、北交所、科创板、老三板
    df_spot = df_spot[~df_spot['名称'].str.contains('ST')]
    df_spot = df_spot[~df_spot['代码'].str.startswith(('8', '688', '4'))]
    
    print(f"[{datetime.now(BJ_TZ).strftime('%H:%M:%S')}] 基础过滤完成，划分战略梯队...")

    # 第一梯队：核心狙击目标（涨幅 3% - 5%，换手率 >= 5%）
    strict_targets = df_spot[
        (df_spot['涨跌幅'] >= 3.0) & 
        (df_spot['涨跌幅'] <= 5.0) & 
        (df_spot['换手率'] >= 5.0)
    ].copy()
    
    # 第二梯队：高优先备选（涨幅 1.5% - 5%，换手率 >= 4%），且剔除已在第一梯队的
    near_miss_targets = df_spot[
        (df_spot['涨跌幅'] >= 1.5) & 
        (df_spot['涨跌幅'] <= 5.0) & 
        (df_spot['换手率'] >= 4.0) &
        (~df_spot['代码'].isin(strict_targets['代码'] if not strict_targets.empty else []))
    ].copy()

    return strict_targets, near_miss_targets

def push_results(strict_df, near_miss_df, is_error=False):
    """HTML 格式化与推送模块"""
    url = "http://www.pushplus.plus/send"
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    
    if is_error:
        html_content = f"<h3>⚠️ 尾盘监控异常</h3><p>API获取数据彻底失败或网络断开，建议手动查看盘面。</p>"
    else:
        # 基础 CSS
        html_content = f"""
        <html>
        <head>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}
            .container {{ padding: 10px; }}
            .title {{ font-size: 20px; font-weight: bold; text-align: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
            .section-title {{ font-size: 16px; font-weight: bold; margin-top: 15px; padding: 5px; }}
            .title-strict {{ background-color: #ffebee; color: #c62828; border-left: 4px solid #c62828; }}
            .title-near {{ background-color: #e3f2fd; color: #1565c0; border-left: 4px solid #1565c0; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 10px; }}
            th, td {{ padding: 8px 4px; text-align: center; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f5f5f5; }}
            .red-text {{ color: #e53935; font-weight: bold; }}
            .tips {{ font-size: 12px; color: #888; background-color: #f9f9f9; padding: 10px; margin-top: 20px; }}
        </style>
        </head>
        <body>
        <div class="container">
            <div class="title">🎯 尾盘少妇战法 14:40 狙击指令</div>
        """

        # 第一梯队
        html_content += '<div class="section-title title-strict">🔥 核心狙击目标 (完全达标)</div>'
        if strict_df.empty:
            html_content += '<p style="text-align: center; color: #888;">当前无完全符合标准的标的（空仓）。</p>'
        else:
            strict_df = strict_df.sort_values(by='换手率', ascending=False).head(10)
            html_content += '<table><tr><th>代码</th><th>名称</th><th>涨幅</th><th>换手率</th></tr>'
            for _, row in strict_df.iterrows():
                html_content += f"<tr><td>{row['代码']}</td><td><b>{row['名称']}</b></td><td class='red-text'>+{row['涨跌幅']}%</td><td>{row['换手率']}%</td></tr>"
            html_content += '</table>'

        # 第二梯队
        html_content += '<div class="section-title title-near">⚡ 高优先备选队列 (蓄势待发)</div>'
        if near_miss_df.empty:
            html_content += '<p style="text-align: center; color: #888;">当前无备选标的。</p>'
        else:
            near_miss_df = near_miss_df.sort_values(by='换手率', ascending=False).head(8)
            html_content += '<table><tr><th>代码</th><th>名称</th><th>涨幅</th><th>换手率</th></tr>'
            for _, row in near_miss_df.iterrows():
                html_content += f"<tr><td>{row['代码']}</td><td><b>{row['名称']}</b></td><td class='red-text'>+{row['涨跌幅']}%</td><td>{row['换手率']}%</td></tr>"
            html_content += '</table>'

        html_content += """
            <div class="tips">
                <b>风控纪律：</b><br>1. 14:45-14:55 确认承接力度。<br>2. 尾盘大盘跳水坚决放弃。<br>3. 备选队列仅做极轻仓试错。
            </div>
        </div></body></html>
        """

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": f"尾盘战法决策 - {date_str} {'异常' if is_error else '14:40'}",
        "content": html_content,
        "template": "html"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{now.strftime('%H:%M:%S')}] 推送成功！")
        else:
            print(f"推送失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"推送异常: {e}")

def main():
    # 智能休眠：14:40:02
    wait_for_market_time(14, 40, 2)
    
    strict_targets, near_miss_targets = get_market_data_and_filter()
    
    if strict_targets.empty and near_miss_targets.empty and get_market_data_and_filter.__code__.co_consts == ():
        # 这里判断如果是 API 彻底失效导致的数据全空
        push_results(pd.DataFrame(), pd.DataFrame(), is_error=True)
    else:
        # 即使选股为空，也会正常推送 HTML 格式的空仓提示
        push_results(strict_targets, near_miss_targets, is_error=False)

if __name__ == "__main__":
    main()