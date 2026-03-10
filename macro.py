import akshare as ak
import pandas as pd
import requests
import time
from datetime import datetime

# ================= 配置区 =================
PUSHPLUS_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
# ==========================================

def get_market_data_and_filter():
    """拉取全市场数据并进行双层梯队筛选"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始拉取 A 股实时切片数据...")
    
    # 获取 A 股实时行情数据
    df_spot = ak.stock_zh_a_spot_em()
    
    # 基础过滤：剔除ST股、北交所(8开头)、科创板(688开头)、老三板(4开头)
    df_spot = df_spot[~df_spot['名称'].str.contains('ST')]
    df_spot = df_spot[~df_spot['代码'].str.startswith(('8', '688', '4'))]
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 基础过滤完成，开始划分战略梯队...")

    # 第一梯队：完全符合标准的买入目标（涨幅 3% - 5%，换手率 >= 5%）
    strict_targets = df_spot[
        (df_spot['涨跌幅'] >= 3.0) & 
        (df_spot['涨跌幅'] <= 5.0) & 
        (df_spot['换手率'] >= 5.0)
    ].copy()
    
    # 第二梯队：高优先备选队列（涨幅 1.5% - 5%，换手率 >= 4%）
    # 必须剔除掉已经进入第一梯队的股票
    near_miss_targets = df_spot[
        (df_spot['涨跌幅'] >= 1.5) & 
        (df_spot['涨跌幅'] <= 5.0) & 
        (df_spot['换手率'] >= 4.0) &
        (~df_spot['代码'].isin(strict_targets['代码']))
    ].copy()

    return strict_targets, near_miss_targets

def push_results(strict_df, near_miss_df):
    """将两层梯队的数据格式化为美观的 HTML 并推送至微信"""
    url = "http://www.pushplus.plus/send"
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 基础 CSS 样式定义（针对微信移动端优化）
    html_content = f"""
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ padding: 10px; }}
        .title {{ font-size: 20px; font-weight: bold; text-align: center; color: #1a1a1a; margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        .section-title {{ font-size: 16px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; padding: 5px 10px; border-radius: 4px; }}
        .title-strict {{ background-color: #ffebee; color: #c62828; border-left: 4px solid #c62828; }}
        .title-near {{ background-color: #e3f2fd; color: #1565c0; border-left: 4px solid #1565c0; }}
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
        <div class="title">🎯 尾盘战法 14:40 狙击指令</div>
    """

    # --- 构建第一梯队：完全达标的核心目标 ---
    html_content += '<div class="section-title title-strict">🔥 核心狙击目标 (完全达标)</div>'
    if strict_df.empty:
        html_content += '<p style="text-align: center; color: #888; font-size: 14px;">当前无完全符合严格标准的标的。</p>'
    else:
        # 按换手率降序排序，选出最具活力的前10只标的
        strict_df = strict_df.sort_values(by='换手率', ascending=False).head(10)
        html_content += '<table><tr><th>代码</th><th>名称</th><th>涨幅</th><th>换手率</th></tr>'
        for _, row in strict_df.iterrows():
            html_content += f"""
            <tr>
                <td style="color: #666;">{row['代码']}</td>
                <td style="font-weight: bold;">{row['名称']}</td>
                <td class="red-text">+{round(row['涨跌幅'], 2)}%</td>
                <td>{round(row['换手率'], 2)}%</td>
            </tr>
            """
        html_content += '</table>'

    # --- 构建第二梯队：高优先备选队列 ---
    html_content += '<div class="section-title title-near">⚡ 高优先备选队列 (蓄势待发)</div>'
    if near_miss_df.empty:
        html_content += '<p style="text-align: center; color: #888; font-size: 14px;">当前无接近达标的备选标的。</p>'
    else:
        # 备选队列也按换手率排序，提取前 8 名避免信息过载
        near_miss_df = near_miss_df.sort_values(by='换手率', ascending=False).head(8)
        html_content += '<table><tr><th>代码</th><th>名称</th><th>涨幅</th><th>换手率</th></tr>'
        for _, row in near_miss_df.iterrows():
            html_content += f"""
            <tr>
                <td style="color: #666;">{row['代码']}</td>
                <td style="font-weight: bold;">{row['名称']}</td>
                <td class="red-text">+{round(row['涨跌幅'], 2)}%</td>
                <td>{round(row['换手率'], 2)}%</td>
            </tr>
            """
        html_content += '</table>'

    # --- 风险提示模块 ---
    html_content += """
        <div class="tips">
            <b>纪律执行提示：</b><br>
            1. 请务必在 14:45 - 14:55 之间完成分时均线承接力度的最终确认。<br>
            2. 若尾盘大盘出现跳水放量，无论标的形态多好，坚决放弃买入。<br>
            3. 备选队列仅做次日观察或极轻仓试错，核心仓位必须留给完全达标标的。
        </div>
    </div>
    </body>
    </html>
    """

    # 组装 API 请求负载
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": f"尾盘战法决策 - {date_str} 14:40",
        "content": html_content,
        "template": "html"
    }
    
    # 发送推送
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 尾盘策略排版推送成功！请查收微信。")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 推送失败，PushPlus 状态码: {response.status_code}")
    except Exception as e:
        print(f"推送过程发生异常: {e}")

def main():
    # 核心：精确计算需要休眠的时间，直到北京时间 14:40:02 避开网络延迟
    now = datetime.now()
    target_time = now.replace(hour=14, minute=40, second=2, microsecond=0)
    
    wait_seconds = (target_time - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 脚本已在 GitHub 云端启动，进入静默休眠...")
        print(f"等待 14:40:02 唤醒狙击 (还需等待 {int(wait_seconds)} 秒)")
        time.sleep(wait_seconds)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 当前时间已过 14:40，立即执行数据拉取！")
        
    # 时间到达，唤醒执行
    strict_targets, near_miss_targets = get_market_data_and_filter()
    push_results(strict_targets, near_miss_targets)

if __name__ == "__main__":
    main()
