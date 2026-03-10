import akshare as ak
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# ================= 配置区 =================
PUSHPLUS_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
# 游资擒龙因子
MIN_MARKET_CAP = 10_0000_0000     # 流通盘下限 10亿
MAX_MARKET_CAP = 150_0000_0000    # 流通盘上限 150亿
MIN_TURNOVER = 5.0                # 换手率下限 5%
GAP_UP_MIN = 2.0                  # 竞价高开下限 2%
GAP_UP_MAX = 6.0                  # 竞价高开上限 6%
# ==========================================

def get_static_pool():
    """第一阶段：9:15运行，计算昨日符合游资审美的静态标的"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始获取全市场基础数据，构建擒龙蓄水池...")
    df_spot = ak.stock_zh_a_spot_em()
    
    # 过滤ST、北交所、科创板
    df_spot = df_spot[~df_spot['名称'].str.contains('ST')]
    df_spot = df_spot[~df_spot['代码'].str.startswith(('8', '688', '4'))]
    
    # 盘面轻盈与活跃度过滤
    df_filtered = df_spot[
        (df_spot['流通市值'] >= MIN_MARKET_CAP) & 
        (df_spot['流通市值'] <= MAX_MARKET_CAP) &
        (df_spot['换手率'] >= MIN_TURNOVER) 
    ].copy()

    target_stocks = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 基础过滤剩余 {len(df_filtered)} 只，开始测算涨停基因...")
    for index, row in df_filtered.iterrows():
        code = row['代码']
        try:
            hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qq")
            if len(hist_df) < 5:
                continue
            
            # 寻找近5天内有过涨停（简化为涨幅>9.5%），且目前不是极高位连板的股票
            limit_up_days = hist_df[hist_df['涨跌幅'] >= 9.5]
            if 1 <= len(limit_up_days) <= 3:
                target_stocks.append({
                    "代码": code,
                    "名称": row['名称'],
                    "昨收": row['昨收']
                })
        except Exception:
            continue
            
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 静态蓄水池构建完成，共锁定 {len(target_stocks)} 只潜在标的。")
    return target_stocks

def get_auction_data_and_push(pool):
    """第二阶段：9:25:05运行，获取竞价结果并推送"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 集合竞价结束，开始狙击异动标的...")
    
    # 获取9:25最新的实时全市场切片
    df_spot_now = ak.stock_zh_a_spot_em()
    
    final_targets = []
    
    for stock in pool:
        # 在实时切片中找到该股票目前的竞价开盘数据
        current_data = df_spot_now[df_spot_now['代码'] == stock['代码']]
        if current_data.empty:
            continue
            
        open_price = current_data['最新价'].values[0] # 9:25的最新价即为开盘价
        pre_close = stock['昨收']
        
        # 计算高开幅度
        if pre_close > 0:
            gap_up_pct = (open_price - pre_close) / pre_close * 100
            
            # 核心战法：满足 2% ~ 6% 的弱转强高开标准
            if GAP_UP_MIN <= gap_up_pct <= GAP_UP_MAX:
                final_targets.append({
                    "代码": stock['代码'],
                    "名称": stock['名称'],
                    "昨收": pre_close,
                    "竞价开盘": open_price,
                    "高开幅度": round(gap_up_pct, 2)
                })

    # 推送至 PushPlus
    date_str = datetime.now().strftime("%Y-%m-%d")
    url = "http://www.pushplus.plus/send"
    
    if not final_targets:
        content = "今日 9:25 集合竞价未发现符合游资高开标准的标的，建议空仓或极轻仓观望。"
    else:
        # 按高开幅度降序排列
        final_targets = sorted(final_targets, key=lambda x: x['高开幅度'], reverse=True)
        
        content = f"<h3>🐉 游资擒龙战法 - 竞价狙击名单 ({date_str})</h3>"
        content += "<p>以下标的已确认早盘符合<b>【弱转强】</b>高开标准，请在开盘 5 分钟内密切盯防资金承接力度：</p>"
        content += "<table border='1' cellspacing='0' cellpadding='5'>"
        content += "<tr><th>代码</th><th>名称</th><th>昨收价</th><th>竞价开盘价</th><th>高开幅度(%)</th></tr>"
        
        for target in final_targets:
            content += f"<tr><td>{target['代码']}</td><td>{target['名称']}</td><td>{target['昨收']}</td><td>{target['竞价开盘']}</td><td><b>+{target['高开幅度']}%</b></td></tr>"
        
        content += "</table>"
        content += "<br><p><b>游资风控铁律：</b>如果开盘后垂直向下砸破分时均线且不回头，<b>绝对放弃买入</b>！只买点火向上的瞬间！</p>"

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": f"⚡ 9:25 擒龙实盘指令 - {date_str}",
        "content": content,
        "template": "html"
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 微信推送成功！")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 推送失败，状态码: {response.status_code}")

def main():
    # 1. 启动即运行第一阶段（建议通过操作系统的定时任务在 9:15 触发此脚本）
    pool = get_static_pool()
    
    if not pool:
        print("未筛选出基础标的，程序结束。")
        return
        
    # 2. 精确等待至 9:25:05 (留5秒给交易所数据延迟)
    now = datetime.now()
    target_time = now.replace(hour=9, minute=25, second=5, microsecond=0)
    
    wait_seconds = (target_time - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 进入休眠，等待 9:25:05 竞价结束唤醒... (需等待 {int(wait_seconds)} 秒)")
        time.sleep(wait_seconds)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 当前时间已过 9:25:05，立即执行竞价拉取！")
        
    # 3. 执行第二阶段并推送
    get_auction_data_and_push(pool)

if __name__ == "__main__":
    main()