"""
飆股雷達 v2 - 全市場掃描核心
資料來源: FinMind
支援: 上市 + 上櫃，約 1,700+ 檔
"""

import os
import json
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
OUTPUT_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://api.finmindtrade.com/api/v4/data"

# ── 選股門檻 ────────────────────────────────────────────
CRITERIA = {
    "min_consolidation_days": 20,
    "min_volume_ratio"      : 1.5,
    "min_score"             : 65,
    "min_price"             : 10,      # 過濾低價股
    "min_volume_daily"      : 500000,  # 最低日均量（張）
}

# ── 產業分類對照表 ──────────────────────────────────────
INDUSTRY_MAP = {
    "半導體": ["半導體", "積體電路", "晶圓", "IC設計", "封測"],
    "電子零組件": ["電子零組件", "被動元件", "連接器", "印刷電路板", "PCB"],
    "電腦及周邊": ["電腦及周邊", "伺服器", "筆記型電腦", "儲存"],
    "通訊網路": ["通訊網路", "網路", "電信", "5G", "光纖"],
    "光電": ["光電", "LED", "面板", "顯示器"],
    "金融保險": ["金融", "銀行", "保險", "證券", "金控"],
    "生技醫療": ["生技", "醫療", "製藥", "醫材", "健康"],
    "電機機械": ["電機", "機械", "自動化", "馬達"],
    "鋼鐵金屬": ["鋼鐵", "金屬", "鋁", "銅"],
    "塑膠化工": ["塑膠", "化工", "石化", "橡膠"],
    "食品": ["食品", "飲料", "農業"],
    "紡織": ["紡織", "成衣"],
    "建材營造": ["建材", "營造", "水泥", "玻璃"],
    "航運": ["航運", "海運", "空運", "貨運"],
    "觀光休閒": ["觀光", "休閒", "飯店", "旅遊"],
    "其他": [],
}

def classify_industry(industry_str: str) -> str:
    if not industry_str:
        return "其他"
    for group, keywords in INDUSTRY_MAP.items():
        if group == "其他":
            continue
        if any(kw in industry_str for kw in keywords):
            return group
        if group in industry_str:
            return group
    return "其他"

def classify_market_cap(close: float, shares: float = None) -> str:
    """依股價簡易分類（無股本資料時用股價代替）"""
    if close >= 500:
        return "大型股"
    elif close >= 100:
        return "中型股"
    elif close >= 30:
        return "小型股"
    else:
        return "微型股"

# ── FinMind API ─────────────────────────────────────────
def fm_get(dataset: str, stock_id: str = "", start: str = "", end: str = "",
           extra: dict = None) -> pd.DataFrame:
    params = {
        "dataset"   : dataset,
        "token"     : FINMIND_TOKEN,
    }
    if stock_id: params["data_id"]    = stock_id
    if start:    params["start_date"] = start
    if end:      params["end_date"]   = end
    if extra:    params.update(extra)

    for attempt in range(3):
        try:
            r = requests.get(BASE_URL, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            if data.get("status") == 200 and data.get("data"):
                return pd.DataFrame(data["data"])
            return pd.DataFrame()
        except Exception as e:
            if attempt == 2:
                log.debug(f"[FinMind] {stock_id} {dataset} 失敗: {e}")
            time.sleep(1)
    return pd.DataFrame()


def get_stock_universe() -> pd.DataFrame:
    """取得全市場股票清單（上市+上櫃）"""
    log.info("取得上市股票清單...")
    params = {
        "dataset": "TaiwanStockInfo",
        "token"  : FINMIND_TOKEN,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=20)
        data = r.json()
        print("API 回傳狀態:", data.get("status"))
        print("欄位:", pd.DataFrame(data.get("data", [])).columns.tolist() if data.get("data") else "無資料")
        if data.get("status") == 200 and data.get("data"):
            df = pd.DataFrame(data["data"])
            # 只保留四碼純數字的普通股
            df = df[df["stock_id"].str.match(r'^\d{4}$', na=False)]
            log.info(f"共取得 {len(df)} 檔股票")
            return df
    except Exception as e:
        log.error(f"取得清單失敗: {e}")
    return pd.DataFrame()


def analyze_stock(stock_id: str, end_date: str) -> dict | None:
    start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=200)).strftime("%Y-%m-%d")

    df = fm_get("TaiwanStockPrice", stock_id, start, end_date)
    if df.empty or len(df) < 65:
        return None

    # 欄位標準化
    df = df.rename(columns={
        "Trading_Volume": "volume",
        "max": "high",
        "min": "low",
    })

    df = df.sort_values("date").reset_index(drop=True)
    for col in ["close", "open", "high", "low", "volume"]:
        if col not in df.columns:
            return None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["close", "volume"])
    if len(df) < 65:
        return None

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    # 基本過濾
    if latest["close"] < CRITERIA["min_price"]:
        return None

    vol_ma20 = df["volume"].iloc[-21:-1].mean()
    if vol_ma20 < CRITERIA["min_volume_daily"]:
        return None

    # 均線
    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    latest = df.iloc[-1]
    score   = 0
    signals = []

    # 1. 均線多頭排列
    try:
        ma_bull4 = (latest["ma5"] > latest["ma10"] > latest["ma20"] > latest["ma60"]
                    and latest["close"] > latest["ma5"])
        ma_bull3 = (latest["ma5"] > latest["ma10"] > latest["ma20"]
                    and latest["close"] > latest["ma5"])
    except:
        return None

    if ma_bull4:
        score += 25; signals.append("趨勢")
    elif ma_bull3:
        score += 15; signals.append("趨勢")

    # 2. 爆量
    vol_ratio = latest["volume"] / vol_ma20 if vol_ma20 > 0 else 0
    if vol_ratio >= CRITERIA["min_volume_ratio"]:
        score += 20; signals.append("籌碼")

    # 3. 底部打底
    recent60 = df["close"].iloc[-61:-1]
    base     = recent60.median()
    in_range = ((recent60 >= base * 0.92) & (recent60 <= base * 1.08))
    run = max_run = 0
    for v in in_range:
        run = run + 1 if v else 0
        max_run = max(max_run, run)
    consolidation_days = max_run
    if consolidation_days >= CRITERIA["min_consolidation_days"]:
        score += 20; signals.append("型態")

    # 4. 突破近20日高點
    high20     = df["close"].iloc[-21:-1].max()
    is_breakout = latest["close"] > high20
    if is_breakout:
        score += 15
        if "型態" not in signals:
            signals.append("型態")

    # 5. 動能
    if len(df) >= 6:
        mom5 = (latest["close"] / df.iloc[-6]["close"] - 1) * 100
    else:
        mom5 = 0
    if mom5 >= 3:
        score += 10; signals.append("動能")
    elif mom5 >= 1:
        score += 5

    # 6. 陽線實體
    body_pct = (latest["close"] - latest["open"]) / latest["open"] * 100 if latest["open"] > 0 else 0
    if body_pct >= 1.5:
        score += 10

    if score < CRITERIA["min_score"]:
        return None

    # 進場策略
    if is_breakout and vol_ratio >= 2.0:
        entry = "盤整突破"
    elif ma_bull3 and vol_ratio < 1.2 and mom5 > 0:
        entry = "回後買上漲"
    else:
        entry = "觀察等待"

    chg = (latest["close"] / prev["close"] - 1) * 100 if prev["close"] > 0 else 0

    return {
        "code"              : stock_id,
        "price"             : round(float(latest["close"]), 1),
        "chg"               : round(chg, 2),
        "score"             : min(score, 100),
        "signals"           : signals,
        "consolidation_days": int(consolidation_days),
        "vol_ratio"         : round(vol_ratio, 2),
        "momentum_5d"       : round(mom5, 2),
        "entry"             : entry,
        "ma_bull4"          : bool(ma_bull4),
    }


def run_screener(date: str = None, max_workers: int = 3) -> list[dict]:
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    # 取得股票清單
    universe = get_stock_universe()
    if universe.empty:
        log.error("無法取得股票清單，終止")
        return []

    stock_ids = universe["stock_id"].tolist()

    # 建立代號→產業對照
    industry_lookup = {}
    name_lookup     = {}
    if "industry_category" in universe.columns:
        for _, row in universe.iterrows():
            sid = row["stock_id"]
            industry_lookup[sid] = classify_industry(str(row.get("industry_category", "")))
            name_lookup[sid]     = str(row.get("stock_name", sid))

    log.info(f"開始掃描 {len(stock_ids)} 檔，基準日: {date}")
    results  = []
    total    = len(stock_ids)
    done     = 0

    # 使用 ThreadPoolExecutor 加速（但控制並發數避免被限速）
    def worker(sid):
        result = analyze_stock(sid, date)
        time.sleep(0.3)
        return sid, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, sid): sid for sid in stock_ids}
        for future in as_completed(futures):
            done += 1
            sid, result = future.result()
            if result:
                result["industry"] = industry_lookup.get(sid, "其他")
                result["name"]     = name_lookup.get(sid, sid)
                result["cap_size"] = classify_market_cap(result["price"])
                results.append(result)
            if done % 50 == 0 or done == total:
                log.info(f"進度: {done}/{total}，目前找到 {len(results)} 檔")

    results.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"掃描完成，共 {len(results)} 檔符合條件")
    return results


if __name__ == "__main__":
    today      = datetime.today().strftime("%Y-%m-%d")
    candidates = run_screener(today)

    out_path = os.path.join(OUTPUT_DIR, f"result_{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": today, "candidates": candidates}, f, ensure_ascii=False, indent=2)

    log.info(f"結果儲存: {out_path}")
    print(f"\n✅ 今日飆股候選：{len(candidates)} 檔")
    for s in candidates[:20]:
        print(f"  {s['code']} {s['name']:8s}  評分:{s['score']:3d}  {s['industry']:8s}  {s['cap_size']}  {s['entry']}")
