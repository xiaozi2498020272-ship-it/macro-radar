import akshare as ak
import datetime
import pandas as pd
import requests

# === 核心配置区 ===
PUSH_TOKEN = "0388622be9f34acdbaaafa2126e80fa2"
# =================

def send_wechat_msg(title, content):
    """通过 PushPlus 发送微信推送"""
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("\n✅ 微信推送成功，雷达运转正常！")
        else:
            print(f"\n❌ 推送失败，错误代码: {response.status_code}")
    except Exception as e:
        print(f"\n❌ 推送异常: {e}")

def get_daily_macro_calendar():
    today = datetime.date.today().strftime("%Y%m%d")
    print(f"正在启动宏观数据雷达，拉取 {today} 核心日历...\n")

    try:
        df = ak.news_economic_baidu(date=today)
        
        if df.empty:
            print("今日无任何宏观数据公布。")
            return

        # 1. 提取中美数据
        region_col = '地区' if '地区' in df.columns else 'country' if 'country' in df.columns else None
        if region_col:
            target_data = df[df[region_col].isin(['美国', '中国'])]
        else:
            target_data = df

        if target_data.empty:
            print("今日中美无相关数据公布。")
            return

        # 2. 核心过滤器：死死拦截低星级数据，只放行对标普500和A股有大影响的事件
        star_col = '重要性' if '重要性' in target_data.columns else 'importance' if 'importance' in target_data.columns else None
        if star_col:
            target_data = target_data[target_data[star_col].astype(str).str.contains('高|3')]
        
        # 如果今天没大事，就推送安心提示
        if target_data.empty:
            msg = "今日中美均无【高优/3星级】核心宏观数据公布。\n盘面受消息面干预概率极低，请安心持有底仓，维持原有的定投纪律。"
            print(msg)
            send_wechat_msg(title=f"{today} 宏观清淡", content=msg)
            return
            
        print("--- 抓取到核心数据，准备推送 ---")
        push_messages = []
        
        for index, row in target_data.iterrows():
            time_str = row.get('时间', row.get('time', '未知时间'))
            event = row.get('事件', row.get('标题', row.get('指标名称', '未知事件')))
            country = row.get('地区', row.get('country', ''))
            prev = row.get('前值', row.get('previous', '-'))
            fore = row.get('预测值', row.get('forecast', '-'))
            
            single_msg = f"📍 [{country}] {time_str}\n{event}\n前值: {prev} | 预期: {fore}\n"
            print(single_msg.strip()) 
            push_messages.append(single_msg) 
            
        final_push_text = "【今日重磅数据预警】\n\n" + "\n".join(push_messages)
        
        send_wechat_msg(title=f"{today} 中美核心数据雷达", content=final_push_text)
            
    except Exception as e:
        print(f"系统运行出现错误: {e}")

if __name__ == "__main__":
    get_daily_macro_calendar()