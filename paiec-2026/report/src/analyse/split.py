# Split-Term D = E(R_acq - R_eval)^2 bei 50/50-Teilung je Paar, aus paare.parquet (items, r), Naeherung ohne Item-Heterogenitaet:
# Var(R_half) um R = p(1-p)/N_half * (1 - N_half/N) (endliche Population, Items austauschbar) -> E(R_acq-R_eval)^2 ~ 2*p(1-p)/N_half*(1-1/2) = p(1-p)*2/N  (N = items)
import pandas as pd, numpy as np, json
import os
W=os.environ["PAIEC_WORK"].rstrip("/")+"/modell/"  # lokale Datenbasis (README, Schritt 0)
p=pd.read_parquet(W+"paare.parquet")
p=p[p["items"]>=80]
# 30er-Kappung je Benchmark nicht nachgebaut; zwei Gewichtungen: alle Paare / benchmark-balanciert
D_pair = (p.r*(1-p.r)*2/p["items"])
out={"paare":len(p),"items_median":float(p["items"].median()),
 "D_alle_paare":float(D_pair.mean()),
 "D_bm_balanciert":float(D_pair.groupby(p.b_code).mean().mean()),
 "D_cap30":None}
rng=np.random.default_rng(0)
cap=p.groupby("b_code",group_keys=False).apply(lambda x: x.sample(min(len(x),30),random_state=0))
out["D_cap30"]=float((cap.r*(1-cap.r)*2/cap["items"]).mean()); out["paare_cap30"]=len(cap)
# Vorhersage B31 fuer BB mit kappa=2.73, V0=0.0673, U=0.1833 plus Split-Term
U,V0,k=0.1833,0.0673,2.73
for D in (out["D_cap30"],):
    pred={int(B):round((B*U+k*k*V0)/(B+k)**2 + (B/(B+k))**2*D,4) for B in (1,3,7,15,31)}
out["BB_vorhersage_mit_split_kappa2.73"]=pred
out["BB_beobachtet"]={1:0.0498,3:0.0329,7:0.0197,15:0.0113,31:0.0065}
json.dump(out,open("split.json","w"),indent=1); print(json.dumps(out,indent=1))
