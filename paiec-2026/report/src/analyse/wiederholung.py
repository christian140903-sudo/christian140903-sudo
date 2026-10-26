# Irreduzible Schranke aus Wiederholungs-Labels (Subjekt x Item mit n>=2), python3 -I
import pyarrow.parquet as pq, pyarrow.compute as pc, pyarrow as pa, numpy as np, pandas as pd, json, sys
import os
W=os.environ["PAIEC_WORK"].rstrip("/")+"/modell/"  # lokale Datenbasis (README, Schritt 0)
t=pq.read_table(W+"agg.parquet")
n=t["n"].to_numpy().astype(np.float64); k=t["k"].to_numpy().astype(np.float64); b=t["b_code"].to_numpy()
tot_rows=len(n); tot_resp=n.sum()
rep=n>=2
out={}
out["zeilen_gesamt"]=int(tot_rows); out["antworten_gesamt"]=int(tot_resp)
out["zeilen_mit_wiederholung"]=int(rep.sum()); out["anteil_zeilen_wdh"]=float(rep.mean())
out["anteil_antworten_in_wdh_zellen"]=float(n[rep].sum()/tot_resp)
# unverzerrter Schätzer der Zellvarianz p(1-p): k(n-k)/(n(n-1))
v=np.zeros_like(n); v[rep]=k[rep]*(n[rep]-k[rep])/(n[rep]*(n[rep]-1))
# Brier-Schranke bei bekannter Zell-Wahrscheinlichkeit, antwortgewichtet, nur Zellen mit n>=2
out["schranke_antwortgewichtet_nur_wdh"]=float((n[rep]*v[rep]).sum()/n[rep].sum())
# zellgewichtet
out["schranke_zellgewichtet_nur_wdh"]=float(v[rep].mean())
# k/n-Orakel (verzerrt, n=1 -> 0), über alle Zellen antwortgewichtet (Vergleich zu C L9 0,0065)
kn=k*(n-k)/np.maximum(n,1)
out["orakel_kn_alle_zellen"]=float(kn.sum()/tot_resp)
# Vergleich: Bernoulli-Varianz der Zellrate (p_hat(1-p_hat)) in Wdh-Zellen = Obergrenze, Item-Ebene
ph=k[rep]/n[rep]; out["phat_1_minus_phat_wdh"]=float((n[rep]*ph*(1-ph)).sum()/n[rep].sum())
# je Benchmark
df=pd.DataFrame({"b":b,"n":n,"k":k,"v":v,"rep":rep})
g=df[df.rep].groupby("b").apply(lambda x: pd.Series({"zellen":len(x),"antw":x.n.sum(),"schranke":(x.n*x.v).sum()/x.n.sum(),"n_median":x.n.median(),"n_max":x.n.max()}))
g=g[g.zellen>=100]
out["benchmarks_mit_>=100_wdh_zellen"]=int(len(g))
out["schranke_je_bm_quantile"]={q:float(g.schranke.quantile(q)) for q in (0.1,0.25,0.5,0.75,0.9)}
out["schranke_bm_balanciert_mittel"]=float(g.schranke.mean())
bm=pd.read_parquet(W+"benchmarks.parquet")
namecol=[c for c in bm.columns if c in ("folder","name","benchmark_id")]
g2=g.reset_index().merge(bm[["b_code"]+namecol].rename(columns={"b_code":"b"}),on="b",how="left").sort_values("schranke",ascending=False)
out["top10"]=g2.head(10).to_dict(orient="records"); out["bottom5"]=g2.tail(5).to_dict(orient="records")
# Anteil der R(1-R)-Untergrenze (0,1833) der irreduzibel ist: Vergleich innerhalb Wdh-Zellen
# Für dieselben Zellen: Paar-Untergrenze = Varianz um Paarrate; wir nehmen die Zell-Rate-Varianz dazu
json.dump(out,open("wiederholung.json","w"),indent=1,default=str)
print(json.dumps(out,indent=1,default=str))
