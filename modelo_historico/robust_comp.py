"""Quão robusto é o comparecimento 'esperado' para 2026 (−0,1)? Retreina o gradient boosting tirando um ano de cada vez,
compara com um modelo linear e com a média simples dos anos anteriores, e mede o acerto de cada um no teste deixando um ano de fora.
Lê DADOS/derivados/modelo_historico/municipios.csv (via modelo.carregar) e só imprime: é a origem dos números de comparecimento
esperado com e sem 2022 (−0,1 e −2,1) escritos em texto.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import modelo as m  # noqa: E402

d = m.carregar()
ANOS = list(m.ANOS)
hist = d[d["ano"].isin(ANOS)]


def nac(df, col):
    return 100 * float((df[col] * df["QT_APTOS_1"]).sum() / df["QT_APTOS_1"].sum())


def linear(treino, alvo_df):
    cols = ["s_pt", "s_adv", "s_outros", "s_bn", "s_abs", "base", "comp1", "log_aptos"]
    X = np.column_stack([np.ones(len(treino)), treino[cols].to_numpy()])
    w = np.sqrt(treino["QT_APTOS_1"].to_numpy())
    beta, *_ = np.linalg.lstsq(X * w[:, None], treino["dcomp"].to_numpy() * w, rcond=None)
    return np.column_stack([np.ones(len(alvo_df)), alvo_df[cols].to_numpy()]) @ beta


real = {a: nac(d[d["ano"] == a].dropna(subset=["dcomp"]), "dcomp") for a in ANOS + [2026]}
print("real", {a: round(v, 2) for a, v in real.items()})

# 1) teste deixando um ano de fora: GBM, linear e média dos outros anos
erros = {"gbm": [], "linear": [], "media": []}
for a in ANOS:
    treino, alvo = hist[hist["ano"] != a], d[d["ano"] == a].copy()
    alvo["g"] = m.gbm(treino, "dcomp").predict(alvo[m.FEATS])
    alvo["l"] = linear(treino, alvo)
    media = np.mean([real[b] for b in ANOS if b != a])
    pg, pl = nac(alvo, "g"), nac(alvo, "l")
    erros["gbm"].append(pg - real[a]); erros["linear"].append(pl - real[a]); erros["media"].append(media - real[a])
    print(a, f"real {real[a]:+.2f} | gbm {pg:+.2f} | linear {pl:+.2f} | média dos outros {media:+.2f}")
print("erro médio absoluto:", {k: round(float(np.mean(np.abs(v))), 2) for k, v in erros.items()})

# 2) 2026 com todos os anos e tirando um ano de cada vez
alvo = d[d["ano"] == 2026].copy()
alvo["g"] = m.gbm(hist, "dcomp").predict(alvo[m.FEATS])
alvo["l"] = linear(hist, alvo)
print(f"2026 todos: gbm {nac(alvo, 'g'):+.2f} | linear {nac(alvo, 'l'):+.2f} | média {np.mean([real[b] for b in ANOS]):+.2f}")
for fora in ANOS:
    treino = hist[hist["ano"] != fora]
    alvo["g"] = m.gbm(treino, "dcomp").predict(alvo[m.FEATS])
    alvo["l"] = linear(treino, alvo)
    print(f"2026 sem {fora}: gbm {nac(alvo, 'g'):+.2f} | linear {nac(alvo, 'l'):+.2f}")

# 3) o que diferencia 2026: features médias por ano
cols = ["s_outros", "s_bn", "s_abs", "comp1", "base"]
print(d.assign(**{c: d[c] * d["QT_APTOS_1"] for c in cols}).groupby("ano")[cols + ["QT_APTOS_1"]].sum()
      .pipe(lambda g: g[cols].div(g["QT_APTOS_1"], axis=0) * 100).round(1))
