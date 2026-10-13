"""Build transparent, price-based rotation metrics and PNGs for a daily recap."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
SEMI = ["NVDA", "AVGO", "AMD", "MU", "MRVL", "QCOM", "ADI", "TXN", "INTC", "AMAT", "LRCX", "KLAC"]
SOFTWARE = ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "SNOW", "DDOG", "MDB", "WDAY", "CRWD", "PANW", "ZS"]
TECH_EX = ["AVGO", "AMD", "QCOM", "CRM", "NOW", "ADBE", "ANET", "MU", "MRVL", "CRDO", "ALAB", "HPE", "DELL", "SMCI"]
AI_CAPEX = ["NVDA", "AVGO", "AMD", "MU", "MRVL", "CRDO", "ANET", "HPE", "DELL", "SMCI", "VRT", "ETN", "PWR", "CEG", "NRG", "APLD"]
AI_APPS = ["MSFT", "GOOGL", "AMZN", "META", "ORCL", "CRM", "NOW", "ADBE", "SNOW", "DDOG", "MDB", "CRWD"]
CYCLICAL = ["XLI", "XLB", "XLE", "XLF", "XLY"]
DEFENSIVE = ["XLP", "XLV", "XLU"]
SECTOR_LABELS = {"XLK": "XLK（科技）", "XLC": "XLC（通信服务）", "XLY": "XLY（可选消费）", "XLF": "XLF（金融）", "XLI": "XLI（工业）", "XLE": "XLE（能源）", "XLB": "XLB（材料）", "XLV": "XLV（医疗保健）", "XLP": "XLP（必选消费）", "XLRE": "XLRE（房地产）", "XLU": "XLU（公用事业）"}
# The broad-sector map is intentionally paired with the most decision-useful
# industry proxies so that XLV/XLU cannot hide biotech, power, or other
# concentrated single-stock moves.
ROTATION_MAP = [
    "XLK", "XLC", "XLY", "XLP", "XLF", "XLI", "XLE", "XLB", "XLV", "XLRE", "XLU",
    "SOXX", "SMH", "IGV", "CIBR", "SKYY", "XBI", "IBB", "IHI", "XHE", "ARKG",
    "XME", "COPX", "GDX", "KRE", "XRT", "XHB", "ITA", "ARKK",
]
SUBSECTOR_LABELS = {
    "SOXX": "SOXX（半导体）", "SMH": "SMH（半导体）", "IGV": "IGV（软件）",
    "CIBR": "CIBR（网络安全）", "SKYY": "SKYY（云计算）",
    "XBI": "XBI（生物医药）", "IBB": "IBB（生物医药）",
    "IHI": "IHI（医疗器械）", "XHE": "XHE（医疗器械）",
    "ARKG": "ARKG（基因组学）", "XME": "XME（金属与矿业）",
    "COPX": "COPX（铜矿）", "GDX": "GDX（黄金矿业）", "KRE": "KRE（区域银行）",
    "XRT": "XRT（零售）", "XHB": "XHB（住宅建筑）", "ITA": "ITA（航空航天国防）",
    "ARKK": "ARKK（创新成长）",
}

def load_close(root: Path, symbol: str) -> pd.Series | None:
    p = root / (symbol.replace("^", "idx_").replace("=", "_") + "_daily.csv")
    if not p.exists(): return None
    x = pd.read_csv(p)
    if "Date" not in x or "Close" not in x: return None
    return pd.Series(pd.to_numeric(x["Close"], errors="coerce").values, index=pd.to_datetime(x["Date"])).dropna().sort_index()

def basket(root: Path, names: list[str]) -> pd.DataFrame:
    xs = {s: load_close(root, s) for s in names}
    xs = {s: x for s, x in xs.items() if x is not None}
    return pd.concat(xs, axis=1).dropna(how="all") if xs else pd.DataFrame()

def stats(df: pd.DataFrame, spy: pd.Series | None) -> dict:
    if df.empty: return {"n": 0}
    ret = df.pct_change()
    last = ret.iloc[-1].dropna()
    def ew(n): return float(df.pct_change(n).iloc[-1].mean() * 100)
    out = {"n": int(len(last)), "equal_weight_1d": float(last.mean()*100), "median_1d": float(last.median()*100),
           "advancing_pct": float((last>0).mean()*100), "above_2_pct": int((last>0.02).sum()), "below_2_pct": int((last<-0.02).sum()),
           "equal_weight_5d": ew(5), "equal_weight_20d": ew(20)}
    if spy is not None:
        sr = spy.pct_change().reindex(df.index)
        out["outperforming_spy_pct"] = float((last - sr.iloc[-1] > 0).mean()*100) if pd.notna(sr.iloc[-1]) else None
    return out

def regime(one, five, twenty, breadth, volume):
    if any(pd.isna(x) for x in [one, five, twenty]): return "UNCLEAR"
    if abs(one) < 0.002 and abs(five) < 0.005: return "NOISE"
    if one * twenty < 0 and abs(one) > 0.01: return "REVERSING"
    if abs(twenty) > 0.10 and abs(five) > 0.03: return "EXTENDED"
    if abs(one) > 0.005 and abs(five) > 0.01 and (breadth is None or abs(breadth) > 10) and volume:
        return "CONFIRMED"
    if abs(one) > 0.005: return "EMERGING"
    return "UNCLEAR"

def relative_return_gap(a1: pd.Series, a2: pd.Series, n: int) -> float:
    """Return compounded n-session performance gap in decimal form."""
    if len(a1) <= n or len(a2) <= n:
        return float("nan")
    return (a1.iloc[-1] / a1.iloc[-n-1] - 1) - (a2.iloc[-1] / a2.iloc[-n-1] - 1)

def observation_payload(semi_stats: dict, software_stats: dict, mag7_stats: dict) -> dict:
    semi_1d = float(semi_stats.get("equal_weight_1d", float("nan")))
    software_1d = float(software_stats.get("equal_weight_1d", float("nan")))
    spread = semi_1d - software_1d
    return {
        "semi_software": {
            "semi_equal_weight_1d": semi_1d,
            "software_equal_weight_1d": software_1d,
            "spread_1d": spread,
            "relative_winner": "Semi" if spread > 0 else "Software" if spread < 0 else "Tie",
            "semi_absolute_direction": "up" if semi_1d > 0 else "down" if semi_1d < 0 else "flat",
            "software_absolute_direction": "up" if software_1d > 0 else "down" if software_1d < 0 else "flat",
            "breadth_confirmation": semi_stats.get("advancing_pct", float("nan")) > 50 and software_stats.get("advancing_pct", float("nan")) < 50 if spread > 0 else software_stats.get("advancing_pct", float("nan")) > 50 and semi_stats.get("advancing_pct", float("nan")) < 50 if spread < 0 else False,
        },
        "mag7": {
            "equal_weight_1d": float(mag7_stats.get("equal_weight_1d", float("nan"))),
            "advancing_pct": float(mag7_stats.get("advancing_pct", float("nan"))),
            "regime_hint": "broad_strength" if mag7_stats.get("advancing_pct", 0) >= 70 and mag7_stats.get("equal_weight_1d", 0) > 0 else "broad_weakness" if mag7_stats.get("advancing_pct", 100) <= 30 and mag7_stats.get("equal_weight_1d", 0) < 0 else "fragmented",
        },
    }

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", required=True); ap.add_argument("--root", default=None); a=ap.parse_args()
    root = Path(a.root) if a.root else Path("D:/codex/outputs/us_market_daily_recaps") / a.date
    out = root; out.mkdir(parents=True, exist_ok=True)
    spy = load_close(root, "SPY"); soxx = load_close(root, "SOXX"); igv = load_close(root, "IGV")
    pairs = [("Semi - Software", soxx, igv), ("Mag7 - Tech ex-Mag7", basket(root,MAG7).mean(axis=1), basket(root,TECH_EX).mean(axis=1)), ("Mag7 - RSP", basket(root,MAG7).mean(axis=1), load_close(root,"RSP")), ("QQQ - RSP", load_close(root,"QQQ"), load_close(root,"RSP")), ("Growth - Defensive", load_close(root,"QQQ"), basket(root,DEFENSIVE).mean(axis=1)), ("Cyclical - Defensive", basket(root,CYCLICAL).mean(axis=1), basket(root,DEFENSIVE).mean(axis=1)), ("AI CapEx - AI Applications", basket(root,AI_CAPEX).mean(axis=1), basket(root,AI_APPS).mean(axis=1)), ("High Beta - Low Vol", load_close(root,"SPHB"), load_close(root,"USMV")), ("Small Cap - Large Cap", load_close(root,"IWM"), load_close(root,"SPY"))]
    rows=[]
    for name,a1,a2 in pairs:
        if a1 is None or a2 is None: continue
        z=pd.concat([a1,a2],axis=1).dropna(); r=z.pct_change(); sp=r.iloc[:,0]-r.iloc[:,1]; one=float(sp.iloc[-1]); five=relative_return_gap(z.iloc[:,0],z.iloc[:,1],5); twenty=relative_return_gap(z.iloc[:,0],z.iloc[:,1],20); s={"pair":name,"1d":float(one*100),"5d":float(five*100),"20d":float(twenty*100),"regime":regime(one,five,twenty,None,True),"basis":"price-based rotation proxy"}; rows.append(s)
    pd.DataFrame(rows).to_csv(out/"rotation_matrix.csv",index=False)
    basket_stats={"semi":stats(basket(root,SEMI),spy),"software":stats(basket(root,SOFTWARE),spy),"mag7":stats(basket(root,MAG7),spy)}
    payload={"date":a.date,"basis":"price-based rotation proxy","baskets":{"semi":SEMI,"software":SOFTWARE,"tech_ex_mag7":TECH_EX,"ai_capex":AI_CAPEX,"ai_applications":AI_APPS,"cyclical":CYCLICAL,"defensive":DEFENSIVE},"stats":basket_stats,"observations":observation_payload(basket_stats["semi"],basket_stats["software"],basket_stats["mag7"]),"matrix":rows}
    (out/"rotation_engine.json").write_text(json.dumps(payload,indent=2,allow_nan=False),encoding="utf-8")
    plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":9,"axes.spines.top":False,"axes.spines.right":False})
    if soxx is not None and igv is not None:
        z=pd.concat([soxx,igv],axis=1).dropna().tail(20); z=z/z.iloc[0]*100; z.columns=["SOXX","IGV"]; ax=z.plot(figsize=(8,3.5),color=["#1f77b4","#d62728"],title="Semi vs Software Relative Performance"); ax.set_ylabel("T-20 = 100"); ax.figure.tight_layout(); ax.figure.savefig(out/"rotation_semi_software.png",dpi=180); plt.close(ax.figure)
        sp=soxx.pct_change().sub(igv.pct_change(),fill_value=np.nan).dropna().tail(20)*100; fig,ax=plt.subplots(figsize=(8,3)); ax.bar(sp.index.strftime("%m-%d"),sp,color=np.where(sp>=0,"#1f77b4","#d62728")); ax.axhline(0,color="black",lw=.7); ax.set_title("Semi - Software Daily Spread"); ax.set_ylabel("percentage points"); ax.tick_params(axis="x",rotation=60); fig.tight_layout(); fig.savefig(out/"rotation_semi_software_spread.png",dpi=180); plt.close(fig)
    m=basket(root,MAG7); spy2=spy.reindex(m.index) if spy is not None else None; heat=pd.DataFrame({"1D":m.pct_change().iloc[-1]*100,"5D":m.pct_change(5).iloc[-1]*100,"20D":m.pct_change(20).iloc[-1]*100,"vs SPY":(m.pct_change().iloc[-1]-spy2.pct_change().iloc[-1])*100 if spy2 is not None else np.nan}); fig,ax=plt.subplots(figsize=(6.5,3.2)); im=ax.imshow(heat.fillna(0),cmap="RdYlGn",aspect="auto",vmin=-6,vmax=6); ax.set_xticks(range(4),heat.columns); ax.set_yticks(range(len(heat)),heat.index); ax.set_title("Mag7 Internal Rotation"); [ax.text(j,i,f"{heat.iloc[i,j]:+.1f}%",ha="center",va="center",fontsize=8) for i in range(len(heat)) for j in range(4)]; fig.colorbar(im,ax=ax,shrink=.7); fig.tight_layout(); fig.savefig(out/"rotation_mag7_heatmap.png",dpi=180); plt.close(fig)
    leadership={"Mag7":MAG7,"Tech ex-Mag7":TECH_EX,"Semi":SEMI,"Software":SOFTWARE,"AI CapEx":AI_CAPEX,"AI Applications":AI_APPS,"Cyclicals":CYCLICAL,"Defensives":DEFENSIVE,"Small Cap":["IWM"]}
    lm=[]
    for label,names in leadership.items():
        x=basket(root,names) if len(names)>1 else basket(root,names)
        if x.empty: continue
        rr=x.pct_change(); lm.append([label,float(rr.iloc[-1].mean()*100),float(x.pct_change(5).iloc[-1].mean()*100),float(x.pct_change(20).iloc[-1].mean()*100)])
    lh=pd.DataFrame(lm,columns=["basket","1D","5D","20D"]).set_index("basket"); fig,ax=plt.subplots(figsize=(6.8,4.4)); im=ax.imshow(lh.fillna(0),cmap="RdYlGn",aspect="auto",vmin=-8,vmax=8); ax.set_xticks(range(3),lh.columns); ax.set_yticks(range(len(lh)),lh.index); ax.set_title("Leadership Rotation Heatmap"); [ax.text(j,i,f"{lh.iloc[i,j]:+.1f}%",ha="center",va="center",fontsize=8) for i in range(len(lh)) for j in range(3)]; fig.colorbar(im,ax=ax,shrink=.7); fig.tight_layout(); fig.savefig(out/"rotation_leadership_heatmap.png",dpi=180); plt.close(fig)
    sectors=ROTATION_MAP; sm=[]
    for s in sectors:
        x=load_close(root,s)
        if x is not None and len(x)>20: sm.append([s,float(x.pct_change().iloc[-1]*100),float(x.pct_change(5).iloc[-1]*100),float(x.pct_change(20).iloc[-1]*100)])
    sh=pd.DataFrame(sm,columns=["sector","1D","5D","20D"]).set_index("sector");
    if not sh.empty:
        fig,ax=plt.subplots(figsize=(7.8,max(6.4,0.30*len(sh)+1.4))); im=ax.imshow(sh,cmap="RdYlGn",aspect="auto",vmin=-8,vmax=8); ax.set_xticks(range(3),sh.columns); ax.set_yticks(range(len(sh)),[SECTOR_LABELS.get(s, SUBSECTOR_LABELS.get(s,s)) for s in sh.index]); ax.set_title("Sector & Industry Rotation Map"); [ax.text(j,i,f"{sh.iloc[i,j]:+.1f}%",ha="center",va="center",fontsize=7.5) for i in range(len(sh)) for j in range(3)]; fig.colorbar(im,ax=ax,shrink=.7); fig.tight_layout(); fig.savefig(out/"rotation_sector_heatmap.png",dpi=180); plt.close(fig)
        sh.to_csv(out/"rotation_sector_heatmap.csv")
    sub_rows=[]
    for s in SUBSECTOR_LABELS:
        x=load_close(root,s)
        if x is not None and len(x)>20:
            sub_rows.append([s,float(x.pct_change().iloc[-1]*100),float(x.pct_change(5).iloc[-1]*100),float(x.pct_change(20).iloc[-1]*100)])
    subh=pd.DataFrame(sub_rows,columns=["subsector","1D","5D","20D"]).set_index("subsector") if sub_rows else pd.DataFrame()
    if not subh.empty:
        subh.to_csv(out/"rotation_subsector.csv")
        fig,ax=plt.subplots(figsize=(7.2,max(3.6,0.38*len(subh)+1.2))); im=ax.imshow(subh,cmap="RdYlGn",aspect="auto",vmin=-8,vmax=8); ax.set_xticks(range(3),subh.columns); ax.set_yticks(range(len(subh)),[SUBSECTOR_LABELS.get(s,s) for s in subh.index]); ax.set_title("Sub-sector Rotation Map"); [ax.text(j,i,f"{subh.iloc[i,j]:+.1f}%",ha="center",va="center",fontsize=8) for i in range(len(subh)) for j in range(3)]; fig.colorbar(im,ax=ax,shrink=.7); fig.tight_layout(); fig.savefig(out/"rotation_subsector_heatmap.png",dpi=180); plt.close(fig)
    else:
        (out/"rotation_subsector.csv").write_text("subsector,1D,5D,20D\n",encoding="utf-8")
    cache=out.parent/"rotation_cache"; cache.mkdir(parents=True,exist_ok=True); cache_file=cache/"rotation_history.csv"; cache_rows=pd.DataFrame(rows); cache_rows.insert(0,"date",a.date)
    if cache_file.exists():
        old=pd.read_csv(cache_file); cache_rows=pd.concat([old,cache_rows],ignore_index=True).drop_duplicates(["date","pair"],keep="last")
    cache_rows.to_csv(cache_file,index=False)
    print(json.dumps({"date":a.date,"matrix_rows":len(rows),"output":str(out)},ensure_ascii=False))
if __name__ == "__main__": main()
