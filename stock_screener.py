"""飆股雷達選股系統 v4 - 四套獨立評分系統"""
import os, json, logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

BASE_URL = "https://api.finmindtrade.com/api/v4/data"

CRITERIA = {
    "min_consolidation_days": 20,
    "min_volume_ratio": 1.0,
    "min_score": 55,
    "min_price": 20,
    "min_volume_daily": 500000,
}

INDUSTRY_MAP = {
    "水泥": "水泥",
    "食品": "食品",
    "塑膠": "塑膠",
    "紡織": "紡織",
    "電機": "電機",
    "電器電纜": "電器電纜",
    "玻璃陶瓷": "玻璃陶瓷",
    "鋼鐵": "鋼鐵",
    "橡膠": "橡膠",
    "造紙": "造紙",
    "化肥": "化肥",
    "化學": "化學",
    "生技醫療": "生技醫療",
    "油電燃氣": "油電燃氣",
    "玻璃": "玻璃",
    "陶瓷": "陶瓷",
    "營建": "營建",
    "運輸": "運輸",
    "觀光": "觀光",
    "金融保險": "金融保險",
    "貿易百貨": "貿易百貨",
    "綜合": "綜合",
    "其他": "其他",
}

def get_stock_universe():
    try:
        params = {
            "dataset": "TaiwanStockInfo",
            "token": os.getenv("FINMIND_TOKEN", "")
        }
        r = requests.get(BASE_URL, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                df = pd.DataFrame(data["data"])
                # 不篩選 market_type，直接使用所有股票
                df = df.drop_duplicates(subset=["stock_id"])
                return df
    except Exception as e:
        log.error(f"❌ 取得股票清單失敗: {e}")
    return pd.DataFrame()

def classify_industry(cat):
    for key, val in INDUSTRY_MAP.items():
        if key in str(cat):
            return val
    return "其他"

def fetch_stock_data(stock_id, end_date):
    try:
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=250)).strftime("%Y-%m-%d"),
            "end_date": end_date,
            "token": os.getenv("FINMIND_TOKEN", "")
        }
        r = requests.get(BASE_URL, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data["data"]:
                df = pd.DataFrame(data["data"])
                df = df.rename(columns={"Trading_Volume": "volume", "max": "high", "min": "low"})
                df["close"] = pd.to_numeric(df["close"], errors="coerce")
                df["high"] = pd.to_numeric(df["high"], errors="coerce")
                df["low"] = pd.to_numeric(df["low"], errors="coerce")
                df["open"] = pd.to_numeric(df["open"], errors="coerce")
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
                df = df.dropna(subset=["close"])
                return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        log.debug(f"⚠️ {stock_id} 資料取得失敗: {e}")
    return pd.DataFrame()

def analyze_stock(stock_id, stock_name, industry, df, date):
    if df.empty or len(df) < 60:
        return None
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    
    price = float(latest["close"])
    if price < CRITERIA["min_price"]:
        return None
    
    vol = int(latest["volume"])
    if vol < CRITERIA["min_volume_daily"]:
        return None
    
    # 共用指標
    chg = ((price - float(prev["close"])) / float(prev["close"]) * 100) if prev["close"] > 0 else 0
    vol_ma20 = df["volume"].iloc[-21:-1].mean() if len(df) >= 21 else df["volume"].mean()
    vol_ma5 = df["volume"].iloc[-6:-1].mean() if len(df) >= 6 else df["volume"].mean()
    prev_vol = float(prev["volume"])
    prev_close = float(prev["close"])
    prev_high = float(prev["high"])
    
    # 新指標
    upper_shadow_pct = ((latest["high"] - latest["close"]) / latest["close"] * 100) if latest["close"] > 0 else 0
    vol_ratio_prev = vol / prev_vol if prev_vol > 0 else 0
    vol_ratio_5d = vol / vol_ma5 if vol_ma5 > 0 else 0
    
    # 5日均價
    avg_price_5d = df["close"].iloc[-6:-1].mean() if len(df) >= 6 else price
    
    # 均線
    ma5 = df["close"].iloc[-6:-1].mean() if len(df) >= 6 else price
    ma10 = df["close"].iloc[-11:-1].mean() if len(df) >= 11 else price
    ma20 = df["close"].iloc[-21:-1].mean() if len(df) >= 21 else price
    ma60 = df["close"].iloc[-61:-1].mean() if len(df) >= 61 else price
    
    ma_bull3 = (ma5 > ma10 > ma20) and (price > ma5)
    ma_bull4 = (ma5 > ma10 > ma20 > ma60) and (price > ma5)
    
    # 新高判定
    high20 = df["close"].iloc[-21:-1].max() if len(df) >= 21 else 0
    is_new_high_20 = price > high20
    
    # 昨日最高點
    over_prev_h = price > prev_high
    
    # 量縮判定
    vol_ma5_thresh = vol_ma20 * 0.80
    vol_reduced = vol_ma5 < vol_ma5_thresh
    
    # 20日均量
    vol_ratio_20d = vol / vol_ma20 if vol_ma20 > 0 else 0
    
    # 動能
    mom5 = ((price / df.iloc[-6]["close"] - 1) * 100) if len(df) >= 6 and df.iloc[-6]["close"] > 0 else 0
    
    # 熱門產業（動態偵測）
    hot_industries = []  # 在 run_screener 中動態生成
    
    result_score = 0
    result_sigs = []
    result_entry = None
    
    # ═══════════════════════════════════════
    #  系統一：盤整突破（必備 5 條件）
    # ═══════════════════════════════════════
    score_b = 0
    sigs_b = []
    
    # 必備條件檢查
    b1 = is_new_high_20
    b2 = ma_bull3
    b3 = over_prev_h
    b4 = vol_ratio_prev >= 1.0  # 今日量 > 昨日量
    b5 = upper_shadow_pct < 3.0  # 上影線 < 3%
    
    breakout_valid = b1 and b2 and b3 and b4 and b5
    
    if breakout_valid:
        score_b = 100
        sigs_b = ["型態", "籌碼", "趨勢"]
    
    # ═══════════════════════════════════════
    #  系統二：回後買上漲（必備 5 條件）
    # ═══════════════════════════════════════
    score_p = 0
    sigs_p = []
    
    # 支撐不破（20MA）
    support_hold = price > ma20
    
    # 必備條件檢查
    p1 = vol_reduced  # 近 5 日量縮
    p2 = vol_ratio_5d >= 1.0  # 今日量 > 5日均量
    p3 = ma_bull3
    p4 = support_hold
    p5 = over_prev_h
    p6 = vol_ratio_prev >= 1.2  # 今日量 > 昨日量 × 1.2
    
    pullback_valid = p1 and p2 and p3 and p4 and p5 and p6
    
    if pullback_valid:
        score_p = 100
        sigs_p = ["型態", "籌碼", "趨勢"]
    
    # ═══════════════════════════════════════
    #  系統三：強勢上漲（必備 5 條件）
    # ═══════════════════════════════════════
    score_s = 0
    sigs_s = []
    
    # 必備條件檢查
    s1 = is_new_high_20
    s2 = ma_bull3
    s3 = vol_ratio_20d >= 1.5  # 爆量 ≥ 1.5x
    s4 = over_prev_h
    s5 = vol_ratio_prev >= 1.0  # 今日量 > 昨日量
    
    strong_valid = s1 and s2 and s3 and s4 and s5
    
    if strong_valid:
        score_s = 100
        sigs_s = ["型態", "籌碼", "趨勢"]
    
    # ═══════════════════════════════════════
    #  系統四：題材熱股（必備 6 條件）
    # ═══════════════════════════════════════
    score_t = 0
    sigs_t = []
    
    # 必備條件檢查
    t1 = False  # hot_industries 在主函數中判定
    t2 = ma_bull3
    t3 = vol_ratio_20d >= 1.5  # 爆量 ≥ 1.5x
    t4 = over_prev_h
    t5 = vol_ratio_prev >= 1.0  # 今日量 > 昨日量
    t6 = is_new_high_20  # 創新高確認
    
    theme_valid = t1 and t2 and t3 and t4 and t5 and t6  # t1 需要外部判定
    
    if theme_valid:
        score_t = 100
        sigs_t = ["型態", "籌碼", "趨勢", "題材"]
    
    # ═══════════════════════════════════════
    #  決定最終結果
    # ═══════════════════════════════════════
    if breakout_valid and score_b >= 65:
        result_entry = "盤整突破"
        result_score = score_b
        result_sigs = sigs_b
    elif pullback_valid and score_p >= 65:
        result_entry = "回後買上漲"
        result_score = score_p
        result_sigs = sigs_p
    elif strong_valid and score_s >= 60:
        result_entry = "強勢上漲"
        result_score = score_s
        result_sigs = sigs_s
    elif theme_valid and score_t >= 55:
        result_entry = "題材熱股"
        result_score = score_t
        result_sigs = sigs_t
    else:
        return None
    
    return {
        "code": stock_id,
        "name": stock_name,
        "price": round(price, 1),
        "chg": round(chg, 2),
        "score": result_score,
        "signals": list(dict.fromkeys(result_sigs)),
        "entry": result_entry,
        "prev_close": round(prev_close, 1),
        "prev_vol": int(prev_vol),
        "volume": int(vol),
        "avg_price_5d": round(avg_price_5d, 1),
        "upper_shadow_pct": round(upper_shadow_pct, 2),
        "vol_ma5": round(vol_ma5, 0),
    }

def run_screener(date=None, max_workers=3):
    today = date or datetime.today().strftime("%Y-%m-%d")
    log.info(f"開始掃描 {today}")
    
    universe = get_stock_universe()
    if universe.empty:
        log.error("❌ 無法取得股票清單")
        return []
    
    candidates = []
    seen_codes = set()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, row in universe.iterrows():
            stock_id = str(row["stock_id"])
            if stock_id in seen_codes:
                continue
            seen_codes.add(stock_id)
            
            stock_name = str(row.get("stock_name", stock_id))
            industry = classify_industry(row.get("industry_category", ""))
            
            future = executor.submit(fetch_stock_data, stock_id, today)
            futures.append((stock_id, stock_name, industry, future))
        
        # 熱門產業偵測
        all_industries = {}
        for _, _, ind, _ in futures:
            all_industries[ind] = all_industries.get(ind, 0) + 1
        
        hot_inds = sorted(all_industries.items(), key=lambda x: x[1], reverse=True)[:3]
        hot_industry_names = [x[0] for x in hot_inds]
        
        for i, (stock_id, stock_name, industry, future) in enumerate(futures):
            df = future.result()
            if df.empty:
                continue
            
            result = analyze_stock(stock_id, stock_name, industry, df, today)
            
            # 題材熱股判定
            if result and industry in hot_industry_names:
                if result["entry"] != "題材熱股":
                    result["entry"] = "題材熱股"
                    result["signals"].append("題材")
            
            if result:
                candidates.append(result)
            
            if (i + 1) % 50 == 0:
                log.info(f"進度: {i+1}/{len(futures)}，目前找到 {len(candidates)} 檔")
    
    candidates.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"✅ 完成！共 {len(candidates)} 檔候選")
    return candidates

def main():
    today = datetime.today().strftime("%Y-%m-%d")
    candidates = run_screener(today)
    with open(f"result_{today}.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "candidates": candidates}, f, ensure_ascii=False, indent=2)
    print(f"✅ 完成！{len(candidates)} 檔")

if __name__ == "__main__":
    main()
