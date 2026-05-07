"""飆股雷達 HTML報告生成"""
import os, json, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from stock_screener import run_screener, INDUSTRY_MAP

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

EMAIL_CONFIG = {
    "sender": os.getenv("EMAIL_SENDER", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "receiver": os.getenv("EMAIL_RECEIVER", ""),
    "smtp": "smtp.gmail.com",
    "port": 587,
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def build_html(candidates, date):
    weekday = ["一","二","三","四","五","六","日"][datetime.strptime(date, "%Y-%m-%d").weekday()]
    data_json = json.dumps(candidates, ensure_ascii=False)
    
    industries = sorted(set(s["industry"] for s in candidates),
        key=lambda x: list(INDUSTRY_MAP.keys()).index(x) if x in INDUSTRY_MAP else 99)
    
    ind_options = "".join(f'<option value="{i}">{i}</option>' for i in industries)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>飆股雷達 {date}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0c0f;--surface:#111418;--surface2:#181c22;--border:#222830;--accent:#f0b429;--text:#e2e8f0;--muted:#718096;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Noto Sans TC',sans-serif;}}
header{{border-bottom:1px solid var(--border);padding:20px 32px;position:sticky;top:0;background:rgba(10,12,15,.95);z-index:50}}
.logo{{font-size:20px;font-weight:900;color:var(--accent)}}
main{{max-width:1600px;margin:0 auto;padding:32px}}
.sec-title{{font-size:11px;color:var(--muted);margin-bottom:16px}}
.filter-panel{{background:var(--surface);border:1px solid var(--border);padding:24px;margin-bottom:32px}}
.filters-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-bottom:20px}}
.filter-group{{display:flex;flex-direction:column;gap:8px}}
.f-select,.f-input{{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:8px;width:100%}}
.breakout-params{{display:none;background:rgba(240,180,41,.05);border:1px solid rgba(240,180,41,.2);border-radius:4px;padding:16px;margin-top:16px}}
.breakout-params.show{{display:block}}
.params-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.toggle-row{{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}}
.toggle-btn{{padding:6px 12px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer}}
.toggle-btn.on{{background:rgba(240,180,41,.12);border-color:var(--accent);color:var(--accent)}}
.run-btn{{width:100%;padding:14px;margin-top:20px;background:var(--accent);color:#0a0c0f;font-weight:700;border:none;cursor:pointer}}
.table-wrap{{background:var(--surface);border:1px solid var(--border);border-radius:4px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{padding:10px;text-align:left;font-size:11px;color:var(--muted);border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer}}
td{{padding:10px;border-bottom:1px solid rgba(34,40,48,.6)}}
.stock-link{{text-decoration:none;color:#63b3ed}}
.stock-link:hover{{text-decoration:underline}}
.sig{{display:inline-block;padding:2px 6px;font-size:10px;border-radius:2px;margin:1px}}
.sig-型態{{background:#dbeafe;color:#1d4ed8}}
.sig-籌碼{{background:#fef9c3;color:#92400e}}
.sig-趨勢{{background:#dcfce7;color:#15803d}}
.sig-動能{{background:#f3e8ff;color:#7e22ce}}
.sig-題材{{background:#fee2e2;color:#b91c1c}}
.ok{{color:#68d391;font-weight:600}}.ng{{color:#fc8181;font-weight:600}}
.up{{color:#fc8181}}.down{{color:#68d391}}
</style>
</head>
<body>
<header>
  <div class="logo">🎯 飆股雷達</div>
  <div style="font-size:12px;color:var(--muted);margin-top:4px">{date}（週{weekday}） • {len(candidates)} 檔</div>
</header>
<main>
<div class="sec-title">篩選條件</div>
<div class="filter-panel">
  <div class="filters-grid">
    <div>
      <label style="font-size:11px;color:var(--muted)">進場策略</label>
      <select class="f-select" id="f-entry" onchange="toggleBreakoutParams(); render()">
        <option value="">全部</option>
        <option value="盤整突破">盤整突破</option>
        <option value="回後買上漲">回後買上漲</option>
        <option value="強勢上漲">強勢上漲</option>
        <option value="題材熱股">題材熱股</option>
      </select>
    </div>
    <div>
      <label style="font-size:11px;color:var(--muted)">產業別</label>
      <select class="f-select" id="f-ind" onchange="render()">
        <option value="">全部</option>
        {ind_options}
      </select>
    </div>
    <div>
      <label style="font-size:11px;color:var(--muted)">市值規模</label>
      <select class="f-select" id="f-cap" onchange="render()">
        <option value="">全部</option>
        <option value="大型股">大型股</option>
        <option value="中型股">中型股</option>
        <option value="小型股">小型股</option>
        <option value="微型股">微型股</option>
      </select>
    </div>
    <div>
      <label style="font-size:11px;color:var(--muted)">最低評分</label>
      <input class="f-input" type="number" id="f-score" value="55" min="0" max="100" onchange="render()">
    </div>
  </div>
  
  <div id="breakoutParams" class="breakout-params">
    <div style="font-size:12px;font-weight:700;margin-bottom:12px;color:var(--accent)">盤整突破參數設定</div>
    <div class="params-grid">
      <div>
        <label style="font-size:11px;color:var(--muted)">近N日新高</label>
        <input class="f-input" type="number" id="p-high-days" value="20" min="5" max="60" onchange="render()">
      </div>
      <div>
        <label style="font-size:11px;color:var(--muted)">5日均量倍數</label>
        <input class="f-input" type="number" id="p-vol-5d" value="1.5" min="0.5" max="5" step="0.1" onchange="render()">
      </div>
      <div>
        <label style="font-size:11px;color:var(--muted)">上影線上限%</label>
        <input class="f-input" type="number" id="p-upper-shadow" value="2" min="0" max="10" step="0.5" onchange="render()">
      </div>
      <div>
        <label style="font-size:11px;color:var(--muted)">昨日量倍數</label>
        <input class="f-input" type="number" id="p-vol-prev" value="1.2" min="0.5" max="5" step="0.1" onchange="render()">
      </div>
    </div>
  </div>
  
  <div class="toggle-row">
    <span style="font-size:11px;color:var(--muted)">訊號篩選：</span>
    <button class="toggle-btn" data-sig="型態" onclick="toggleSig(this)">型態</button>
    <button class="toggle-btn" data-sig="籌碼" onclick="toggleSig(this)">籌碼</button>
    <button class="toggle-btn" data-sig="趨勢" onclick="toggleSig(this)">趨勢</button>
    <button class="toggle-btn" data-sig="動能" onclick="toggleSig(this)">動能</button>
    <button class="toggle-btn" data-sig="題材" onclick="toggleSig(this)">題材</button>
  </div>
  <button class="run-btn" onclick="render()">🔍 套用篩選</button>
</div>

<div style="margin-bottom:16px">
  <span style="font-size:13px">找到 <span id="cnt" style="color:var(--accent);font-weight:700">-</span> 檔候選</span>
</div>
<div class="table-wrap">
  <table>
    <thead><tr style="background:var(--surface2)">
      <th onclick="sortBy('code',this)" style="cursor:pointer">代號</th>
      <th>名稱</th>
      <th onclick="sortBy('prev_close',this)" style="cursor:pointer">昨日收盤</th>
      <th onclick="sortBy('prev_vol',this)" style="cursor:pointer">昨日量</th>
      <th onclick="sortBy('price',this)" style="cursor:pointer">今日收盤</th>
      <th onclick="sortBy('volume',this)" style="cursor:pointer">今日量</th>
      <th>5日均價</th>
      <th>漲跌%</th>
      <th>上影線%</th>
      <th>量比(vs5日)</th>
      <th>量比(vsYesterday)</th>
      <th onclick="sortBy('score',this)" style="cursor:pointer">評分</th>
      <th>訊號</th>
      <th>產業</th>
      <th>市值</th>
      <th>策略</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
</main>

<script>
const ALL = {data_json};
let sKey='score', sDir=-1, actSigs=new Set();

function toggleBreakoutParams() {{
  const entry = document.getElementById('f-entry').value;
  const panel = document.getElementById('breakoutParams');
  if(entry === '盤整突破') {{
    panel.classList.add('show');
  }} else {{
    panel.classList.remove('show');
  }}
}}

function getFiltered() {{
  const ms = +document.getElementById('f-score').value||0;
  const ef = document.getElementById('f-entry').value;
  const inf = document.getElementById('f-ind').value;
  const cf = document.getElementById('f-cap').value;
  
  // 盤整突破參數
  const highDays = +document.getElementById('p-high-days').value||20;
  const vol5d = +document.getElementById('p-vol-5d').value||1.5;
  const upperShadow = +document.getElementById('p-upper-shadow').value||2;
  const volPrev = +document.getElementById('p-vol-prev').value||1.2;
  
  return ALL.filter(s => {{
    if(s.score < ms) return false;
    if(ef && s.entry !== ef) return false;
    if(inf && s.industry !== inf) return false;
    if(cf && s.cap_size !== cf) return false;
    
    // 盤整突破硬篩選
    if(ef === '盤整突破') {{
      // 這裡需要從原始資料計算，但現在只有最終結果
      // 實際上需要在 stock_screener.py 傳回這些數據
      // 暫時用 entry 是否為盤整突破來判斷
      if(s.entry !== '盤整突破') return false;
    }}
    
    if(actSigs.size > 0) {{
      const hasAll = [...actSigs].every(sig => s.signals.includes(sig));
      if(!hasAll) return false;
    }}
    return true;
  }}).sort((a,b) => {{
    const va = a[sKey], vb = b[sKey];
    return (typeof va === 'number' ? va-vb : String(va).localeCompare(String(vb))) * sDir;
  }});
}}

function render() {{
  const data = getFiltered();
  document.getElementById('cnt').textContent = data.length;
  const tbody = document.getElementById('tbody');
  
  if(!data.length) {{
    tbody.innerHTML = '<tr><td colspan="16" style="text-align:center;padding:48px;color:var(--muted)">無符合條件</td></tr>';
    return;
  }}
  
  tbody.innerHTML = data.map(s => {{
    const chgStr = (s.chg>=0?'+':'') + s.chg + '%';
    const chgClass = s.chg>=0 ? 'up' : 'down';
    const sigs = s.signals.map(sig => `<span class="sig sig-${{sig}}">${{sig}}</span>`).join('');
    const url = `https://www.wantgoo.com/stock/${{s.code}}/technical-chart`;
    
    // 計算需要的欄位
    const prev_vol = s.prev_vol || 0;
    const vol_5d = s.vol_ma5 || 0;
    const vol_ratio_5d = vol_5d > 0 ? (s.volume / vol_5d).toFixed(2) : 'N/A';
    const vol_ratio_prev = prev_vol > 0 ? (s.volume / prev_vol).toFixed(2) : 'N/A';
    const upper_shadow = s.upper_shadow_pct || 0;
    const avg_price_5d = s.avg_price_5d || '-';
    
    return `<tr>
      <td><a class="stock-link" href="${{url}}" target="_blank">${{s.code}}</a></td>
      <td>${{s.name}}</td>
      <td>${{s.prev_close || '-'}}</td>
      <td>${{s.prev_vol ? s.prev_vol.toLocaleString() : '-'}}</td>
      <td><strong>${{s.price}}</strong></td>
      <td>${{s.volume.toLocaleString()}}</td>
      <td>${{avg_price_5d}}</td>
      <td class="${{chgClass}}">${{chgStr}}</td>
      <td>${{upper_shadow.toFixed(2)}}%</td>
      <td class="${{vol_ratio_5d >= 1.5 ? 'ok' : 'ng'}}">${{vol_ratio_5d}}</td>
      <td class="${{vol_ratio_prev >= 1.2 ? 'ok' : 'ng'}}">${{vol_ratio_prev}}</td>
      <td><strong>${{s.score}}</strong></td>
      <td>${{sigs}}</td>
      <td>${{s.industry}}</td>
      <td>${{s.cap_size}}</td>
      <td>${{s.entry}}</td>
    </tr>`;
  }}).join('');
}}

function toggleSig(btn) {{
  const sig = btn.dataset.sig;
  if(actSigs.has(sig)) {{
    actSigs.delete(sig);
    btn.classList.remove('on');
  }} else {{
    actSigs.add(sig);
    btn.classList.add('on');
  }}
  render();
}}

function sortBy(key, th) {{
  if(sKey === key) sDir *= -1;
  else {{ sKey = key; sDir = -1; }}
  document.querySelectorAll('th').forEach(t => t.textContent = t.textContent.replace(/ [▲▼]/, ''));
  th.textContent += sDir === -1 ? ' ▼' : ' ▲';
  render();
}}

render();
</script>
</body></html>"""
    return html

def build_email_html(candidates, date):
    return f"""<html><body style="font-family:Arial;background:#f9fafb">
<div style="max-width:680px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden">
  <div style="background:#1a1a2e;color:#f0b429;padding:20px;text-align:center">
    <div style="font-size:24px;font-weight:900">飆股雷達</div>
    <div style="font-size:12px;margin-top:8px">{date} • {len(candidates)}檔候選</div>
  </div>
  <div style="padding:20px">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:#f3f4f6;border-bottom:2px solid #e5e7eb">
        <th style="padding:10px;text-align:left">代號</th>
        <th style="padding:10px;text-align:left">名稱</th>
        <th style="padding:10px">現價</th>
        <th style="padding:10px">漲跌</th>
        <th style="padding:10px">評分</th>
      </tr></thead>
      <tbody>
        {''.join(f'''<tr style="border-bottom:1px solid #e5e7eb">
          <td style="padding:10px"><a href="https://www.wantgoo.com/stock/{s["code"]}/technical-chart" style="color:#2563eb;text-decoration:none">{s["code"]}</a></td>
          <td style="padding:10px">{s["name"]}</td>
          <td style="padding:10px;text-align:right">{s["price"]}</td>
          <td style="padding:10px;text-align:right;color:{"#fc8181" if s["chg"]>=0 else "#68d391"}">{("+"+str(s["chg"]) if s["chg"]>=0 else str(s["chg"]))+"%"}</td>
          <td style="padding:10px;text-align:right;font-weight:700">{s["score"]}</td>
        </tr>''' for s in sorted(candidates, key=lambda x: x["score"], reverse=True)[:50])}
      </tbody>
    </table>
  </div>
  <div style="padding:14px;background:#f8fafc;text-align:center;font-size:10px;color:#6b7280">
    ⚠️ 自動產生，僅供參考。資料來源：FinMind
  </div>
</div></body></html>"""

def send_email(html, date, count):
    cfg = EMAIL_CONFIG
    if not cfg["password"] or not cfg["sender"]:
        log.warning("未設定 Email")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📈 飆股雷達 {date} — {count}檔"
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["receiver"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(cfg["smtp"], cfg["port"]) as s:
            s.ehlo(); s.starttls()
            s.login(cfg["sender"], cfg["password"])
            s.sendmail(cfg["sender"], cfg["receiver"], msg.as_string())
        log.info(f"✅ Email 寄出")
    except Exception as e:
        log.error(f"❌ 寄信失敗: {e}")

def main():
    today = datetime.today().strftime("%Y-%m-%d")
    candidates = run_screener(today)
    html = build_html(candidates, today)
    
    local_path = os.path.join(OUTPUT_DIR, f"report_{today}.html")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(root_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    send_email(build_email_html(candidates, today), today, len(candidates))
    
    with open(os.path.join(OUTPUT_DIR, f"result_{today}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today, "candidates": candidates}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！{len(candidates)}檔")

if __name__ == "__main__":
    main()
