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

ROOT = Path(r"D:\codex\outputs\us_market_daily_recaps\2026-10-13")
OUT = Path(r"D:\codex\outputs\us_market_daily_recaps\us_market_recap_2026-10-13_BJT_us_2026-10-12_final.docx")
Q = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
B = json.loads((ROOT / "breadth.json").read_text(encoding="utf-8"))
ROT = json.loads((ROOT / "rotation_engine.json").read_text(encoding="utf-8"))
OPTIONS = json.loads((ROOT / "options_chain.json").read_text(encoding="utf-8"))
WATCH = json.loads((ROOT / "index_inclusion_watch.json").read_text(encoding="utf-8"))


def pct(symbol: str, field: str = "day") -> str:
    x = Q[symbol].get(field)
    return "不可得" if x is None else f"{x:+.2f}%"


def val(symbol: str, field: str = "close", digits: int = 2) -> str:
    x = Q[symbol].get(field)
    return "不可得" if x is None else f"{x:,.{digits}f}"


def ret_n(symbol: str, n: int) -> float:
    path = ROOT / (symbol.replace("^", "idx_").replace("=", "_") + "_daily.csv")
    c = pd.to_numeric(pd.read_csv(path)["Close"], errors="coerce").dropna()
    return float((c.iloc[-1] / c.iloc[-1 - n] - 1) * 100)


def mean_return(names: list[str]) -> float:
    xs = [Q[s]["day"] for s in names if s in Q and Q[s].get("day") is not None]
    return sum(xs) / len(xs) if xs else float("nan")


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

doc.add_heading("美股每日复盘 | 2026-10-12 美东收盘", level=0)
para("报告日期：2026-10-13（北京时间）｜覆盖交易日：2026-10-12（美国现金盘）｜数据截点：收盘及可获得的盘后公开链数据。", small=True)
para("结论先行：这是一个“指数近乎横盘、内部轮动明显”的交易日。道指 +0.38%，标普500 -0.06%，纳指 -0.44%，Russell 2000 -0.45%；但标普成分股上涨 321 家、下跌 179 家，涨跌比约 1.79。资金从高估值 AI 硬件与高 Beta 方向撤出，转向能源、必选消费、医疗、通信服务和部分防御资产。", highlight=True)

heading("1. Executive Tape Snapshot")
table(["资产/指标", "收盘/状态", "当日", "5D", "读法"], [
    ["Dow Jones", val("^DJI"), pct("^DJI"), pct("^DJI", "5d"), "相对最强，价值/防御托底"],
    ["S&P 500", val("^GSPC"), pct("^GSPC"), pct("^GSPC", "5d"), "指数平稳，内部并非平稳"],
    ["Nasdaq Composite", val("^IXIC"), pct("^IXIC"), pct("^IXIC", "5d"), "成长权重承压"],
    ["Russell 2000", val("^RUT"), pct("^RUT"), pct("^RUT", "5d"), "小盘弱于大盘"],
    ["VIX / VVIX / SKEW", f"{val('^VIX')} / {val('^VVIX')} / {val('^SKEW')}", pct("^VIX"), "—", "波动率温和上行，尾部定价偏高"],
    ["DXY / WTI / BTC", f"{val('DX-Y.NYB')} / {val('CL=F')} / {val('BTC-USD')}", "美元/油涨，BTC跌", "—", "宏观流动性与风险偏好分化"],
], widths=[1.35, 1.35, .9, .9, 2.0])
chart("sector_bar.png", "板块当日表现与成交相对强度", "Yahoo Finance Chart API；日收益率，成交相对30日均量。", width=5.85)
para("图表读法：当日最强为能源（XLE +1.43%）、必选消费（XLP +1.17%）、通信服务（XLC +0.97%）；科技（XLK -1.22%）与半导体代理（SOXX -2.60%）明显落后。结合上涨家数占比 63.8%，可判定为“风险偏好没有全面崩坏，但高拥挤成长资产被主动降仓”。")

heading("2. Rotation & Leadership Dashboard")
chart("rotation_sector_heatmap.png", "Sector Rotation Map（行业指数）", "本地 rotation_engine；1D/5D/20D，单位为百分比；括号内为行业名称。")
para("资金方向判断：短线流入能源、必选消费、医疗保健、房地产和通信服务，流出科技、材料与可选消费；20日维度则仍保留半导体、软件/网络和 AI 相关资产的历史强势，因此今天更像高位主题内部的去杠杆，而不是趋势彻底反转。科技板块内部不能只看 XLK：SOXX/SMH、CIBR、SKYY 和 XBI 进一步走弱，而 IHI、XHE 体现医疗器械相对韧性。")
chart("rotation_subsector_heatmap.png", "Subsector Rotation Map（细分行业）", "本地 rotation_engine；加入 XBI、IHI、XHE、CIBR、SKYY、XME、COPX、GDX、KRE、XRT、XHB、ITA 等行业/主题代理。")
para("异常个股必须回填在行业图旁：光通信链条 LITE -9.78%、CIEN -9.95%、COHR -7.87%、AAOI -8.17%、CRDO -7.25%，明显弱于通信服务 ETF，说明行业指数掩盖了硬件子组的集中抛压；FICO +10.85%、FIGS +12.42%、MDT +3.90%则是单股驱动，不能被简单归入“金融、可选消费或医疗整体上涨”。")
chart("rotation_semi_software.png", "Semi vs Software：横截面当日收益", "本地 rotation_engine；各自12只代表性成分，等权。")
chart("rotation_semi_software_spread.png", "Semi - Software Daily Spread", "定义：Semi - Software > 0 表示半导体跑赢软件；< 0 表示软件跑赢半导体。")
para("图表解读：半导体等权当日约 -2.07%，软件约 -1.48%，价差约 -1.37 个百分点，意味着软件相对抗跌；但过去 20 日半导体仍明显占优，故今天更接近短期估值/仓位再平衡。不能把“半导体下跌”泛化为整个科技板块都弱，META +3.38%就是大型平台股的反例。")

heading("3. Rotation Matrix")
rows = []
for x in ROT["matrix"]:
    rows.append([x["pair"], f"{x['1d']:+.2f}pp", f"{x['5d']:+.2f}pp", f"{x['20d']:+.2f}pp", x["regime"]])
table(["比较组合", "1D", "5D", "20D", "状态"], rows, widths=[2.35, .85, .85, .85, 1.25])
para("矩阵显示：QQQ 相对 RSP 的 1D/5D 明显走弱，Mag7 相对科技除 Mag7 仍有当日支撑；AI CapEx 相对 AI Applications、High Beta 相对 Low Vol 均转弱。大盘上涨家数超过下跌家数，说明“参与度”没有塌陷，但高弹性和高拥挤的资金速度在下降。")

heading("4. Factor, Microstructure & HF Positioning")
chart("breadth.png", "Breadth & Participation", "503 只当前 S&P 500 成分；Advancing/Declining 为当日涨跌家数，New highs/lows 为252交易日极值。")
para(f"广度：上涨 {B['advancers']}、下跌 {B['decliners']}、不变 {B['unchanged']}，上涨占比 {B['up_pct']:.1f}%，涨跌比 {B['ad_ratio']:.2f}；252日新高 {B['highs_252']}、新低 {B['lows_252']}。这不是“全市场风险关闭”，而是指数权重和主题结构在切换。RSP 当日 {pct('RSP')}，SPY {pct('SPY')}，RSP 相对 SPY 约 {Q['RSP']['day'] - Q['SPY']['day']:+.2f}pp，等权参与度优于市值加权。")
chart("factor_proxy.png", "Factor Proxy Dashboard", "本地公开 ETF 代理；Momentum=MTUM，High Beta=SPHB，Low Vol=USMV，Small Cap=IWM，Quality/defensive 以行业 ETF辅助。")
para("因子结论：SPHB 相对 USMV 走弱，小盘相对大盘走弱；在宏观美元与油价同时偏强的环境下，对冲基金更可能采取 de-grossing，而不是单向全面做空。其典型路径是砍掉高 Beta 多头、回补此前已拥挤的空头，因此个别高空头光模块或存储名字若逆势反弹，不能直接解释为基本面反转，需等待成交、借券、期权执行方向和后续指引确认。公开数据没有 GS/PB 净买入、总交易量或 CTA 实时阈值，本报告不编造。")

heading("5. Today's Company Expectation Resets")
table(["公司/主题", "今日证据", "状态", "市场含义"], [
    ["META / Muse Wonder", "META +3.38%；官方发布 Muse Wonder 与 Muse Wonder Full", "已确认", "平台 AI 产品进展改善大型科技相对强度；尚不能外推为全行业硬件需求"],
    ["AVGO", "AVGO -1.88%；当日有 CEO 对 AI 预期过高/投资者行为的二手报道", "二手报道", "更像估值与预期重估；不是新财报，不把 9/2 财报重复写成今日催化"],
    ["光通信硬件", "LITE/CIEN/COHR/AAOI/CRDO 同步大跌，未见单一公司新公告", "板块重定价", "供给、估值、拥挤仓位或产业链预期同时收缩；不能硬归因于 FCC"],
    ["ORCL", "本日未发现新财报或新指引证据", "历史背景", "不纳入今日催化；只在云基础设施相对表现需要时作为背景参照"],
], widths=[1.45, 2.05, 1.0, 2.0])
para("事件闸门：只有当当天有新公告、正式报告、公司交流、明确指引或可验证的市场结构证据，才升级为个股催化。旧财报只作为估值和预期背景，不重复追踪。")

heading("6. Technology Sector Scan")
chart("ai_ladder.png", "AI Chain Ladder：Tier 1 / Tier 2 / Tier 3", "本地行情数据；Tier 1 为现金流巨头，Tier 2 为网络/存储/互联，Tier 3 为电力/数据中心基础设施。")
para("AI 链条分层：Tier 1 中 META 逆势上涨，NVDA -1.29%、AVGO -1.88%，表现分化；Tier 2 的 MU -3.88%、SNDK -5.97%、MRVL -3.42%、CRDO -7.25%、LITE -9.78%、COHR -7.87%显著承压；Tier 3 也不是同质，VRT/CEG/NRG 受能源与电力叙事影响相对独立。今天不是“AI 全线崩”，而是资金把最依赖持续加速订单、估值和资本开支预期的二阶硬件资产先降仓。")
chart("movers.png", "科技与主题异动个股", "Yahoo Finance Chart API；按当日绝对收益及成交相对30日均量筛选。")
para("异动原因必须逐个核验：FICO +10.85%伴随约 2.16 倍成交，属于强催化/预期重估候选，但本次公开数据未给出足够单一事件证据，标注为“待验”；FIGS +12.42%伴随约 3.83 倍成交，需核查业绩、产品或卖方报告；MDT +3.90%相对医疗器械 ETF走强，属于行业内部 Alpha。反面是光通信簇跌幅接近 -8%至 -10%，而非通信服务 ETF同步大跌，说明个股/子行业因素占主导。")

heading("7. Non-Tech Sector Scan")
table(["方向", "代理/行业", "1D", "判断"], [
    ["流入", "能源 XLE", pct("XLE"), "油价上涨与通胀/现金流防御共振"],
    ["流入", "必选消费 XLP", pct("XLP"), "防御与稳定现金流"],
    ["流入", "医疗保健 XLV / 医疗器械 IHI", f"{pct('XLV')} / {pct('IHI')}", "IHI 强于 XLV，行业内部偏器械 Alpha"],
    ["流入", "通信服务 XLC", pct("XLC"), "META、无线运营商支撑，非单一软件行情"],
    ["流出", "材料 XLB / 房屋 XHB", f"{pct('XLB')} / {pct('XHB')}", "周期与利率敏感资产相对弱"],
    ["流出", "生物科技 XBI / ARKG", f"{pct('XBI')} / {pct('ARKG')}", "生物科技内部偏风险收缩，TWST等个股需单独解释"],
], widths=[1.0, 1.8, 1.0, 2.5])
para("TWST 与 XLV 的关系：单只生物科技股的大涨/大跌可以由临床、监管、合作、融资或短 squeeze 驱动，不要求 XLV 同向。行业 ETF 是组合篮子，个股是事件驱动；当两者背离时，报告必须把个股原因和行业资金方向分开写。")

heading("8. Decliners & Kill Reasons")
table(["标的", "当日", "成交/状态", "当前可验证解释"], [
    ["LITE", pct("LITE"), "约" + f"{Q['LITE'].get('volume_ratio', float('nan')):.2f}x均量", "光通信硬件簇同步杀估值；单一 FCC 因素证据不足，列为板块重定价"],
    ["CIEN", pct("CIEN"), "高波动", "与 LITE/COHR/AAOI 同步，偏行业预期与仓位收缩；二手市场文章未替代公司公告"],
    ["SNDK", pct("SNDK"), "高 Beta/存储", "AI 硬件链预期降温与高位去杠杆，未找到当日新财报证据"],
    ["CRDO", pct("CRDO"), "网络互联", "Tier 2 相对弱于 Tier 1；需后续订单/客户验证"],
    ["IONQ", pct("IONQ"), "主题高 Beta", "高 Beta 与成长风险偏好收缩，暂不写成基本面单因子"],
], widths=[1.0, 1.0, 1.35, 3.0])
para("Kill reason 的写法：先写价格和成交，再写可验证事件，最后写结构性解释与待验项。没有新公告时，不把旧财报、传闻或行业图表强行包装成“今日公司事件”。")

heading("9. Where Capital Focused")
para("资金主线不是单一板块，而是三条并行路径：第一，能源与必选消费承接宏观不确定性；第二，通信服务由 META 和运营商支撑，表现为平台/现金流而非纯成长扩张；第三，科技内部从 Tier 2 高弹性硬件向 Tier 1 平台与防御性资产收缩。广度为正且 RSP 跑赢 SPY，说明有真实参与，但 QQQ 跑输 RSP、High Beta 跑输 Low Vol，说明增量资金更挑剔。")

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
        opt_rows.append([x["ticker"], x.get("expiry_near", "不可得"), f"{x.get('call_put_volume_ratio', float('nan')):.2f}", f"{x.get('max_strike_volume_share', float('nan')):.1%}", label])
table(["标的", "近月到期", "Call/Put成交量", "最大执行价成交占比", "提示"], opt_rows, widths=[.75, 1.15, 1.25, 1.4, 2.0])
chart("options_alerts.png", "公开期权链异常扫描", "Nasdaq public option-chain endpoint；检查时点 2026-10-12 19:41 ET；无执行方向确认。")
para("解读规则：CIEN 的远月执行价集中度约 46.98%、AAOI 约 21.18%、TWST 约 28.97%、MRVL 约 22.40%，说明成交/未平仓结构可能围绕少数执行价聚集，常见含义包括事件对冲、做市商库存管理、价位 pinning 或投机性集中下注；它不等于“看涨/看跌”。MU 同时触发 Call Volume/OI 与 Put Volume/OI 阈值，说明期权活跃度异常，但公开链没有买卖方向、开平仓、扫单/大宗标签，不能把它写成净买入或净卖出。")
para("期权数据限制：本次优先抓取 Nasdaq 公共链，StockWe 每笔成交方向未形成可验证数据；缺少执行侧、开平仓、IV历史与 GEX，故不编造“机构买 Call/买 Put”结论。")

heading("11. Derivatives, Gamma & Flows")
table(["指标", "数据", "结论"], [
    ["VIX / VVIX / SKEW", f"{val('^VIX')} / {val('^VVIX')} / {val('^SKEW')}", "波动率与尾部保护需求偏高，但未到恐慌级"],
    ["0DTE / GEX", "不可得", "没有公开、可审计的全市场实时 GEX，不推断正/负 Gamma"],
    ["MOC / 尾盘20分钟", "不可得", "5分钟接口本次返回空序列，不能判断 Imbalance Buy/Sell"],
    ["GS/PB / CTA", "不可得", "不披露内部净买入、总交易量或实时触发线"],
], widths=[1.5, 1.4, 3.6])
para("今天可确认的是价格与横截面结构：指数近乎平盘、广度偏正、QQQ/RSP 走弱、高 Beta/小盘走弱。因此对冲基金去杠杆是一个结构性假设，而不是已经被 PB 数据证实的事实。")

doc.add_page_break()
heading("12. Post-Bell / Next Session")
table(["时间/事件", "状态", "跟踪重点"], [
    ["10/13 美股交易日", "下一交易日", "观察 SOXX/光通信是否出现相对止跌，及 RSP-SPY 价差是否继续扩大"],
    ["JPMorgan 投资者活动", "公开日程待核", "若出现公司交流或指引，按新事件而非历史财报处理"],
    ["宏观：油价/美元/利率", "持续跟踪", "美元与油价同时上行是否继续压制高 Beta 与小盘"],
    ["指数纳入与期权", "无当前提醒", "若出现正式公告或异常执行价聚集，进入下一日报告"],
], widths=[1.6, 1.3, 3.6])

heading("13. A-Share & Hong Kong Mapping")
para("映射只做产业链方向，不把美股单日跌幅机械外推到 A/H 股。AI 硬件/光互联对应光模块、连接器、PCB、交换机、服务器和液冷；存储链对应 DRAM/NAND 与控制器；Tier 1 平台走强而 Tier 2 硬件走弱时，应优先观察 A/H 市场是否出现高位主题分化、资金向现金流和低估值环节切换。通信服务与运营商相对强，不等于 A/H 通信设备必然上涨，需要结合人民币、北向/南向和本地估值。")

heading("14. Data Appendix")
chart("breadth.png", "Appendix: breadth data", "同上；503只S&P 500成分。")
chart("factor_proxy.png", "Appendix: factor proxies", "同上；ETF代理，不等同于可交易因子组合收益。")
para("数据完整性：Yahoo Finance Chart API 取得收盘与历史收益；S&P 500 成分广度抓取成功 503/503；期权链抓取成功但为公开链快照；盘中 5分钟数据接口返回空序列，MOC/尾盘20分钟不可得；PB、CTA、真实 GEX、执行方向均不可得。所有不可得项均保留为“不可得”，没有用估计值替代。")

heading("15. Sources")
link("AP market recap（指数、板块与个股收盘摘要）", "https://apnews.com/article/f07713e8b2e438ac5903b50f5ce97235")
link("Meta 官方：Muse Wonder / Muse Wonder Full", "https://about.fb.com/news/2026/10/introducing-muse-wonder-models/")
link("Broadcom CEO AI 预期相关二手报道", "https://www.investing.com/news/stock-market-news/broadcom-ceo-says-many-ai-investors-are-gamblers-4943815")
link("Nasdaq public option chain example: LITE", "https://www.nasdaq.com/market-activity/stocks/lite/option-chain")
link("Yahoo Finance Chart API example: SPY", "https://query1.finance.yahoo.com/v8/finance/chart/SPY")
link("BLS October 2026 release schedule", "https://www.bls.gov/schedule/2026/10_sched_list.htm")
para("方法声明：本报告为收盘后复盘，不构成投资建议。公司事件优先使用官方公告；媒体和二手报道只作为待验线索。价格归因区分“已确认”“二手报道”“结构性解释”“待验”，避免把相关性写成因果性。", small=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(str(OUT))
