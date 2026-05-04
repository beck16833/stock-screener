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
    "min_consolidation_days": 10,
    "min_volume_ratio"      : 1.0,
    "min_score"             : 55,
    "min_price"             : 10,      # 過濾低價股
    "min_volume_daily"      : 500,  # 最低日均量（張）
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
    listed = fm_get("TaiwanStockInfo")

    if listed.empty:
        log.error("無法取得股票清單")
        return pd.DataFrame()

    # 過濾：只保留普通股（排除 ETF、特別股、權證等）
    if "type" in listed.columns:
        listed = listed[listed["type"].isin(["twse", "tpex"])]

    # 排除代號含字母的（權證、ETF等）
    if "stock_id" in listed.columns:
        listed = listed[listed["stock_id"].str.match(r'^\d{4}$', na=False)]

    log.info(f"共取得 {len(listed)} 檔股票")
    return listed


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

    # 均線計算
    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    latest = df.iloc[-1]

    try:
        ma_bull4 = (latest["ma5"] > latest["ma10"] > latest["ma20"] > latest["ma60"]
                    and latest["close"] > latest["ma5"])
        ma_bull3 = (latest["ma5"] > latest["ma10"] > latest["ma20"]
                    and latest["close"] > latest["ma5"])
    except:
        return None

    # 共用指標
    vol_ratio    = latest["volume"] / vol_ma20 if vol_ma20 > 0 else 0
    high20       = df["close"].iloc[-21:-1].max()
    prev_high    = float(prev["high"])
    over_prev_h  = latest["close"] > prev_high
    is_breakout  = latest["close"] > high20
    body_pct     = (latest["close"] - latest["open"]) / latest["open"] * 100 if latest["open"] > 0 else 0
    mom5         = (latest["close"] / df.iloc[-6]["close"] - 1) * 100 if len(df) >= 6 else 0

    # 底部打底天數
    recent60 = df["close"].iloc[-61:-1]
    base     = recent60.median()
    in_range = ((recent60 >= base * 0.92) & (recent60 <= base * 1.08))
    run = max_run = 0
    for v in in_range:
        run = run + 1 if v else 0
        max_run = max(max_run, run)
    consolidation_days = max_run

    # 回檔計算：從近20日高點回落幅度
    recent20_high = df["high"].iloc[-21:-1].max()
    pullback_pct  = (recent20_high - latest["close"]) / recent20_high * 100 if recent20_high > 0 else 0
    # 支撐不破：收盤未跌破 20MA 且未跌破前波低點
    recent10_low  = df["low"].iloc[-11:-1].min()
    above_ma20    = latest["close"] > latest["ma20"]
    support_hold  = above_ma20 and latest["close"] > recent10_low

    # ═══════════════════════════════════════
    #  系統一：盤整突破評分（滿分100）
    # ═══════════════════════════════════════
    score_b  = 0
    sigs_b   = []

    # 條件1：底部打底 ≥ 20天（地基紮實）—— 核心條件
    if consolidation_days >= 20:
        score_b += 35
        sigs_b.append("型態")
    elif consolidation_days >= 10:
        score_b += 18
        sigs_b.append("型態")

    # 條件2：突破近20日高點 —— 核心條件
    if is_breakout:
        score_b += 30
        if "型態" not in sigs_b:
            sigs_b.append("型態")

    # 條件3：過昨日最高點（確認突破有效）
    if over_prev_h:
        score_b += 20

    # 條件4：爆量 ≥ 1.5x（主力進場）
    if vol_ratio >= 1.5:
        score_b += 20
        sigs_b.append("籌碼")
    elif vol_ratio >= 1.2:
        score_b += 10
        sigs_b.append("籌碼")

    # 條件5：陽線實體 ≥ 1.5%
    if body_pct >= 2.0:
        score_b += 10
    elif body_pct >= 1.5:
        score_b += 5

    # 條件6：均線多頭加分
    if ma_bull4:
        score_b += 10
        sigs_b.append("趨勢")
    elif ma_bull3:
        score_b += 5
        sigs_b.append("趨勢")

    # 動能加分
    if mom5 >= 3:
        sigs_b.append("動能")

    # 盤整突破必要條件：底部打底 + 突破 + 過昨高，三者缺一不可
    breakout_valid = (consolidation_days >= 20 and is_breakout and over_prev_h)

    # ═══════════════════════════════════════
    #  系統二：回後買上漲評分（滿分100）
    # ═══════════════════════════════════════
    score_p  = 0
    sigs_p   = []

    # 條件1：均線多頭排列 —— 核心條件（趨勢必須健康）
    if ma_bull4:
        score_p += 30
        sigs_p.append("趨勢")
    elif ma_bull3:
        score_p += 20
        sigs_p.append("趨勢")
    else:
        score_p = 0  # 無趨勢直接不符合

    # 條件2：支撐不破（收盤 > 20MA，未跌破前波低點）
    if support_hold:
        score_p += 25
        sigs_p.append("型態")

    # 條件3：過昨日最高點（確認反彈啟動）—— 核心條件
    if over_prev_h:
        score_p += 20

    # 條件4：量縮回檔後今日放量（回檔量縮 + 今日量增）
    vol_ma5_prev = df["volume"].iloc[-6:-1].mean()
    vol_shrink   = vol_ma5_prev < vol_ma20 * 0.8   # 近5日均量 < 20日均量80%（量縮）
    vol_expand   = latest["volume"] > vol_ma5_prev  # 今日量 > 近5日均量（量增）
    if vol_shrink and vol_expand:
        score_p += 15
        sigs_p.append("籌碼")
    elif vol_shrink:
        score_p += 8

    # 條件5：5日動能轉正
    if mom5 >= 1:
        score_p += 10
        sigs_p.append("動能")
    elif mom5 > 0:
        score_p += 5

    # 回後買上漲必要條件：有趨勢 + 支撐不破 + 過昨高
    pullback_valid = (ma_bull3 and support_hold and over_prev_h)

    # ═══════════════════════════════════════
    #  決定最終結果
    # ═══════════════════════════════════════
    MIN_SCORE = CRITERIA["min_score"]  # 65

    result_entry  = None
    result_score  = 0
    result_sigs   = []

    if breakout_valid and score_b >= MIN_SCORE:
        result_entry = "盤整突破"
        result_score = min(score_b, 100)
        result_sigs  = sigs_b
    elif pullback_valid and score_p >= MIN_SCORE:
        result_entry = "回後買上漲"
        result_score = min(score_p, 100)
        result_sigs  = sigs_p
    else:
        return None  # 兩種型態都不符合，直接排除

    chg = (latest["close"] / prev["close"] - 1) * 100 if prev["close"] > 0 else 0

    return {
        "code"              : stock_id,
        "price"             : round(float(latest["close"]), 1),
        "chg"               : round(chg, 2),
        "score"             : result_score,
        "signals"           : list(dict.fromkeys(result_sigs)),  # 去重保序
        "consolidation_days": int(consolidation_days),
        "vol_ratio"         : round(vol_ratio, 2),
        "momentum_5d"       : round(mom5, 2),
        "entry"             : result_entry,
        "ma_bull4"          : bool(ma_bull4),
        "details"           : {
            "breakout"      : bool(is_breakout),
            "over_prev_high": bool(over_prev_h),
            "support_hold"  : bool(support_hold),
            "pullback_pct"  : round(pullback_pct, 2),
            "body_pct"      : round(body_pct, 2),
        }
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
