import akshare as ak
import datetime
import pandas as pd
import requests
import time

# === 核心配置区 ===
PUSH_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
TARGET_POOL_INDEX = "000016"  # 改为上证50指数，只扫描50只龙头股，极大降低被封IP概率，用于测试打通链路
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
        if df.empty:
            return "今日无任何宏观数据公布。\n"

        region_col = '地区' if '地区' in df.columns else 'country' if 'country' in df.columns else None
        if region_col:
            target_data = df[df[region_col].isin(['美国', '中国'])]
        else:
            target_data = df

        if target_data.empty:
            return "今日中美无相关数据公布。\n"

        star_col = '重要性' if '重要性' in target_data.columns else 'importance' if 'importance' in target_data.columns else None
        if star_col:
            target_data = target_data[target_data[star_col].astype(str).str.contains('高|3')]
        
        if target_data.empty:
            return "> 今日中美均无【高优/3星级】核心宏观数据公布。\n> 盘面受消息面干预概率极低，请安心持有底仓，维持原有的定投纪律。\n"
            
        push_messages = ["**【今日重磅宏观预警】**\n"]
        for index, row in target_data.iterrows():
            time_str = row.get('时间', row.get('time', '未知时间'))
            event = row.get('事件', row.get('标题', row.get('指标名称', '未知事件')))
            country = row.get('地区', row.get('country', ''))
            prev = row.get('前值', row.get('previous', '-'))
            fore = row.get('预测值', row.get('forecast', '-'))
            
            single_msg = f"- **[{country}] {time_str}**\n  {event} (前值: {prev} | 预期: {fore})"
            push_messages.append(single_msg)
            
        return "\n".join(push_messages) + "\n"
        
    except Exception as e:
        return f"⚠️ 宏观数据抓取异常: {e}\n"

def get_market_str():
    """抓取核心资产每日盘口数据"""
    print("正在抓取盘口数据...")
    report_lines = ["**【核心资产异动播报】**\n"]
    
    try:
        a_etf_df = ak.fund_etf_spot_em()
        target_a_assets = {
            "510500": "中证500ETF (A股宽基)",
            "588200": "科创芯片ETF (核心科技赛道)",
            "518880": "黄金ETF (防御底仓)"
        }
        report_lines.append("**📍 国内盘面 (A股/黄金)**")
        for code, name in target_a_assets.items():
            asset_data = a_etf_df[a_etf_df["代码"] == code]
            if not asset_data.empty:
                price = asset_data["最新价"].values[0]
                pct_change = asset_data["涨跌幅"].values[0]
                trend = "🔴涨" if pct_change > 0 else "🟢跌" if pct_change < 0 else "⚪平"
                report_lines.append(f"- {name}: `{price}` | {pct_change}% {trend}")
            else:
                report_lines.append(f"- {name}: 数据获取失败")

        us_etf_df = ak.stock_us_spot_em()
        target_us_assets = {
            "105.SPY": "SPY (标普500)",
            "105.QQQ": "QQQ (纳指100)"
        }
        report_lines.append("\n**📍 海外盘面 (美股引擎)**")
        for code, name in target_us_assets.items():
            asset_data = us_etf_df[us_etf_df["代码"] == code]
            if not asset_data.empty:
                price = asset_data["最新价"].values[0]
                pct_change = asset_data["涨跌幅"].values[0]
                trend = "🔴涨" if pct_change > 0 else "🟢跌" if pct_change < 0 else "⚪平"
                report_lines.append(f"- {name}: `${price}` | {pct_change}% {trend}")
            else:
                report_lines.append(f"- {name}: 数据获取失败 (检查前缀)")

        return "\n".join(report_lines) + "\n"

    except Exception as e:
        return f"⚠️ 盘面数据抓取异常: {str(e)}\n"

# ================= 量化选股模块 =================
def check_macro_gate():
    """宏观风控：上证指数收盘价是否大于20日均线"""
    try:
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        df['MA20'] = df['close'].rolling(20).mean()
        latest = df.iloc[-1]
        return latest['close'] > latest['MA20']
    except Exception:
        return True

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
    """单只股票的策略验证逻辑"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if len(df) < 60:
            return False
            
        df = calc_indicators(df)
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        if not (today['MA20'] > today['MA60'] and today['MA20'] > yesterday['MA20']): return False
        if not (today['收盘'] > today['BBI'] and today['BBI'] > yesterday['BBI']): return False
        if not (today['成交量'] < today['V_MA5'] * 0.6): return False
        if not (today['J'] < 20): return False
        if not (today['最低'] <= today['MA20'] * 1.015 and today['收盘'] > today['MA20']): return False
            
        return True
    except Exception:
        return False

def get_quant_strategy_str():
    """执行量化选股并生成报告"""
    print("正在执行量化选股策略扫描 (耗时较长，请耐心等待)...")
    
    if not check_macro_gate():
        return "**【🎯 量化选股信号 (缩量回踩)】**\n> 🔴 宏观风控阻断：当前上证指数跌破20日均线。今日强制空仓，暂停选股。\n"

    try:
        pool_df = ak.index_stock_cons_weight_csindex(symbol=TARGET_POOL_INDEX)
    except Exception as e:
        return f"**【🎯 量化选股信号】**\n> ⚠️ 获取基础股票池失败: {e}\n"

    selected_stocks = []
    total_count = len(pool_df)
    
    for idx, row in pool_df.iterrows():
        code = row['成分券代码']
        name = row['成分券名称']
        
        # 每一只股票都实时打印，使用 \r 覆盖同一行，不刷屏
        print(f"雷达扫描中: [{idx + 1}/{total_count}] - {name} ({code}) ...", end="\r")
        
        time.sleep(0.5)  # 睡眠时间延长到 0.5 秒，防封 IP
        
        if strategy_filter(code):
            try:
                realtime = ak.stock_zh_a_spot_em()
                stock_rt = realtime[realtime['代码'] == code].iloc[0]
                price = stock_rt['最新价']
                pct = stock_rt['涨跌幅']
                selected_stocks.append(f"- **{name}** ({code}) | 现价: `{price}` | 涨幅: {pct}%")
            except:
                selected_stocks.append(f"- **{name}** ({code})")
                
    print("\n扫描完成！正在生成并推送报告...") 
    
    report_lines = ["**【🎯 量化选股信号 (缩量回踩)】**\n"]
    if selected_stocks:
        report_lines.append("> 🟢 今日符合特征的标的如下，请人工确认K线图形后择机入场：\n")
        report_lines.extend(selected_stocks)
    else:
        report_lines.append("> ⚪ 今日标的池中无符合“缩量回踩”特征的股票，继续空仓或持底仓。")

    return "\n".join(report_lines) + "\n"
# ===============================================

if __name__ == "__main__":
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"=== 启动投资数据雷达 ({today_str}) ===\n")

    # 1. 获取各个模块数据
    macro_info = get_macro_str()
    market_info = get_market_str()
    quant_info = get_quant_strategy_str()

    # 2. 拼接为一份完整的 Markdown 报告
    final_content = f"{macro_info}\n---\n\n{market_info}\n---\n\n{quant_info}"
    
    # 3. 本地预览打印
    print("\n" + "="*30 + " 报告预览 " + "="*30)
    print(final_content)
    print("="*70 + "\n")
    
    # 4. 执行推送
    send_wechat_msg(title=f"📊 {today_str} 投资核心日报", content=final_content)
