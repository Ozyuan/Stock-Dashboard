"""
fetch_data.py
每天由 GitHub Actions 定时自动执行一次：
1. 从 Finnhub 拉取行情（现价/涨跌幅）、当天分时K线（含成交量）、公司新闻、近期财报日历
2. 做一些"纯数学"的计算（成交量是否放大、新闻大致对应哪根K线）
3. 把结果写成 data.json，网页会直接读取这个文件来显示

注意：这里【没有】用AI去判断"新闻导致了涨跌"这种因果关系，
只是把"时间最接近的新闻"和"那根K线的涨跌/成交量"摆在一起给你参考，
真正的因果判断建议你自己看新闻内容来判断。
如果想要AI自动生成"涨跌原因"的文字分析，需要额外接一个语言模型API（比如Claude），
这个可以作为下一步升级，现在先把免费、纯数据的版本跑通。
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse
from zoneinfo import ZoneInfo

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
if not FINNHUB_KEY:
    print("错误：没有读取到环境变量 FINNHUB_API_KEY，请检查 GitHub Secrets 设置。")
    sys.exit(1)

ET = ZoneInfo("America/New_York")
BASE = "https://finnhub.io/api/v1"

SYMBOLS = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "META"]
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "NVDA": "NVIDIA Corp.",
    "TSLA": "Tesla Inc.",
    "MSFT": "Microsoft Corp.",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc.",
}


def api_get(path, params, retries=3):
    """调用 Finnhub API，自动处理限速重试。"""
    params = dict(params)
    params["token"] = FINNHUB_KEY
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "stock-news-dashboard"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"  被限速(429)，等待 {wait}s 后重试...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"多次重试后仍失败: {path}")


def get_quote(symbol):
    return api_get("/quote", {"symbol": symbol})


def get_candles(symbol, resolution="30"):
    """拉取当天从开盘(09:30 ET)到现在的分时K线。"""
    now_ts = int(time.time())
    now_et = datetime.datetime.now(tz=ET)
    market_open_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    from_ts = int(market_open_et.timestamp())
    return api_get(
        "/stock/candle",
        {"symbol": symbol, "resolution": resolution, "from": from_ts, "to": now_ts},
    )


def get_news(symbol, days_back=1):
    today = datetime.date.today()
    frm = today - datetime.timedelta(days=days_back)
    return api_get("/company-news", {"symbol": symbol, "from": frm.isoformat(), "to": today.isoformat()})


def get_earnings(symbol):
    today = datetime.date.today()
    to = today + datetime.timedelta(days=21)
    try:
        data = api_get("/calendar/earnings", {"symbol": symbol, "from": today.isoformat(), "to": to.isoformat()})
        return data.get("earningsCalendar", [])
    except Exception as e:
        print(f"  财报日历获取失败（可能免费额度不支持）：{e}")
        return []


def nearest_bar_index(news_ts, bar_times):
    if not bar_times:
        return 0
    best_idx, best_diff = 0, None
    for i, t in enumerate(bar_times):
        diff = abs(t - news_ts)
        if best_diff is None or diff < best_diff:
            best_diff, best_idx = diff, i
    return best_idx


def build_stock_data(symbol):
    result = {"name": COMPANY_NAMES.get(symbol, symbol), "error": None}
    try:
        quote = get_quote(symbol)
        candles = get_candles(symbol)

        if candles.get("s") != "ok" or not candles.get("t"):
            raise RuntimeError(f"当前无K线数据（状态: {candles.get('s')}），可能未开盘或免费额度限制")

        times = candles["t"]
        closes = candles["c"]
        volumes = candles["v"]
        time_labels = [datetime.datetime.fromtimestamp(t, tz=ET).strftime("%H:%M") for t in times]

        avg_volume = (sum(volumes) / len(volumes)) if volumes else 0

        # 早期预警：最新一根K线成交量是否远超当天均量
        early_warning = {"active": False, "text": ""}
        if volumes and avg_volume > 0:
            latest_ratio = volumes[-1] / avg_volume
            if latest_ratio >= 1.5:
                early_warning = {
                    "active": True,
                    "text": f"最近一段（{time_labels[-1]} 附近）成交量为当日均量的 {latest_ratio:.1f} 倍，明显放大，值得留意是否有消息面变化。",
                }

        # 新闻，就近匹配到某根K线，附带该K线的涨跌与成交量倍数（不代表因果关系）
        raw_news = get_news(symbol, days_back=1)
        news_items = []
        for item in raw_news[:6]:
            ts = item.get("datetime", 0)
            if not ts:
                continue
            idx = nearest_bar_index(ts, times)
            bar_change = None
            if idx > 0:
                bar_change = ((closes[idx] - closes[idx - 1]) / closes[idx - 1]) * 100
            vol_ratio = (volumes[idx] / avg_volume) if avg_volume else None
            news_items.append(
                {
                    "idx": idx,
                    "title": item.get("headline", ""),
                    "src": item.get("source", ""),
                    "url": item.get("url", ""),
                    "time": datetime.datetime.fromtimestamp(ts, tz=ET).strftime("%H:%M ET"),
                    "barChangePct": bar_change,
                    "volRatio": vol_ratio,
                }
            )

        # 近期财报等风险事件
        earnings = get_earnings(symbol)
        events = []
        for e in earnings[:2]:
            events.append(
                {
                    "type": "earnings",
                    "title": f"预计公布财报（市场预估EPS: {e.get('epsEstimate', 'N/A')}）",
                    "when": e.get("date", ""),
                    "impact": "high",
                }
            )

        result.update(
            {
                "timesLabel": time_labels,
                "prices": closes,
                "volumes": volumes,
                "avgVolume": avg_volume,
                "earlyWarning": early_warning,
                "news": news_items,
                "events": events,
                "currentPrice": quote.get("c"),
                "changePct": quote.get("dp"),
            }
        )

    except Exception as e:
        result["error"] = str(e)
        print(f"  [{symbol}] 出错: {e}")

    return result


def main():
    out = {"generatedAt": datetime.datetime.now(tz=ET).isoformat(), "stocks": {}}
    for sym in SYMBOLS:
        print(f"抓取 {sym} ...")
        out["stocks"][sym] = build_stock_data(sym)
        time.sleep(1.2)  # 主动限速，避免触发免费额度的429

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("完成，已写入 data.json")


if __name__ == "__main__":
    main()
