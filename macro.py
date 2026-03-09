import akshare as ak
import datetime
import pandas as pd
import requests
import time

# === 核心配置区 ===
PUSH_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
# =================

def send_wechat_msg(title, content):
    """通过 PushPlus 发送微信推送"""
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200 and response.json().get('code') == 200:
            print("\n✅ 微信推送成功，雷达运转正常！")
        else:
            print(f"\n❌ 推送失败，状态/返回: {response.status_code} / {response.text}")
    except Exception as e:
        print(f"\n❌ 推送异常: {e}")

def get_macro_str():
    """抓取并过滤中美核心宏观数据"""
    today = datetime.date.today().strftime("%Y%m%d")
    print("正在抓取宏观数据...")
    try:
        df = ak.news_economic_baidu(date=today)
        if df.empty: return "今日无任何宏观数据公布。\n"
        region_col = '地区' if '地区' in df.columns else 'country' if 'country' in df.columns else None
        if region_col: target_data = df[df[region_col].isin(['美国', '中国'])]
        else: target_data = df
        if target_data.empty: return "今日中美无相关数据公布。\n"
        star_col = '重要性' if '重要性' in target_data.columns else 'importance' if 'importance' in target_data.columns else None
        if star_col: target_data = target_data[target_data[star_col].astype(str).str.contains('高|3')]
        if target_data.empty:
            return "> 今日中美均无【高优/3星级】核心宏观数据公布。\n> 盘面受消息面干预概率极低，请安心持有底仓，维持原有的定投纪律。\n"
        push_messages = ["**【今日重磅宏观预警】**\n"]
        for index, row in target_data.iterrows():
            time_str = row.get('时间', row.get('time', '未知时间'))
            event = row.get('事件', row.get('标题', row.get('指标名称', '未知事件')))
            country = row.get('地区', row.get('country', ''))
            prev = row.get('前值', row.get('previous', '-'))
            fore = row.get('预测值', row.get('forecast', '-'))
            push_messages.append(f"- **[{country}] {time_str}**\n  {event} (前值: {prev} | 预期: {fore})")
        return "\n".join(push_messages) + "\n"
    except Exception as e:
        return f"⚠️ 宏观数据抓取异常: {e}\n"

def get_market_str():
    """抓取核心资产每日盘口数据"""
    print("正在抓取盘口数据...")
    report_lines = ["**【核心资产异动播报】**\n"]
    try:
        a_etf_df = ak.fund_etf_spot_em()
        target_a_assets = {"510500": "中证500ETF (A股宽基)", "588200": "科创芯片ETF (核心科技)", "518880": "黄金ETF (防御底仓)"}
        report_lines.append("**📍 国内盘面 (A股/黄金)**")
        for code, name in target_a_assets.items():
            asset_data = a_etf_df[a_etf_df["代码"] == code]
            if not asset_data.empty:
                price = asset_data["最新价"].values[0]
                pct_change = asset_data["涨跌幅"].values[0]
                trend = "🔴涨" if pct_change > 0 else "🟢跌" if pct_change < 0 else "⚪平"
                report_lines.append(f"- {name}: `{price}` | {pct_change}% {trend}")
            else: report_lines.append(f"- {name}: 数据获取失败")
            
        us_etf_df = ak.stock_us_spot_em()
        target_us_assets = {"105.SPY": "SPY (标普500)", "105.QQQ": "QQQ (纳指100)"}
        report_lines.append("\n**📍 海外盘面 (美股引擎)**")
        for code, name in target_us_assets.items():
            asset_data = us_etf_df[us_etf_df["代码"] == code]
            if not asset_data.empty:
                price = asset_data["最新价"].values[0]
                pct_change = asset_data["涨跌幅"].values[0]
                trend = "🔴涨" if pct_change > 0 else "🟢跌" if pct_change < 0 else "⚪平"
                report_lines.append(f"- {name}: `${price}` | {pct_change}% {trend}")
            else: report_lines.append(f"- {name}: 数据获取失败 (检查前缀)")
        return "\n".join(report_lines) + "\n"
    except Exception as e:
        return f"⚠️ 盘面数据抓取异常: {str(e)}\n"

# ================= 量化选股模块 =================
def check_macro_gate():
    """宏观风控：上证指数收盘价是否大于20日均线"""
    try:
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        df['MA20'] = df['close'].rolling(20).mean()
        return df.iloc[-1]['close'] > df.iloc[-1]['MA20']
    except: return True

def calc_indicators(df):
    """计算策略所需技术指标"""
    df['MA20'] = df['收盘'].rolling(20).mean()
    df['MA60'] = df['收盘'].rolling(60).mean()
    df['MA3'] = df['收盘'].rolling(3).mean()
    df['MA6'] = df['收盘'].rolling(6).mean()
    df['MA12'] = df['收盘'].rolling(12).mean()
    df['MA24'] = df['收盘'].rolling(24).mean()
    df['BBI'] = (df['MA3'] + df['MA6'] + df['MA12'] + df['MA24']) / 4
    df['V_MA5'] = df['成交量'].rolling(5).mean()
    
    low_list = df['最低'].rolling(9, min_periods=9).min()
    high_list = df['最高'].rolling(9, min_periods=9).max()
    rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    return df

def strategy_filter(stock_code):
    """单只股票的策略验证逻辑（深度校验）"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if len(df) < 60: return False
        df = calc_indicators(df)
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # === 新增：K线形态安全因子 ===
        # 1. 拒绝跳空低开 (防重大利空)
        if today['开盘'] < yesterday['收盘'] * 0.985: return False 
        # 2. 拒绝光头大长阴 (防坚决出货)
        if today['收盘'] < today['开盘'] * 0.97: return False
        # 3. 拒绝长上影线 (防抛压极重)
        if today['收盘'] > today['开盘']:
            if (today['最高'] - today['收盘']) > (today['收盘'] - today['开盘']) * 1.5:
                return False
        
        # === 原有基础逻辑 ===
        if not (today['MA20'] > today['MA60'] and today['MA20'] > yesterday['MA20']): return False
        if not (today['收盘'] > today['BBI'] and today['BBI'] > yesterday['BBI']): return False
        # 严格缩量：当日成交量必须小于 5日均量 * 0.6
        if not (today['成交量'] < today['V_MA5'] * 0.6): return False
        if not (today['J'] < 20): return False
        if not (today['最低'] <= today['MA20'] * 1.015 and today['收盘'] > today['MA20']): return False
            
        return True
    except: return False

def get_quant_strategy_str():
    """全市场预筛 + 深度量化过滤"""
    print("正在执行全市场动量与活跃度初筛...")
    if not check_macro_gate():
        return "**【🎯 量化选股信号 (缩量回踩)】**\n> 🔴 宏观风控阻断：当前上证指数跌破20日均线。今日强制空仓，暂停选股。\n"

    try:
        spot_df = ak.stock_zh_a_spot_em()
        spot_df = spot_df[~spot_df['名称'].str.contains('ST')]
        spot_df = spot_df[~spot_df['代码'].str.startswith(('8', '4', '3', '68'))] 
        
        # === 核心多因子预筛 ===
        spot_df = spot_df[
            (spot_df['流通市值'] > 10000000000) &    # 百亿市值龙头
            (spot_df['量比'] <= 0.8) &             # 盘口极度缩量
            (spot_df['涨跌幅'] >= -4) &            # 拒绝暴跌
            (spot_df['涨跌幅'] <= 2) &             # 拒绝追高
            (spot_df['换手率'] >= 2.0) &            # 活跃度因子：过滤死水
            (spot_df['60日涨跌幅'] >= 15.0)        # 动量因子：近期强势主线
        ]
        
        # 按量比极度缩量排序，取最优质的前 400 只进入精准测算
        spot_df = spot_df.sort_values(by='量比', ascending=True)
        pool_df = spot_df.head(400).copy()
        
    except Exception as e:
        return f"**【🎯 量化选股信号】**\n> ⚠️ 获取全市场预筛数据失败: {e}\n"

    selected_stocks = []
    total_count = len(pool_df)
    
    for idx, row in pool_df.iterrows():
        code = row['代码']
        name = row['名称']
        print(f"雷达深度测算中: [{idx + 1}/{total_count}] - {name} ({code}) ...", end="\r")
        time.sleep(0.2)
        
        if strategy_filter(code):
            price = row['最新价']
            pct = row['涨跌幅']
            selected_stocks.append(f"- **{name}** ({code}) | 现价: `{price}` | 涨跌幅: {pct}%")
                
    print("\n扫描完成！正在生成并推送报告...") 
    report_lines = ["**【🎯 量化选股信号 (多因子精锐版)】**\n"]
    if selected_stocks:
        report_lines.append("> 🟢 今日符合【百亿主线活跃股 + 强支撑位洗盘 + K线安全防御】的极品标的如下：\n")
        report_lines.extend(selected_stocks)
    else:
        report_lines.append("> ⚪ 今日全市场无完美契合【少妇战法】全因子的标的。宁可错过，绝不乱做。继续空仓或持底仓。")

    return "\n".join(report_lines) + "\n"
# ===============================================

if __name__ == "__main__":
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"=== 启动投资数据雷达 ({today_str}) ===\n")
    macro_info = get_macro_str()
    market_info = get_market_str()
    quant_info = get_quant_strategy_str()
    final_content = f"{macro_info}\n---\n\n{market_info}\n---\n\n{quant_info}"
    print("\n" + "="*30 + " 报告预览 " + "="*30)
    print(final_content)
    print("="*70 + "\n")
    send_wechat_msg(title=f"📊 {today_str} 投资核心日报", content=final_content)
