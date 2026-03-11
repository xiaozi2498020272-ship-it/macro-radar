import akshare as ak
import pandas as pd
import requests
import time
from datetime import datetime, timezone, timedelta

# ================= 配置区 =================
PUSHPLUS_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
BJ_TZ = timezone(timedelta(hours=8)) 

MIN_MARKET_CAP = 10_0000_0000     
MAX_MARKET_CAP = 150_0000_0000    
MIN_TURNOVER = 5.0                
GAP_UP_MIN = 2.0                  
GAP_UP_MAX = 6.0                  
# ==========================================

def fetch_data_with_retry(fetch_func, max_retries=3, delay=3, **kwargs):
    """网络请求容错装甲：应对 GitHub 海外节点被拦截的重试机制"""
    for i in range(max_retries):
        try:
            return fetch_func(**kwargs)
        except Exception as e:
            now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
            print(f"[{now_str}] 接口被拦截或超时，正在重试 ({i+1}/{max_retries})...")
            time.sleep(delay)
    print("多次强行请求东方财富接口失败，海外 IP 被彻底封锁。")
    return pd.DataFrame() # 所有重试失败，返回空数据框

def get_static_pool():
    """第一阶段：计算昨日符合游资审美的静态标的"""
    now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f"[{now_str}] 开始获取全市场基础数据，构建擒龙蓄水池...")
    
    # 启用装甲获取数据
    df_spot = fetch_data_with_retry(ak.stock_zh_a_spot_em)
    
    if df_spot.empty:
        return [] # 如果连全市场数据都拿不到，直接返回空池子
    
    df_spot = df_spot[~df_spot['名称'].str.contains('ST')]
    df_spot = df_spot[~df_spot['代码'].str.startswith(('8', '688', '4'))]
    
    df_filtered = df_spot[
        (df_spot['流通市值'] >= MIN_MARKET_CAP) & 
        (df_spot['流通市值'] <= MAX_MARKET_CAP) &
        (df_spot['换手率'] >= MIN_TURNOVER) 
    ].copy()

    target_stocks = []
    end_date = datetime.now(BJ_TZ).strftime("%Y%m%d")
    start_date = (datetime.now(BJ_TZ) - timedelta(days=10)).strftime("%Y%m%d")

    now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f"[{now_str}] 基础过滤剩余 {len(df_filtered)} 只，开始测算涨停基因...")
    
    for index, row in df_filtered.iterrows():
        code = row['代码']
        # 历史数据获取同样需要套上装甲
        hist_df = fetch_data_with_retry(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qq")
        
        if hist_df.empty or len(hist_df) < 5:
            continue
        
        limit_up_days = hist_df[hist_df['涨跌幅'] >= 9.5]
        if 1 <= len(limit_up_days) <= 3:
            target_stocks.append({
                "代码": code,
                "名称": row['名称'],
                "昨收": row['昨收']
            })
            
    now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f"[{now_str}] 静态蓄水池构建完成，共锁定 {len(target_stocks)} 只潜在标的。")
    return target_stocks

def get_auction_data_and_push(pool):
    """第二阶段：获取竞价结果并推送"""
    now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f"[{now_str}] 开始狙击 9:25 异动标的...")
    
    # 启用装甲拉取 9:25 的集合竞价切片
    df_spot_now = fetch_data_with_retry(ak.stock_zh_a_spot_em)
    final_targets = []
    
    if not df_spot_now.empty:
        for stock in pool:
            current_data = df_spot_now[df_spot_now['代码'] == stock['代码']]
            if current_data.empty:
                continue
                
            open_price = current_data['最新价'].values[0] 
            pre_close = stock['昨收']
            
            if pre_close > 0:
                gap_up_pct = (open_price - pre_close) / pre_close * 100
                if GAP_UP_MIN <= gap_up_pct <= GAP_UP_MAX:
                    final_targets.append({
                        "代码": stock['代码'],
                        "名称": stock['名称'],
                        "昨收": pre_close,
                        "竞价开盘": open_price,
                        "高开幅度": round(gap_up_pct, 2)
                    })

    date_str = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    url = "http://www.pushplus.plus/send"
    
    html_content = f"""
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ padding: 10px; }}
        .title {{ font-size: 20px; font-weight: bold; text-align: center; color: #1a1a1a; margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        .section-title {{ font-size: 16px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; padding: 5px 10px; border-radius: 4px; background-color: #ffebee; color: #c62828; border-left: 4px solid #c62828; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background-color: #f5f5f5; color: #555; font-weight: bold; padding: 10px 5px; text-align: center; border-bottom: 1px solid #ddd; }}
        td {{ padding: 10px 5px; text-align: center; border-bottom: 1px solid #eee; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        .red-text {{ color: #e53935; font-weight: bold; }}
        .tips {{ font-size: 12px; color: #888; background-color: #f9f9f9; padding: 10px; border-radius: 5px; margin-top: 20px; text-align: justify; }}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="title">🐉 游资擒龙 9:25 狙击指令</div>
    """

    if not final_targets:
        html_content += '<p style="text-align: center; color: #888; font-size: 14px;">今日竞价未发现符合标准标的，或海外服务器网络彻底瘫痪，建议空仓观望。</p>'
    else:
        final_targets = sorted(final_targets, key=lambda x: x['高开幅度'], reverse=True)
        html_content += '<div class="section-title">🔥 竞价弱转强名单 (2%~6%高开)</div>'
        html_content += '<table><tr><th>代码</th><th>名称</th><th>现价</th><th>高开幅度</th></tr>'
        for target in final_targets:
            html_content += f"""
            <tr>
                <td style="color: #666;">{target['代码']}</td>
                <td style="font-weight: bold;">{target['名称']}</td>
                <td>{target['竞价开盘']}</td>
                <td class="red-text">+{target['高开幅度']}%</td>
            </tr>
            """
        html_content += '</table>'

    html_content += """
        <div class="tips">
            <b>游资风控铁律：</b><br>
            1. 请在开盘 5 分钟内密切盯防资金承接力度。<br>
            2. 如果开盘后垂直向下砸破分时均线且不回头，<b>绝对放弃买入</b>！<br>
            3. 只买点火向上、分时图呈现“脉冲式”拉升的瞬间！
        </div>
    </div>
    </body>
    </html>
    """

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": f"擒龙早盘决策 - {date_str} 09:25",
        "content": html_content,
        "template": "html"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
        if response.status_code == 200:
            print(f"[{now_str}] 早盘竞价排版推送成功！请查收微信。")
        else:
            print(f"[{now_str}] 推送失败，PushPlus 状态码: {response.status_code}")
    except Exception as e:
        print(f"推送过程发生异常: {e}")

def main():
    now_str = datetime.now(BJ_TZ).strftime('%H:%M:%S')
    print(f"[{now_str}] 脚本启动，执行第一阶段静态筛选...")
    
    pool = get_static_pool()
    
    if not pool:
        print("未筛选出基础标的，发送空仓预警并结束程序。")
        requests.post("http://www.pushplus.plus/send", json={
            "token": PUSHPLUS_TOKEN,
            "title": "🐉 擒龙早盘 - 网络异常或空仓",
            "content": "今日基础过滤未筛选出标的，或由于 GitHub 海外 IP 被彻底拦截导致获取数据失败。建议空仓。"
        })
        return
        
    now = datetime.now(BJ_TZ)
    target_time = now.replace(hour=9, minute=25, second=5, microsecond=0)
    wait_seconds = (target_time - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"[{now.strftime('%H:%M:%S')}] 进入休眠，等待 9:25:05 竞价结束唤醒... (需等待 {int(wait_seconds)} 秒)")
        time.sleep(wait_seconds)
    else:
        print(f"[{now.strftime('%H:%M:%S')}] 当前时间已过 9:25:05，立即执行竞价拉取！")
        
    get_auction_data_and_push(pool)

if __name__ == "__main__":
    main()
