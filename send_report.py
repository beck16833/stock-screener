"""
飆股雷達 v3 - 第一版介面 + 全市場掃描 + 玩股網連結
產出: 本地互動 HTML + Email 報告 + index.html（GitHub Pages 用）
"""

import os
import json
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from stock_screener import run_screener, INDUSTRY_MAP

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

EMAIL_CONFIG = {
    "sender"  : os.getenv("EMAIL_SENDER", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "receiver": os.getenv("EMAIL_RECEIVER", ""),
    "smtp"    : "smtp.gmail.com",
    "port"    : 587,
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CAP_ORDER      = ["大型股", "中型股", "小型股", "微型股"]
INDUSTRY_ORDER = list(INDUSTRY_MAP.keys())


def build_html(candidates: list, date: str) -> str:
    weekday   = ["一","二","三","四","五","六","日"][datetime.strptime(date, "%Y-%m-%d").weekday()]
    data_json = json.dumps(candidates, ensure_ascii=False)

    industries = sorted(
        set(s["industry"] for s in candidates),
        key=lambda x: INDUSTRY_ORDER.index(x) if x in INDUSTRY_ORDER else 99
    )
    cap_sizes = [c for c in CAP_ORDER if any(s["cap_size"] == c for s in candidates)]

    ind_btns = "".join(
        f'<button class="toggle-btn" data-type="industry" data-val="{i}" onclick="toggleFilter(this)">{i}</button>'
        for i in industries
    )
    cap_btns = "".join(
        f'<button class="toggle-btn" data-type="cap" data-val="{c}" onclick="toggleFilter(this)">{c}</button>'
        for c in cap_sizes
    )
    ind_options = "".join(
        f'<option value="{i}">{i}</option>' for i in industries
    )

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>飆股雷達｜{date}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0c0f;--surface:#111418;--surface2:#181c22;--border:#222830;
  --accent:#f0b429;--green:#38a169;--red:#e53e3e;--blue:#4299e1;
  --text:#e2e8f0;--muted:#718096;--dim:#4a5568;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Noto Sans TC',sans-serif;min-height:100vh}}
body::before{{content:'';position:fixed;inset:0;pointer-events:none;z-index:100;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.03) 2px,rgba(0,0,0,.03) 4px)}}
header{{border-bottom:1px solid var(--border);padding:20px 32px;display:flex;align-items:center;
  justify-content:space-between;position:sticky;top:0;background:rgba(10,12,15,.95);
  backdrop-filter:blur(12px);z-index:50}}
.logo{{display:flex;align-items:center;gap:12px}}
.logo-icon{{width:36px;height:36px;background:var(--accent);
  clip-path:polygon(50% 0%,100% 100%,0% 100%);animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.8;transform:scale(.95)}}}}
.logo-text{{font-size:20px;font-weight:900;letter-spacing:2px;color:var(--accent)}}
.logo-sub{{font-size:11px;color:var(--muted);letter-spacing:3px;font-family:'JetBrains Mono',monospace;margin-top:2px}}
.header-right{{display:flex;align-items:center;gap:12px}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:12px;padding:4px 12px;border-radius:2px;border:1px solid}}
.badge-muted{{color:var(--muted);border-color:var(--border)}}
.badge-accent{{color:var(--accent);border-color:rgba(240,180,41,.4)}}
main{{max-width:1400px;margin:0 auto;padding:32px}}
.sec-title{{font-size:11px;letter-spacing:4px;color:var(--muted);text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:16px;display:flex;align-items:center;gap:12px}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--border)}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px}}
.grid5{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:32px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:20px;
  position:relative;overflow:hidden;transition:border-color .2s,transform .2s}}
.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--accent);transform:scaleX(1);transform-origin:left}}
.card-num{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);letter-spacing:2px;margin-bottom:8px}}
.card-title{{font-size:15px;font-weight:700;margin-bottom:6px}}
.card-title-sm{{font-size:13px;font-weight:700;margin-bottom:6px}}
.card-desc{{font-size:12px;color:var(--muted);line-height:1.6}}
.card-dot{{position:absolute;bottom:16px;right:16px;width:8px;height:8px;border-radius:50%;
  background:var(--accent);box-shadow:0 0 8px var(--accent)}}
.filter-panel{{background:var(--surface);border:1px solid var(--border);border-radius:4px;
  padding:24px;margin-bottom:32px}}
.filters-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}}
.filter-group{{display:flex;flex-direction:column;gap:8px}}
.filter-label{{font-size:11px;color:var(--muted);letter-spacing:1px;display:flex;align-items:center;gap:6px}}
.dot{{width:6px;height:6px;border-radius:50%}}
.f-select{{background:var(--surface2);border:1px solid var(--border);border-radius:2px;
  color:var(--text);font-family:'Noto Sans TC',sans-serif;font-size:12px;
  padding:6px 10px;width:100%;outline:none;cursor:pointer;transition:border-color .2s}}
.f-select:focus{{border-color:var(--accent)}}
.f-input{{background:var(--surface2);border:1px solid var(--border);border-radius:2px;
  color:var(--text);font-family:'JetBrains Mono',monospace;font-size:12px;
  padding:6px 10px;width:100%;outline:none;transition:border-color .2s}}
.f-input:focus{{border-color:var(--accent)}}
.toggle-row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;padding-top:14px;
  border-top:1px solid var(--border);align-items:center}}
.toggle-label{{font-size:11px;color:var(--muted);margin-right:4px;white-space:nowrap}}
.toggle-btn{{font-family:'Noto Sans TC',sans-serif;font-size:11px;padding:5px 12px;
  border-radius:2px;border:1px solid var(--border);background:transparent;
  color:var(--muted);cursor:pointer;transition:all .2s}}
.toggle-btn:hover{{border-color:var(--dim);color:var(--text)}}
.toggle-btn.on{{background:rgba(240,180,41,.12);border-color:rgba(240,180,41,.5);color:var(--accent)}}
.results-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.results-count{{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--muted)}}
.results-count span{{color:var(--accent);font-weight:700}}
.table-wrap{{background:var(--surface);border:1px solid var(--border);border-radius:4px;overflow:hidden}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead{{background:var(--surface2);border-bottom:1px solid var(--border)}}
th{{padding:12px 14px;text-align:left;font-size:10px;letter-spacing:2px;color:var(--muted);
  font-weight:500;white-space:nowrap;cursor:pointer;user-select:none;transition:color .2s}}
th:hover{{color:var(--text)}}
th.asc::after{{content:' ▲';color:var(--accent)}}
th.desc::after{{content:' ▼';color:var(--accent)}}
tbody tr{{border-bottom:1px solid rgba(34,40,48,.6);transition:background .15s}}
tbody tr:hover{{background:rgba(240,180,41,.04)}}
tbody tr:last-child{{border-bottom:none}}
td{{padding:12px 14px;white-space:nowrap}}
.stock-link{{text-decoration:none;display:block}}
.stock-code{{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:14px;color:#63b3ed}}
.stock-name{{font-size:11px;color:var(--muted);margin-top:2px}}
.stock-link:hover .stock-code{{color:#90cdf4;text-decoration:underline}}
.price{{font-family:'JetBrains Mono',monospace;font-weight:700}}
.up{{color:#fc8181}}.down{{color:#68d391}}
.score-wrap{{display:flex;align-items:center;gap:6px}}
.score-bar{{height:4px;background:var(--border);border-radius:2px;width:70px;overflow:hidden}}
.score-fill{{height:100%;border-radius:2px}}
.score-num{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;min-width:24px}}
.signals{{display:flex;gap:3px;flex-wrap:wrap}}
.sig{{font-size:10px;padding:2px 6px;border-radius:2px;font-weight:600;letter-spacing:.5px}}
.sig-型態{{background:#dbeafe;color:#1d4ed8;border:1px solid #93c5fd}}
.sig-籌碼{{background:#fef9c3;color:#92400e;border:1px solid #fcd34d}}
.sig-趨勢{{background:#dcfce7;color:#15803d;border:1px solid #86efac}}
.sig-動能{{background:#f3e8ff;color:#7e22ce;border:1px solid #d8b4fe}}
.sig-題材{{background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}}
.tag{{display:inline-block;font-size:10px;padding:2px 7px;border-radius:2px;font-weight:500}}
.tag-ind{{background:rgba(66,153,225,.12);color:#63b3ed;border:1px solid rgba(66,153,225,.2)}}
.tag-大型股{{background:rgba(240,180,41,.12);color:#f6c650;border:1px solid rgba(240,180,41,.25)}}
.tag-中型股{{background:rgba(56,161,105,.12);color:#68d391;border:1px solid rgba(56,161,105,.25)}}
.tag-小型股{{background:rgba(159,122,234,.12);color:#b794f4;border:1px solid rgba(159,122,234,.25)}}
.tag-微型股{{background:rgba(113,128,150,.12);color:#a0aec0;border:1px solid rgba(113,128,150,.25)}}
.e-break{{color:#68d391;font-size:12px;font-weight:600}}
.e-pull{{color:#63b3ed;font-size:12px;font-weight:600}}
.e-wait{{color:var(--muted);font-size:12px}}
.empty{{text-align:center;padding:48px;color:var(--muted);font-size:13px}}
.legend{{display:flex;gap:20px;margin-top:14px;padding-top:14px;border-top:1px solid var(--border);flex-wrap:wrap}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}}
.ops-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}}
.ops-card{{background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:22px}}
.ops-label{{font-size:11px;letter-spacing:2px;font-family:'JetBrains Mono',monospace;margin-bottom:14px}}
.ops-item{{display:flex;gap:10px;align-items:flex-start;margin-bottom:12px}}
.ops-item:last-child{{margin-bottom:0}}
.ops-num{{min-width:26px;height:26px;border-radius:2px;display:flex;align-items:center;
  justify-content:center;font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:700}}
.ops-t{{font-weight:600;font-size:13px;margin-bottom:3px}}
.ops-d{{font-size:12px;color:var(--muted);line-height:1.6}}
.run-btn{{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;
  padding:14px;margin-top:20px;background:var(--accent);color:#0a0c0f;
  font-family:'Noto Sans TC',sans-serif;font-weight:700;font-size:14px;letter-spacing:3px;
  border:none;border-radius:2px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}}
.run-btn::after{{content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);
  transform:translateX(-100%);transition:transform .4s}}
.run-btn:hover::after{{transform:translateX(100%)}}
.run-btn:hover{{background:#f7c948;box-shadow:0 0 24px rgba(240,180,41,.3)}}
@media(max-width:1100px){{.grid3{{grid-template-columns:repeat(2,1fr)}}.filters-grid{{grid-template-columns:repeat(2,1fr)}}.ops-grid{{grid-template-columns:1fr}}}}
@media(max-width:700px){{.grid3,.grid5{{grid-template-columns:1fr}}main{{padding:16px}}}}
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon"></div>
    <div>
      <div class="logo-text">飆股雷達</div>
      <div class="logo-sub">FULL MARKET SCREENER</div>
    </div>
  </div>
  <div class="header-right">
    <div class="badge badge-muted">{date}（週{weekday}）</div>
    <div class="badge badge-accent" id="hdrCount">載入中...</div>
  </div>
</header>
<main>

<div class="sec-title">三大先決條件</div>
<div class="grid3">
  <div class="card"><div class="card-num">01 / 基礎型態</div>
    <div class="card-title">底部長期打底</div>
    <div class="card-desc">股價在底部盤整超過 20 個交易日，地基紮實，蓄積能量等待爆發。</div>
    <div class="card-dot"></div></div>
  <div class="card"><div class="card-num">02 / 籌碼動能</div>
    <div class="card-title">底部爆出大量</div>
    <div class="card-desc">低檔出現成交量明顯放大（≥ 近期均量 1.5 倍），主力建倉訊號。</div>
    <div class="card-dot"></div></div>
  <div class="card"><div class="card-num">03 / 趨勢確認</div>
    <div class="card-title">均線多頭排列</div>
    <div class="card-desc">5、10、20、60MA 向上發散，股價站穩所有均線之上，趨勢正式啟動。</div>
    <div class="card-dot"></div></div>
</div>

<div class="sec-title">五大關鍵訊號</div>
<div class="grid5">
  <div class="card" style="border-left:2px solid #4299e1"><div class="card-num" style="color:#4299e1">型態</div>
    <div class="card-title-sm">杯離 / 底部盤整</div><div class="card-desc">Cup & Handle 或長底突破</div><div class="card-dot"></div></div>
  <div class="card" style="border-left:2px solid #f6c650"><div class="card-num" style="color:#f6c650">籌碼</div>
    <div class="card-title-sm">主力連續買超</div><div class="card-desc">底部巨量，法人同步介入</div><div class="card-dot"></div></div>
  <div class="card" style="border-left:2px solid #68d391"><div class="card-num" style="color:#68d391">趨勢</div>
    <div class="card-title-sm">均線多頭排列</div><div class="card-desc">三線或四線多排，勝率最高</div><div class="card-dot"></div></div>
  <div class="card" style="border-left:2px solid #fc8181"><div class="card-num" style="color:#fc8181">題材</div>
    <div class="card-title-sm">市場熱門主題</div><div class="card-desc">AI / 新技術 / 政策受惠</div><div class="card-dot"></div></div>
  <div class="card" style="border-left:2px solid #b794f4"><div class="card-num" style="color:#b794f4">動能</div>
    <div class="card-title-sm">第一波強勢領漲</div><div class="card-desc">類股龍頭，起漲優於大盤</div><div class="card-dot"></div></div>
</div>

<div class="sec-title">篩選條件設定</div>
<div class="filter-panel">
  <div class="filters-grid">
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#4299e1"></span>型態篩選</div>
      <select class="f-select" id="f-pattern" onchange="render()">
        <option value="">全部</option>
        <option value="盤整突破">盤整突破</option>
        <option value="回後買上漲">回後買上漲</option>
      </select>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#68d391"></span>均線多頭排列</div>
      <select class="f-select" id="f-ma" onchange="render()">
        <option value="">全部</option>
        <option value="四線多排">四線多排（5/10/20/60）</option>
        <option value="有趨勢">三線多排（5/10/20）</option>
      </select>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#f6c650"></span>成交量條件</div>
      <div style="display:flex;align-items:center;gap:8px">
        <input class="f-input" type="number" id="f-vol" value="1" min="1" step="0.1" onchange="render()" style="width:80px"> 倍均量
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#b794f4"></span>底部打底天數</div>
      <div style="display:flex;align-items:center;gap:8px">
        <input class="f-input" type="number" id="f-days" value="0" min="0" onchange="render()" style="width:80px"> 天以上
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#fc8181"></span>最低飆股評分</div>
      <input class="f-input" type="number" id="f-score" value="65" min="0" max="100" onchange="render()">
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#4299e1"></span>市值規模</div>
      <select class="f-select" id="f-cap" onchange="render()">
        <option value="">全部</option>
        <option value="大型股">大型股</option>
        <option value="中型股">中型股</option>
        <option value="小型股">小型股</option>
        <option value="微型股">微型股</option>
      </select>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#68d391"></span>進場策略</div>
      <select class="f-select" id="f-entry" onchange="render()">
        <option value="">全部</option>
        <option value="盤整突破">盤整突破</option>
        <option value="回後買上漲">回後買上漲</option>
        <option value="觀察等待">觀察等待</option>
      </select>
    </div>
    <div class="filter-group">
      <div class="filter-label"><span class="dot" style="background:#f6c650"></span>產業別</div>
      <select class="f-select" id="f-ind" onchange="render()">
        <option value="">全部產業</option>
        {ind_options}
      </select>
    </div>
  </div>

  <div class="toggle-row">
    <span class="toggle-label">附加條件：</span>
    <button class="toggle-btn on" data-extra="new_high" onclick="toggleExtra(this)">股價創20日新高</button>
    <button class="toggle-btn on" data-extra="ma_bull4" onclick="toggleExtra(this)">均線四線多排</button>
    <button class="toggle-btn" data-extra="breakout_vol" onclick="toggleExtra(this)">突破量 ≥ 2倍</button>
    <button class="toggle-btn" data-extra="momentum" onclick="toggleExtra(this)">5日動能 ≥ 3%</button>
  </div>

  <div class="toggle-row">
    <span class="toggle-label">訊號篩選：</span>
    <button class="toggle-btn" data-sig="型態" onclick="toggleSig(this)">型態</button>
    <button class="toggle-btn" data-sig="籌碼" onclick="toggleSig(this)">籌碼</button>
    <button class="toggle-btn" data-sig="趨勢" onclick="toggleSig(this)">趨勢</button>
    <button class="toggle-btn" data-sig="動能" onclick="toggleSig(this)">動能</button>
  </div>

  <button class="run-btn" onclick="render()">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    套用篩選條件
  </button>
</div>

<div class="results-hdr">
  <div class="sec-title" style="margin-bottom:0">選股結果</div>
  <div class="results-count">找到 <span id="cnt">-</span> 檔候選標的</div>
</div>
<div class="table-wrap">
  <table>
    <thead><tr>
      <th onclick="sortBy('code',this)">代號 / 名稱</th>
      <th onclick="sortBy('price',this)">現價</th>
      <th onclick="sortBy('chg',this)">漲跌</th>
      <th onclick="sortBy('score',this)">飆股評分</th>
      <th>五大訊號</th>
      <th>產業</th>
      <th>市值</th>
      <th onclick="sortBy('consolidation_days',this)">打底天數</th>
      <th onclick="sortBy('vol_ratio',this)">爆量倍數</th>
      <th>進場策略</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<div class="legend">
  <div class="legend-item"><span class="sig sig-型態">型態</span>底部盤整或杯離突破</div>
  <div class="legend-item"><span class="sig sig-籌碼">籌碼</span>主力法人連續買超</div>
  <div class="legend-item"><span class="sig sig-趨勢">趨勢</span>均線多頭排列</div>
  <div class="legend-item"><span class="sig sig-動能">動能</span>強勢領漲</div>
</div>

<div style="margin-top:48px">
  <div class="sec-title">操作執行準則</div>
  <div class="ops-grid">
    <div class="ops-card">
      <div class="ops-label" style="color:var(--green)">▲ 進場點</div>
      <div class="ops-item">
        <div class="ops-num" style="background:rgba(56,161,105,.15);border:1px solid rgba(56,161,105,.3);color:var(--green)">01</div>
        <div><div class="ops-t">盤整突破（發動點）</div><div class="ops-d">股價跳空或長紅突破盤整壓力區，搭配成交量放大確認。</div></div>
      </div>
      <div class="ops-item">
        <div class="ops-num" style="background:rgba(56,161,105,.15);border:1px solid rgba(56,161,105,.3);color:var(--green)">02</div>
        <div><div class="ops-t">回後買上漲</div><div class="ops-d">多頭趨勢中回檔量縮，支撐不破後重新向上，第二次進場機會。</div></div>
      </div>
    </div>
    <div class="ops-card">
      <div class="ops-label" style="color:var(--red)">▼ 出場點</div>
      <div class="ops-item">
        <div class="ops-num" style="background:rgba(229,62,62,.12);border:1px solid rgba(229,62,62,.3);color:var(--red)">S1</div>
        <div><div class="ops-t">短線：收盤跌破 5MA</div><div class="ops-d">小賠大賺，不戀棧。收盤跌破五日均線即出清。</div></div>
      </div>
      <div class="ops-item">
        <div class="ops-num" style="background:rgba(229,62,62,.12);border:1px solid rgba(229,62,62,.3);color:var(--red)">S2</div>
        <div><div class="ops-t">波段：收盤跌破 20MA</div><div class="ops-d">趨勢維持則持有。出現「頭頭低」或跌破前波低點果斷離場。</div></div>
      </div>
    </div>
  </div>
</div>

</main>
<script>
const ALL = {data_json};
let sKey='score', sDir=-1, actSigs=new Set(), actExtras=new Set(['new_high','ma_bull4']);

const sc = n => n>=90?'#38a169':n>=80?'#ca8a04':'#dc2626';

function getFiltered(){{
  const ms  = +document.getElementById('f-score').value||0;
  const mv  = +document.getElementById('f-vol').value||1;
  const md  = +document.getElementById('f-days').value||0;
  const ef  = document.getElementById('f-entry').value;
  const mf  = document.getElementById('f-ma').value;
  const pf  = document.getElementById('f-pattern').value;
  const cf  = document.getElementById('f-cap').value;
  const inf = document.getElementById('f-ind').value;
  return ALL.filter(s=>{{
    if(s.score<ms) return false;
    if(s.vol_ratio<mv) return false;
    if(s.consolidation_days<md) return false;
    if(ef && s.entry!==ef) return false;
    if(pf && s.entry!==pf) return false;
    if(mf==='四線多排' && !s.ma_bull4) return false;
    if(mf==='有趨勢' && !s.signals.includes('趨勢')) return false;
    if(cf && s.cap_size!==cf) return false;
    if(inf && s.industry!==inf) return false;
    if(actExtras.has('new_high') && !(s.details&&s.details.breakout)) return false;
    if(actExtras.has('ma_bull4') && !s.ma_bull4) return false;
    if(actExtras.has('breakout_vol') && s.vol_ratio<2) return false;
    if(actExtras.has('momentum') && s.momentum_5d<3) return false;
    if(actSigs.size>0 && ![...actSigs].some(sig=>s.signals.includes(sig))) return false;
    return true;
  }}).sort((a,b)=>{{
    const va=a[sKey],vb=b[sKey];
    return(typeof va==='number'?(va-vb):(String(va).localeCompare(String(vb))))*sDir;
  }});
}}

function render(){{
  const data=getFiltered();
  document.getElementById('cnt').textContent=data.length;
  document.getElementById('hdrCount').textContent=data.length+' 檔';
  const tbody=document.getElementById('tbody');
  if(!data.length){{tbody.innerHTML='<tr><td colspan="10" class="empty">無符合條件的標的</td></tr>';return;}}
  tbody.innerHTML=data.map(s=>{{
    const chgStr=(s.chg>=0?'+':'')+s.chg+'%';
    const ec=s.entry==='盤整突破'?'e-break':s.entry==='回後買上漲'?'e-pull':'e-wait';
    const sigs=s.signals.map(sig=>`<span class="sig sig-${{sig}}">${{sig}}</span>`).join('');
    return `<tr>
      <td><a class="stock-link" href="https://www.wantgoo.com/stock/${{s.code}}" target="_blank">
        <div class="stock-code">${{s.code}}</div><div class="stock-name">${{s.name}}</div>
      </a></td>
      <td><span class="price ${{s.chg>=0?'up':'down'}}">${{s.price.toLocaleString()}}</span></td>
      <td><span class="${{s.chg>=0?'up':'down'}}" style="font-family:monospace;font-weight:600">${{chgStr}}</span></td>
      <td><div class="score-wrap">
        <div class="score-bar"><div class="score-fill" style="width:${{s.score}}%;background:${{sc(s.score)}}"></div></div>
        <span class="score-num" style="color:${{sc(s.score)}}">${{s.score}}</span>
      </div></td>
      <td><div class="signals">${{sigs}}</div></td>
      <td><span class="tag tag-ind">${{s.industry}}</span></td>
      <td><span class="tag tag-${{s.cap_size}}">${{s.cap_size}}</span></td>
      <td style="font-family:monospace;font-size:12px;color:var(--muted)">${{s.consolidation_days}}天</td>
      <td style="font-family:monospace;font-size:12px;color:${{s.vol_ratio>=2?'#f6c650':'var(--muted)'}}">${{s.vol_ratio}}x</td>
      <td><span class="${{ec}}">${{s.entry}}</span></td>
    </tr>`;
  }}).join('');
}}

function toggleExtra(btn){{
  const key=btn.dataset.extra;
  if(actExtras.has(key)){{actExtras.delete(key);btn.classList.remove('on');}}
  else{{actExtras.add(key);btn.classList.add('on');}}
}}

function toggleSig(btn){{
  const sig=btn.dataset.sig;
  if(actSigs.has(sig)){{actSigs.delete(sig);btn.classList.remove('on');}}
  else{{actSigs.add(sig);btn.classList.add('on');}}
}}

function sortBy(key,th){{
  if(sKey===key)sDir*=-1;else{{sKey=key;sDir=-1;}}
  document.querySelectorAll('th').forEach(t=>t.classList.remove('asc','desc'));
  th.classList.add(sDir===-1?'desc':'asc');
  render();
}}

render();
</script>
</body></html>"""


def build_email_html(candidates: list, date: str) -> str:
    weekday = ["一","二","三","四","五","六","日"][datetime.strptime(date, "%Y-%m-%d").weekday()]
    by_ind  = {}
    for s in candidates:
        by_ind.setdefault(s["industry"], []).append(s)
    sorted_ind = sorted(by_ind.items(), key=lambda x: len(x[1]), reverse=True)

    def sig_html(sigs):
        bg = {"型態":"#dbeafe","籌碼":"#fef9c3","趨勢":"#dcfce7","動能":"#f3e8ff"}
        fc = {"型態":"#1d4ed8","籌碼":"#92400e","趨勢":"#15803d","動能":"#7e22ce"}
        return "".join(
            f'<span style="display:inline-block;padding:1px 6px;border-radius:2px;font-size:10px;'
            f'font-weight:600;margin:1px;background:{bg.get(s,"#f3f4f6")};color:{fc.get(s,"#374151")}">{s}</span>'
            for s in sigs)

    sections = ""
    for ind, stocks in sorted_ind[:12]:
        rows = ""
        for s in sorted(stocks, key=lambda x: x["score"], reverse=True)[:10]:
            cc = "#dc2626" if s["chg"] >= 0 else "#16a34a"
            cs = f"+{s['chg']}%" if s["chg"] >= 0 else f"{s['chg']}%"
            sc_c = "#16a34a" if s["score"] >= 90 else "#ca8a04" if s["score"] >= 80 else "#dc2626"
            ec = "#16a34a" if "突破" in s["entry"] else "#2563eb" if "買" in s["entry"] else "#6b7280"
            rows += f"""<tr style="border-bottom:1px solid #f3f4f6">
              <td style="padding:8px 10px"><a href="https://www.wantgoo.com/stock/{s['code']}" target="_blank"
                style="font-weight:700;font-size:13px;color:#2563eb;text-decoration:none">{s['code']}</a></td>
              <td style="padding:8px 10px;font-size:12px;color:#6b7280">{s['name']}</td>
              <td style="padding:8px 10px;font-family:monospace;font-weight:700">{s['price']:,}</td>
              <td style="padding:8px 10px;font-family:monospace;font-weight:600;color:{cc}">{cs}</td>
              <td style="padding:8px 10px;font-family:monospace;font-weight:700;color:{sc_c}">{s['score']}</td>
              <td style="padding:8px 10px">{sig_html(s['signals'])}</td>
              <td style="padding:8px 10px;font-size:11px;font-weight:600;color:{ec}">{s['entry']}</td>
            </tr>"""
        sections += f"""<div style="margin-bottom:24px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <span style="font-weight:700;font-size:14px;color:#111827">{ind}</span>
            <span style="background:#f3f4f6;border-radius:10px;padding:1px 9px;
              font-size:11px;color:#6b7280;font-family:monospace">{len(stocks)} 檔</span>
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:12px">
            <thead><tr style="background:#f8fafc;border-bottom:2px solid #e5e7eb">
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">代號</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">名稱</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">現價</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">漲跌</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">評分</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">訊號</th>
              <th style="padding:6px 10px;text-align:left;font-size:10px;color:#9ca3af">策略</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    return f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif">
<div style="max-width:680px;margin:28px auto;background:#fff;border-radius:10px;
     overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08)">
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px 28px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="font-size:20px;font-weight:900;color:#f0b429;letter-spacing:2px">飆股雷達</div>
        <div style="font-size:10px;color:#6b7280;letter-spacing:3px;margin-top:3px">FULL MARKET SCREENER</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:12px;color:#e5e7eb">{date}（週{weekday}）</div>
        <div style="font-size:28px;font-weight:900;color:#f0b429;margin-top:4px">{len(candidates)}</div>
        <div style="font-size:10px;color:#6b7280">檔候選 / {len(sorted_ind)} 個產業</div>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.1)">
      <div style="text-align:center">
        <div style="font-size:18px;font-weight:700;color:#f6c650;font-family:monospace">
          {sum(1 for s in candidates if s['entry']=='盤整突破')}</div>
        <div style="font-size:10px;color:#9ca3af">盤整突破</div>
      </div>
      <div style="text-align:center">
        <div style="font-size:18px;font-weight:700;color:#63b3ed;font-family:monospace">
          {sum(1 for s in candidates if s['entry']=='回後買上漲')}</div>
        <div style="font-size:10px;color:#9ca3af">回後買上漲</div>
      </div>
      <div style="text-align:center">
        <div style="font-size:18px;font-weight:700;color:#68d391;font-family:monospace">
          {sum(1 for s in candidates if s.get('ma_bull4'))}</div>
        <div style="font-size:10px;color:#9ca3af">四線多排</div>
      </div>
    </div>
  </div>
  <div style="padding:24px 28px">{sections}</div>
  <div style="padding:14px 28px;background:#f8fafc;border-top:1px solid #e5e7eb">
    <div style="font-size:10px;color:#9ca3af;line-height:1.8">
      ⚠️ 本報告自動產生，僅供參考，不構成投資建議。資料來源：FinMind 開源資料庫
    </div>
  </div>
</div></body></html>"""


def send_email(html: str, date: str, count: int):
    cfg = EMAIL_CONFIG
    if not cfg["password"] or not cfg["sender"]:
        log.warning("未設定 Email 帳密，跳過寄信")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📈 飆股雷達 {date} — {count} 檔候選 / 全市場掃描"
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["receiver"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(cfg["smtp"], cfg["port"]) as s:
            s.ehlo(); s.starttls()
            s.login(cfg["sender"], cfg["password"])
            s.sendmail(cfg["sender"], cfg["receiver"], msg.as_string())
        log.info(f"✅ Email 寄出至 {cfg['receiver']}")
    except Exception as e:
        log.error(f"❌ 寄信失敗: {e}")


def main():
    today = datetime.today().strftime("%Y-%m-%d")
    candidates = run_screener(today, max_workers=4)

    html = build_html(candidates, today)

    # 本地報告
    local_path = os.path.join(OUTPUT_DIR, f"report_{today}.html")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(html)

    # index.html（GitHub Pages 用）
    root_dir   = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(root_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"HTML 報告: {local_path}")
    log.info(f"index.html: {index_path}")

    # Email
    send_email(build_email_html(candidates, today), today, len(candidates))

    # JSON 備份
    with open(os.path.join(OUTPUT_DIR, f"result_{today}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today, "candidates": candidates}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共 {len(candidates)} 檔候選標的")
    print(f"   本地報告：{local_path}")
    print(f"   GitHub Pages：index.html 已更新")


if __name__ == "__main__":
    main()
