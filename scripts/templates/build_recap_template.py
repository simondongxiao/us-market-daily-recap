from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from daily_movers import write_daily_movers

ROOT = Path(r"D:\codex\outputs\us_market_daily_recaps\2026-10-13")
OUT = Path(r"D:\codex\outputs\us_market_daily_recaps\us_market_recap_2026-10-13_BJT_us_2026-10-12_final.docx")
REPORT_BJT = "2026-10-13"
US_TRADE_DATE = "2026-10-12"
Q = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
B = json.loads((ROOT / "breadth.json").read_text(encoding="utf-8"))
ROT = json.loads((ROOT / "rotation_engine.json").read_text(encoding="utf-8"))
OPTIONS = json.loads((ROOT / "options_chain.json").read_text(encoding="utf-8"))
WATCH = json.loads((ROOT / "index_inclusion_watch.json").read_text(encoding="utf-8"))
INTRADAY_PATH = ROOT / "intraday.json"
INTRADAY = json.loads(INTRADAY_PATH.read_text(encoding="utf-8")) if INTRADAY_PATH.exists() else []
EVENTS_PATH = ROOT / "company_events.json"
COMPANY_EVENTS = json.loads(EVENTS_PATH.read_text(encoding="utf-8")) if EVENTS_PATH.exists() else {"events": [], "market_sources": []}
EVENT_BY_TICKER = {str(item.get("ticker", "")).upper(): item for item in COMPANY_EVENTS.get("events", []) if item.get("ticker")}


def pct(symbol: str, field: str = "day") -> str:
    x = Q[symbol].get(field)
    return "不可得" if x is None else f"{x:+.2f}%"


def val(symbol: str, field: str = "close", digits: int = 2) -> str:
    x = Q[symbol].get(field)
    return "不可得" if x is None else f"{x:,.{digits}f}"


def btc_usd_10k() -> str:
    x = Q.get("BTC-USD", {}).get("close")
    return "不可得" if x is None else f"{x / 10000:.2f}万美元"


def ret_n(symbol: str, n: int) -> float:
    path = ROOT / (symbol.replace("^", "idx_").replace("=", "_") + "_daily.csv")
    c = pd.to_numeric(pd.read_csv(path)["Close"], errors="coerce").dropna()
    return float((c.iloc[-1] / c.iloc[-1 - n] - 1) * 100)


def mean_return(names: list[str]) -> float:
    xs = [Q[s]["day"] for s in names if s in Q and Q[s].get("day") is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def spread(a: str, b: str) -> float:
    av = Q.get(a, {}).get("day")
    bv = Q.get(b, {}).get("day")
    return float("nan") if av is None or bv is None else float(av - bv)


STOCKS = set(Q) - {"^DJI", "^GSPC", "^IXIC", "^RUT", "^VIX", "^VVIX", "^SKEW", "^TNX", "DX-Y.NYB", "CL=F", "BZ=F", "GC=F", "HG=F", "BTC-USD"}


SECTOR_LABELS = {
    "XLK": "科技", "XLC": "通信服务", "XLY": "可选消费", "XLP": "必选消费",
    "XLF": "金融", "XLI": "工业", "XLE": "能源", "XLB": "材料",
    "XLV": "医疗保健", "XLRE": "房地产", "XLU": "公用事业", "SOXX": "半导体",
    "SMH": "半导体", "IGV": "软件", "XBI": "生物医药", "IHI": "医疗器械",
    "CIBR": "网络安全", "SKYY": "云计算", "XME": "金属与矿业", "COPX": "铜矿",
    "GDX": "黄金矿业", "KRE": "区域银行", "XRT": "零售", "XHB": "住宅建筑",
    "ITA": "航空航天/国防", "ARKK": "创新成长",
}


def available_days(names: list[str]) -> list[tuple[str, float]]:
    return [(s, float(Q[s]["day"])) for s in names if s in Q and Q[s].get("day") is not None]


sector_days = available_days(list(SECTOR_LABELS))
sector_days.sort(key=lambda x: x[1], reverse=True)
sector_leaders = "、".join(f"{s}（{SECTOR_LABELS[s]}）{v:+.2f}%" for s, v in sector_days[:3]) or "数据不可得"
sector_laggards = "、".join(f"{s}（{SECTOR_LABELS[s]}）{v:+.2f}%" for s, v in sector_days[-3:]) or "数据不可得"
sector_median = sorted(v for _, v in sector_days)[len(sector_days) // 2] if sector_days else float("nan")

valid_intraday = [
    x for x in INTRADAY
    if not x.get("error") and x.get("trade_date") == US_TRADE_DATE and x.get("late_return") is not None
]
if valid_intraday:
    late_sorted = sorted(valid_intraday, key=lambda x: float(x["late_return"]), reverse=True)
    late_strong = "、".join(f"{x['symbol']} {float(x['late_return']):+.2f}%" for x in late_sorted[:2])
    late_weak = "、".join(f"{x['symbol']} {float(x['late_return']):+.2f}%" for x in late_sorted[-2:])
    moc_data = f"价格代理可得（{len(valid_intraday)}/9）"
    moc_read = f"尾20分钟相对最强 {late_strong}；相对最弱 {late_weak}。仅为价格变化，不是官方MOC金额或买卖失衡"
else:
    moc_data = "不可得"
    moc_read = "目标交易日5分钟序列未通过完整性校验，不能判断尾盘价格方向"


def sector_bucket(symbol: str) -> str:
    value = Q.get(symbol, {}).get("day")
    if value is None or pd.isna(sector_median):
        return "相对强弱不可得"
    return "相对强势候选" if value >= sector_median else "相对弱势候选"
semi_stats = ROT.get("stats", {}).get("semi", {})
software_stats = ROT.get("stats", {}).get("software", {})
semi_eq = float(semi_stats.get("equal_weight_1d", float("nan")))
software_eq = float(software_stats.get("equal_weight_1d", float("nan")))
semi_spread = semi_eq - software_eq
daily_movers = write_daily_movers(ROOT)
selected_movers = daily_movers.get("selected", [])
exception_names = [x["ticker"] for x in selected_movers]
exception_text = "、".join(
    f"{x['ticker']}（{x.get('industry', '行业待核')}）{x['day']:+.2f}%"
    for x in selected_movers
) or "未识别出可用的单股异常"
ai_tier_1 = ["NVDA", "AVGO", "MSFT", "META"]
ai_tier_2 = ["MU", "SNDK", "MRVL", "CRDO", "LITE", "COHR"]
ai_tier_1_text = "、".join(f"{s} {pct(s)}" for s in ai_tier_1 if s in Q and Q[s].get("day") is not None)
ai_tier_2_text = "、".join(f"{s} {pct(s)}" for s in ai_tier_2 if s in Q and Q[s].get("day") is not None)
stock_movers = [
    (x["ticker"], float(x["day"]), x.get("volume_ratio"), x.get("relative_vs_spy"), x.get("selection_reasons", []), x.get("industry", "行业待核"))
    for x in selected_movers
]
stock_mover_text = "；".join(
    f"{s} {v:+.2f}%（{industry}；成交约{vr:.2f}x均量）" if vr is not None else f"{s} {v:+.2f}%（{industry}）"
    for s, v, vr, _, _, industry in stock_movers
) or "未识别出可用的异动个股"
event_digest = "；".join(
    f"{ticker}（{EVENT_BY_TICKER[ticker].get('status', '待验')}）：{EVENT_BY_TICKER[ticker].get('cause', '原因待核')}"
    for ticker in exception_names if ticker in EVENT_BY_TICKER
)
option_checked_at = OPTIONS.get("checked_at_et", "检查时间不可得")
matrix_digest = "；".join(
    f"{x['pair']} 1D {x['1d']:+.2f}pp / 5D {x['5d']:+.2f}pp / 20D {x['20d']:+.2f}pp（{x['regime']}）"
    for x in ROT.get("matrix", [])
)


STOCKS = set(Q) - {"^DJI", "^GSPC", "^IXIC", "^RUT", "^VIX", "^VVIX", "^SKEW", "^TNX", "DX-Y.NYB", "CL=F", "BZ=F", "GC=F", "HG=F", "BTC-USD"}


def shade(run) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "E7E6E6")
    run._element.get_or_add_rPr().append(shd)


def add_text(para, text: str, highlight: bool = False) -> None:
    for part in re.split(r"(\b[A-Z][A-Z0-9]{1,5}\b)", text):
        if not part:
            continue
        run = para.add_run(part)
        if part in STOCKS:
            shade(run)
        if highlight:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def para(text: str, highlight: bool = False, small: bool = False):
    z = doc.add_paragraph()
    z.paragraph_format.space_after = Pt(3 if small else 6)
    z.paragraph_format.line_spacing = 1.15
    add_text(z, text, highlight)
    if small:
        for run in z.runs:
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(85, 85, 85)
    return z


def heading(text: str, level: int = 1):
    z = doc.add_heading(text, level=level)
    z.paragraph_format.keep_with_next = True
    return z


def chart(filename: str, title: str, basis: str, width: float = 6.35):
    path = ROOT / filename
    if not path.exists():
        para(f"图表缺失：{filename}。该数据不可得，本报告不以文字替代图表。", highlight=True)
        return
    z = doc.add_paragraph()
    z.alignment = WD_ALIGN_PARAGRAPH.CENTER
    z.paragraph_format.keep_with_next = True
    z.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph(f"图：{title}。来源/口径：{basis}。")
    cap.paragraph_format.space_after = Pt(5)
    for run in cap.runs:
        run.italic = True
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(85, 85, 85)


def set_cell(cell, text: str, header: bool = False, center: bool = False):
    cell.text = str(text)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "1F4E78" if header else "FFFFFF")
    tcpr.append(shd)
    for z in cell.paragraphs:
        z.paragraph_format.space_before = Pt(3)
        z.paragraph_format.space_after = Pt(3)
        z.paragraph_format.line_spacing = 1.0
        if center:
            z.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in z.runs:
            run.font.size = Pt(8.1 if not header else 8.3)
            run.bold = header
            run.font.color.rgb = RGBColor(255, 255, 255) if header else RGBColor(20, 20, 20)
    mar = OxmlElement("w:tcMar")
    for side in ["top", "start", "bottom", "end"]:
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), "90")
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tcpr.append(mar)


def table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.autofit = False
    for i, x in enumerate(headers):
        set_cell(t.rows[0].cells[i], x, header=True, center=i == 0)
    for row in rows:
        cells = t.add_row().cells
        for i, x in enumerate(row):
            set_cell(cells[i], x, center=i == 0 or bool(widths and widths[i] <= 1.0))
    if widths:
        for row in t.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    for row in t.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def link(label: str, url: str):
    z = doc.add_paragraph()
    rid = z.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rid)
    r = OxmlElement("w:r")
    r.append(OxmlElement("w:rPr"))
    t = OxmlElement("w:t")
    t.text = label
    r.append(t)
    h.append(r)
    z._p.append(h)


doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = Inches(.62)
section.bottom_margin = Inches(.62)
section.left_margin = Inches(.68)
section.right_margin = Inches(.68)
for name in ["Normal", "Body Text", "Caption"]:
    s = doc.styles[name]
    s.font.name = "Calibri"
    s.font.size = Pt(10.4)
    s.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    s.paragraph_format.line_spacing = 1.15
    s.paragraph_format.space_after = Pt(6)
for name, size in [("Title", 21), ("Heading 1", 15), ("Heading 2", 11.5)]:
    s = doc.styles[name]
    s.font.name = "Calibri"
    s.font.size = Pt(size)
    s.font.color.rgb = RGBColor(0, 0, 0)
    s.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

doc.add_heading(f"美股每日复盘 | {US_TRADE_DATE} 美东收盘", level=0)
para(f"报告日期：{REPORT_BJT}（北京时间）｜覆盖交易日：{US_TRADE_DATE}（美国现金盘）｜数据截点：收盘及可获得的盘后公开链数据。", small=True)
para(f"结论先行：指数表现为道指 {pct('^DJI')}、标普500 {pct('^GSPC')}、纳指 {pct('^IXIC')}、Russell 2000 {pct('^RUT')}；S&P 500 广度为上涨 {B.get('advancers', '不可得')}、下跌 {B.get('decliners', '不可得')}，涨跌比 {B.get('ad_ratio', float('nan')):.2f}。板块当日相对强弱由 {sector_leaders} 领跑，{sector_laggards} 落后；这是当天价格与广度观察，不把固定公司名单预设为催化。", highlight=True)

heading("1. Executive Tape Snapshot")
table(["资产/指标", "收盘/状态", "当日", "5D", "读法"], [
    ["Dow Jones", val("^DJI"), pct("^DJI"), pct("^DJI", "5d"), "相对最强，价值/防御托底"],
    ["S&P 500", val("^GSPC"), pct("^GSPC"), pct("^GSPC", "5d"), "结合广度与RSP判断内部结构"],
    ["Nasdaq Composite", val("^IXIC"), pct("^IXIC"), pct("^IXIC", "5d"), "与QQQ/RSP及科技篮子比较"],
    ["Russell 2000", val("^RUT"), pct("^RUT"), pct("^RUT", "5d"), "小盘弱于大盘"],
    ["VIX / VVIX / SKEW", f"{val('^VIX')} / {val('^VVIX')} / {val('^SKEW')}", pct("^VIX"), "—", "以实际变动判断保护需求"],
    ["DXY / WTI / BTC", f"{val('DX-Y.NYB')} / {val('CL=F')} / {btc_usd_10k()}", f"DXY {pct('DX-Y.NYB')} / WTI {pct('CL=F')} / BTC {pct('BTC-USD')}", "—", "跨资产确认或反驳风险偏好叙事"],
], widths=[1.35, 1.35, .9, .9, 2.0])
para(f"图表读法：当日相对最强为 {sector_leaders}，相对最弱为 {sector_laggards}；上涨占比 {B.get('up_pct', float('nan')):.1f}%。需要把 ETF 表现和单股异常分开读，不能用行业平均替代个股催化。")
chart("sector_bar.png", "板块当日表现与成交相对强度", "Yahoo Finance Chart API；日收益率，成交相对30日均量。", width=5.15)

heading("2. Rotation & Leadership Dashboard")
chart("rotation_sector_heatmap.png", "Sector Rotation Map（行业指数）", "本地 rotation_engine；1D/5D/20D，单位为百分比；括号内为行业名称。")
para(f"资金方向判断：价格代理显示相对偏好集中在 {sector_leaders}，相对压力集中在 {sector_laggards}；20日维度需要结合热图判断是否只是短期反转。没有直接 ETF/PB 净流数据时，报告使用“价格偏好/轮动代理”，不把相对涨跌写成已证实的净流入或净流出。")
chart("rotation_leadership_heatmap.png", "Leadership Heatmap（领导力轮动）", "Rotation Engine 固定篮子等权收益；1D/5D/20D；价格相对强弱代理。")
chart("rotation_mag7_heatmap.png", "Mag 7 Internal Heatmap（内部轮动）", "Mag 7 单股 1D/5D/20D 与相对 SPY；不把权重股表现自动写成行业普涨。")
para("领导力读法：先看热图中同一方向的横截面广度，再看 1D、5D、20D 是否一致；若只有少数大市值股票支撑指数，而等权篮子和细分行业走弱，应定义为权重挤压而不是广泛风险偏好改善。")
chart("rotation_subsector_heatmap.png", "Subsector Rotation Map（细分行业）", "本地 rotation_engine；加入 XBI、IHI、XHE、CIBR、SKYY、XME、COPX、GDX、KRE、XRT、XHB、ITA 等行业/主题代理。")
para(f"异常个股必须回填在行业图旁：本次先从 {daily_movers.get('universe_count', 0)} 个可用单股样本中按当日绝对涨跌、相对 SPY、成交量和新高/新低筛出 {daily_movers.get('selected_count', 0)} 个候选：{exception_text}。固定 AI/光通信名单只用于覆盖扫描，未进入当日异动排序的标的不进入本节归因。若当天没有新公告、研报、公司交流或可验证传闻，只能标为结构性重定价或待验，不能把行业 ETF 变化直接当成单股原因。")
chart("rotation_semi_software.png", "Semi vs Software：横截面当日收益", "本地 rotation_engine；各自12只代表性成分，等权。")
chart("rotation_semi_software_spread.png", "Semi - Software Daily Spread", "定义：Semi - Software > 0 表示半导体跑赢软件；< 0 表示软件跑赢半导体。")
para(f"图表解读：半导体等权当日 {semi_eq:+.2f}%，软件等权 {software_eq:+.2f}%，价差（Semi - Software）{semi_spread:+.2f} 个百分点；正值表示半导体相对跑赢，负值表示软件相对跑赢。两者绝对涨跌、ETF 权重和中位数可能不同，不能只凭价差判断整个科技板块方向。")

heading("3. Rotation Matrix")
rows = []
for x in ROT["matrix"]:
    rows.append([x["pair"], f"{x['1d']:+.2f}pp", f"{x['5d']:+.2f}pp", f"{x['20d']:+.2f}pp", x["regime"]])
table(["比较组合", "1D", "5D", "20D", "状态"], rows, widths=[2.35, .85, .85, .85, 1.25])
para(f"矩阵观察：{matrix_digest or '轮动矩阵不可得'}。上涨占比 {B.get('up_pct', float('nan')):.1f}%，因此需把指数方向、横截面参与度和 1D/5D/20D 持续性分开判断；不能用单日价差直接替代资金流。")

heading("4. Factor, Microstructure & HF Positioning")
chart("breadth.png", "Breadth & Participation", "503 只当前 S&P 500 成分；Advancing/Declining 为当日涨跌家数，New highs/lows 为252交易日极值。")
para(f"广度：上涨 {B['advancers']}、下跌 {B['decliners']}、不变 {B['unchanged']}，上涨占比 {B['up_pct']:.1f}%，涨跌比 {B['ad_ratio']:.2f}；252日新高 {B['highs_252']}、新低 {B['lows_252']}。这不是“全市场风险关闭”，而是指数权重和主题结构在切换。RSP 当日 {pct('RSP')}，SPY {pct('SPY')}，RSP 相对 SPY 约 {Q['RSP']['day'] - Q['SPY']['day']:+.2f}pp，等权参与度优于市值加权。")
chart("factor_proxy.png", "Factor Proxy Dashboard", "本地公开 ETF 代理；Momentum=MTUM，High Beta=SPHB，Low Vol=USMV，Small Cap=IWM，Quality/defensive 以行业 ETF辅助。")
chart("factors.png", "Factor Multi-Speed Detail", "公开 ETF 价格代理；Momentum、High Beta、Low Vol、Small Cap、MEME 与 BUZZ 的横截面日收益。")
chart("intraday.png", "Intraday Path", "Yahoo 5分钟常规现金盘；09:30 归一化为 100，尾盘阴影为最后约20分钟。")
chart("moc.png", "Closing Pressure Proxy", "Yahoo 5分钟现金盘最后20分钟收益；不是官方 MOC 金额或买卖失衡。")
chart("volatility.png", "Volatility / Tail Protection", "VIX、VVIX、SKEW 日变；只能作为风险保护代理，不等于做市商 Gamma。")
para(f"因子结论：SPHB {pct('SPHB')} 对比 USMV {pct('USMV')}（差 {spread('SPHB', 'USMV'):+.2f}pp），IWM {pct('IWM')} 对比 SPY {pct('SPY')}（差 {spread('IWM', 'SPY'):+.2f}pp）。在宏观美元与油价同时偏强的环境下，对冲基金去杠杆是一个待验证的结构性假设，而不是已经被 PB 数据证实的事实；其典型路径是砍掉高 Beta 多头、回补此前拥挤的空头，因此个别高空头光模块或存储名字若逆势反弹，不能直接解释为基本面反转。公开数据没有 GS/PB 净买入、总交易量或 CTA 实时阈值，本报告不编造。")

heading("5. Today's Company Expectation Resets")
reset_rows = []
for s, value, volume_ratio, relative_vs_spy, reasons, industry in stock_movers[:6]:
    relative_text = f"；相对SPY {relative_vs_spy:+.2f}pp" if relative_vs_spy is not None else ""
    volume_text = f"；成交 {volume_ratio:.2f}x均量" if volume_ratio is not None else "；成交不可得"
    event = EVENT_BY_TICKER.get(s)
    status = event.get("status", "待验") if event else "待验"
    meaning = event.get("cause") if event else "待核验同日增量；先归为公司/行业/因子重定价候选，不把涨跌倒推成原因"
    reset_rows.append([s, f"{industry}；价格 {value:+.2f}%{relative_text}{volume_text}", status, meaning])
table(["公司/主题", "今日价格证据", "状态", "市场含义"], reset_rows or [["无", "核心异动样本不可得", "不可得", "不编造公司原因"]], widths=[1.45, 2.05, 1.0, 2.0])
for ticker in exception_names:
    event = EVENT_BY_TICKER.get(ticker)
    if not event:
        continue
    para(f"{ticker}（{event.get('industry', '行业待核')}，{event.get('status', '待验')}）：{event.get('cause', '原因待核')}。交易解读：{event.get('interpretation', '需继续观察价格、成交与后续公司信息。')}")
para("事件闸门：只有当当天有新公告、正式报告、公司交流、明确指引或可验证的市场结构证据，才升级为个股催化。旧财报只作为估值和预期背景，不重复追踪。")

heading("6. Technology Sector Scan")
chart("ai_ladder.png", "AI Chain Ladder：Tier 1 / Tier 2 / Tier 3", "本地行情数据；Tier 1 为现金流巨头，Tier 2 为网络/存储/互联，Tier 3 为电力/数据中心基础设施。")
chart("tiers.png", "AI Chain Tier Detail", "固定篮子等权日收益；价格分层，不等于订单或资金流。")
para(f"AI 链条分层：Tier 1 现金流/平台代表为 {ai_tier_1_text or '不可得'}；Tier 2 网络、存储和光互联代表为 {ai_tier_2_text or '不可得'}。这组数据只能说明当天价格速度和相对分化，不能单独证明订单、客户或资本开支发生变化；后者需要公司公告、会议或可复核产业数据。")
chart("movers.png", "科技与主题异动个股", "Yahoo Finance Chart API；按当日绝对收益及成交相对30日均量筛选。")
chart("optical.png", "Optical / AI Networking Exceptions", "光模块、互联、存储与半导体代表股；按目标日价格表现排序。")
chart("memory.png", "Memory and Server Chain", "MU、SNDK、WDC、STX 与服务器/系统代表股；价格横截面，不替代供需验证。")
chart("mag7.png", "Mag 7 Internal Rotation", "Mag 7 单股目标日收益；用于识别权重集中和内部背离。")
para(f"异动原因必须逐个核验：按绝对涨跌筛出的候选为 {stock_mover_text}。本次已取得的同日归因为：{event_digest or '未取得可验证增量，全部保留待验'}。未取得证据的名字只记录价格/成交异常，不把涨跌倒推成原因。")

heading("7. Non-Tech Sector Scan")
chart("sectors.png", "11-Sector Industry Map", "SPDR 行业 ETF；每个代码均带行业关键词。")
chart("subsectors.png", "Sub-sector Industry Detail", "半导体、软件、生物医药、医疗器械、网络安全、云计算、矿业、银行、零售、住宅建筑与国防代理。")
chart("crossasset.png", "Cross-Asset Context", "Yahoo 公开连续合约/指数报价；跨资产涨跌用于确认或质疑单一市场叙事。")
table(["价格方向", "代理/行业", "1D", "观察"], [
    [sector_bucket("XLE"), "能源 XLE", pct("XLE"), "结合WTI、成交和20日趋势核验"],
    [sector_bucket("XLP"), "必选消费 XLP", pct("XLP"), "防御/现金流相对偏好候选"],
    [sector_bucket("XLV"), "医疗保健 XLV / 医疗器械 IHI", f"{pct('XLV')} / {pct('IHI')}", f"IHI相对XLV {spread('IHI', 'XLV'):+.2f}pp，行业内部需拆分"],
    [sector_bucket("XLC"), "通信服务 XLC", pct("XLC"), "查看大型权重与细分通信服务是否同向"],
    [sector_bucket("XLB"), "材料 XLB / 房屋 XHB", f"{pct('XLB')} / {pct('XHB')}", "周期与利率敏感资产相对表现"],
    [sector_bucket("XBI"), "生物科技 XBI / ARKG", f"{pct('XBI')} / {pct('ARKG')}", "ETF弱时仍需单独解释TWST等个股异常"],
], widths=[1.0, 1.8, 1.0, 2.5])
para("TWST 与 XLV 的关系：单只生物科技股的大涨/大跌可以由临床、监管、合作、融资或短 squeeze 驱动，不要求 XLV 同向。行业 ETF 是组合篮子，个股是事件驱动；当两者背离时，报告必须把个股原因和行业资金方向分开写。")

heading("8. Decliners & Kill Reasons")
chart("losers.png", "Pressure Points", "按代表性科技、光互联、存储与高 Beta 标的目标日跌幅排序。")
chart("company_movers.png", "Company Exceptions", "按绝对涨跌筛选，并显示成交量相对30日均量；异常不等于催化。")
decliner_rows = []
for s, value, volume_ratio, relative_vs_spy, reasons, industry in sorted((x for x in stock_movers if x[1] < 0), key=lambda x: x[1])[:6]:
    vol_text = f"{volume_ratio:.2f}x均量" if volume_ratio is not None else "成交不可得"
    relative_text = f"；相对SPY {relative_vs_spy:+.2f}pp" if relative_vs_spy is not None else ""
    event = EVENT_BY_TICKER.get(s)
    explanation = event.get("cause") if event else "当日价格/成交异常；需用同日公告、研报、交流或产业数据确认原因"
    decliner_rows.append([s, f"{industry} {value:+.2f}%", f"{vol_text}{relative_text}", explanation])
table(["标的", "当日", "成交/状态", "当前可验证解释"], decliner_rows or [["无", "—", "—", "未发现可用的下跌异常样本"]], widths=[1.0, 1.0, 1.35, 3.0])
para("Kill reason 的写法：先写价格和成交，再写可验证事件，最后写结构性解释与待验项。没有新公告时，不把旧财报、传闻或行业图表强行包装成“今日公司事件”。")

heading("9. Where Capital Focused")
para(f"资金主线判断基于价格偏好代理：板块前列为 {sector_leaders}，后列为 {sector_laggards}；S&P 广度上涨占比 {B.get('up_pct', float('nan')):.1f}%，RSP {pct('RSP')} 对比 SPY {pct('SPY')}。这能支持参与度和相对偏好的判断，但没有直接基金流、PB 或 CTA 数据时，不写成确认的净流入/净流出。")

heading("10. Index Inclusion & Option Risk")
watch_items = WATCH.get("reminders", [])
if watch_items:
    para("指数纳入跟踪：" + "；".join(map(str, watch_items)))
else:
    para("本次公开资料未识别出有确定纳入日期、且需要持续每日提醒的新增标的。若后续出现正式指数公司公告，将记录公告日、正式生效日、被动资金窗口和预期交易量；在正式纳入前每日提醒，纳入后结束提醒。")
opt_rows = []
for x in OPTIONS.get("results", []):
    alerts = [a for a in x.get("option_alerts", []) if a != "no_threshold_alert"]
    if alerts or x["ticker"] in {"LITE", "COHR", "CIEN", "AAOI", "MU", "SNDK", "NVDA", "AVGO", "META", "FICO", "TWST", "CRDO", "MRVL"}:
        label = ", ".join(alerts) if alerts else "无阈值报警"
        ratio = x.get("call_put_volume_ratio")
        strike_share = x.get("max_strike_volume_share")
        ratio_text = "不可得" if ratio is None or pd.isna(ratio) else f"{float(ratio):.2f}"
        strike_text = "不可得" if strike_share is None or pd.isna(strike_share) else f"{float(strike_share):.1%}"
        opt_rows.append([x["ticker"], x.get("expiry_near") or "不可得", ratio_text, strike_text, label])
table(["标的", "近月到期", "Call/Put成交量", "最大执行价成交占比", "提示"], opt_rows, widths=[.75, 1.15, 1.25, 1.4, 2.0])
chart("options_alerts.png", "公开期权链异常扫描", f"Nasdaq public option-chain endpoint；检查时点 {option_checked_at}；无执行方向确认。")
option_alert_names = [x["ticker"] for x in OPTIONS.get("results", []) if x.get("data_status") == "available" and any(a not in {"no_threshold_alert", "source unavailable"} for a in x.get("option_alerts", []))]
option_unavailable_names = [x["ticker"] for x in OPTIONS.get("results", []) if x.get("data_status") != "available"]
para(f"解读规则：本次触发异常阈值的标的为 {', '.join(option_alert_names) if option_alert_names else '无'}；来源不可得为 {', '.join(option_unavailable_names) if option_unavailable_names else '无'}。执行价集中度只能说明成交/未平仓结构围绕少数执行价聚集，可能对应事件对冲、做市商库存管理、价位 pinning 或投机性集中下注；在没有执行侧、开平仓、扫单/大宗标签时，不等于看涨、看跌、净买入或净卖出。")
para("期权数据限制：本次优先抓取 Nasdaq 公共链，StockWe 每笔成交方向未形成可验证数据；缺少执行侧、开平仓、IV历史与 GEX，故不编造“机构买 Call/买 Put”结论。")

heading("11. Derivatives, Gamma & Flows")
chart("options.png", "Near-Expiry Option Structure", "Nasdaq 公共期权链；Call/Put 成交量比不等于买卖方向。")
chart("macro_curve.png", "10Y Treasury Yield Proxy", "^TNX 公开代理；前收与目标收盘的变化用于利率传导观察。")
table(["指标", "数据", "结论"], [
    ["VIX / VVIX / SKEW", f"{val('^VIX')} / {val('^VVIX')} / {val('^SKEW')}", "波动率与尾部保护需求偏高，但未到恐慌级"],
    ["0DTE / GEX", "不可得", "没有公开、可审计的全市场实时 GEX，不推断正/负 Gamma"],
    ["MOC / 尾盘20分钟", moc_data, moc_read],
    ["GS/PB / CTA", "不可得", "不披露内部净买入、总交易量或实时触发线"],
], widths=[1.5, 1.4, 3.6])
para(f"今天可确认的是价格与横截面结构：标普 {pct('^GSPC')}、纳指 {pct('^IXIC')}，广度上涨占比 {B.get('up_pct', float('nan')):.1f}%，QQQ 对 RSP 的日差为 {spread('QQQ', 'RSP'):+.2f}pp，高 Beta 对低波动为 {spread('SPHB', 'USMV'):+.2f}pp。因此对冲基金去杠杆仍是结构性假设，而不是已经被 PB 数据证实的事实。")

heading("12. Post-Bell / Next Session")
table(["时间/事件", "状态", "跟踪重点"], [
    [f"{US_TRADE_DATE} 美股交易日", "已完成", "观察 SOXX/光通信是否出现相对止跌，及 RSP-SPY 价差是否继续扩大"],
    ["JPMorgan 投资者活动", "公开日程待核", "若出现公司交流或指引，按新事件而非历史财报处理"],
    ["宏观：油价/美元/利率", "持续跟踪", "美元与油价同时上行是否继续压制高 Beta 与小盘"],
    ["指数纳入与期权", "无当前提醒", "若出现正式公告或异常执行价聚集，进入下一日报告"],
], widths=[1.6, 1.3, 3.6])

heading("13. A-Share & Hong Kong Mapping")
chart("mapping.png", "US to A/H Read-through", "基于当日价格偏好与产业链关系的情景映射；不是 A/H 盘中实际资金流。")
para("映射只做产业链方向，不把美股单日跌幅机械外推到 A/H 股。AI 硬件/光互联对应光模块、连接器、PCB、交换机、服务器和液冷；存储链对应 DRAM/NAND 与控制器；Tier 1 平台走强而 Tier 2 硬件走弱时，应优先观察 A/H 市场是否出现高位主题分化、资金向现金流和低估值环节切换。通信服务与运营商相对强，不等于 A/H 通信设备必然上涨，需要结合人民币、北向/南向和本地估值。")

heading("14. Data Appendix")
chart("breadth.png", "Appendix: breadth data", "同上；503只S&P 500成分。")
chart("factor_proxy.png", "Appendix: factor proxies", "同上；ETF代理，不等同于可交易因子组合收益。")
para("数据完整性：核心日线若缺少目标日收盘，则由 Yahoo Chart API 的目标交易日 5分钟常规现金盘聚合重建，并在运行日志保留该口径；S&P 500 成分广度与行业代理均经过目标日校验。期权链为公开快照，PB、CTA、真实 GEX、执行方向仍不可得；所有不可得项均保留为“不可得”，没有用估计值替代。")

heading("15. Sources")
seen_sources = set()
for source in COMPANY_EVENTS.get("market_sources", []):
    url = source.get("url")
    if url and url not in seen_sources:
        link(source.get("label", url), url)
        seen_sources.add(url)
for event in COMPANY_EVENTS.get("events", []):
    for source in event.get("sources", []):
        url = source.get("url")
        if url and url not in seen_sources:
            link(f"{event.get('ticker', '')}：{source.get('label', url)}", url)
            seen_sources.add(url)
link("Nasdaq public option chain example: LITE", "https://www.nasdaq.com/market-activity/stocks/lite/option-chain")
link("Yahoo Finance Chart API example: SPY", "https://query1.finance.yahoo.com/v8/finance/chart/SPY")
para("方法声明：本报告为收盘后复盘，不构成投资建议。公司事件优先使用官方公告；媒体和二手报道只作为待验线索。价格归因区分“已确认”“二手报道”“结构性解释”“待验”，避免把相关性写成因果性。", small=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(str(OUT))
