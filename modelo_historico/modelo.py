"""Quanto o 2º turno de 2026 se afastou do que a história dos 2º turnos (2002–2022) indica, município a município.

Alvo: parte do candidato do PT nos votos válidos do 2º turno (o PT esteve em todos os 2º turnos desde 2002).
Entradas (1º turno, sobre os aptos): PT, outro finalista, demais candidatos, brancos+nulos, abstenção; UF, região, porte.
Modelos:
- base: parte do PT entre os dois finalistas já no 1º turno (sem transferência nenhuma);
- A (transferência): votos do PT e do adversário no 2º turno como combinação não negativa dos grupos do 1º turno (regressão
  ecológica, coeficientes iguais para o país, estimados nos outros anos);
- B (gradient boosting): mesma informação + UF, região e porte, estimando a parte do PT nos válidos.
Teste: cada eleição de 2002 a 2022 é estimada com os modelos treinados nas outras 5 (deixa uma de fora). Depois, 2026 é estimado
com as 6. Grava resultados.json e previsoes.csv. Comparecimento: mesmo esquema para a variação do comparecimento entre os turnos.
Entrada e saídas em DADOS/derivados/modelo_historico/ (municipios.csv vem de montar.py).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

OUT = caminhos.saida("modelo_historico")
ANOS = [2002, 2006, 2010, 2014, 2018, 2022]
REG = {"N": "AC AM AP PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MS MT", "SE": "ES MG RJ SP", "S": "PR RS SC"}
REGIAO = {uf: r for r, ufs in REG.items() for uf in ufs.split()}
G1 = ["pt", "adv", "outros", "bn", "abs"]


def carregar():
    d = pd.read_csv(OUT / "municipios.csv", dtype={"CD_MUNICIPIO": str})
    d = d[~d["SG_UF"].isin(["VT", "ZZ"])].copy()
    d["bn_1"] = d["branco_1"] + d["nulo_1"]
    d["abs_1"] = d["QT_APTOS_1"] - d["QT_COMPARECIMENTO_1"]
    for g in G1:
        d[f"s_{g}"] = d[f"{g}_1"] / d["QT_APTOS_1"]
    d["val2"] = d["pt_2"] + d["adv_2"]
    d["y"] = d["pt_2"] / d["val2"]  # parte do PT nos válidos do 2º turno
    d["base"] = d["pt_1"] / (d["pt_1"] + d["adv_1"])
    d["comp1"] = d["QT_COMPARECIMENTO_1"] / d["QT_APTOS_1"]
    d["comp2"] = d["QT_COMPARECIMENTO_2"] / d["QT_APTOS_2"]
    d["dcomp"] = d["comp2"] - d["comp1"]
    d["regiao"] = d["SG_UF"].map(REGIAO)
    d["log_aptos"] = np.log(d["QT_APTOS_1"])
    d["uf_cod"] = d["SG_UF"].astype("category").cat.codes
    d["reg_cod"] = d["regiao"].astype("category").cat.codes
    return d.dropna(subset=["s_pt"]).reset_index(drop=True)


def transferencia(treino):
    """Coeficientes não negativos: votos do PT (e do adversário) no 2º turno, por apto, = soma dos grupos do 1º turno × coef."""
    X = treino[[f"s_{g}" for g in G1]].to_numpy()
    w = np.sqrt(treino["QT_APTOS_1"].to_numpy())
    coef = {}
    for alvo in ("pt", "adv"):
        y = (treino[f"{alvo}_2"] / treino["QT_APTOS_1"]).to_numpy()
        coef[alvo], _ = nnls(X * w[:, None], y * w)
    return coef


def prever_a(coef, df):
    X = df[[f"s_{g}" for g in G1]].to_numpy()
    pt, adv = X @ coef["pt"], X @ coef["adv"]
    return pt / (pt + adv)


FEATS = ["s_pt", "s_adv", "s_outros", "s_bn", "s_abs", "base", "comp1", "log_aptos", "uf_cod", "reg_cod"]


def gbm(treino, alvo):
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                                      categorical_features=[FEATS.index("uf_cod"), FEATS.index("reg_cod")], random_state=0)
    m.fit(treino[FEATS], treino[alvo], sample_weight=treino["QT_APTOS_1"])
    return m


def nacional(df, col):
    """Parte do PT nos válidos do país, somando a previsão de cada município com os válidos reais do 2º turno como peso."""
    return float((df[col] * df["val2"]).sum() / df["val2"].sum())


def resumo(df, cols):
    out = {"real": nacional(df, "y")}
    for c in cols:
        e = df[c] - df["y"]
        w = df["val2"]
        uf = df.assign(p=df[c] * w, r=df["y"] * w).groupby("SG_UF")[["p", "r", "val2"]].sum()
        e_uf = (uf["p"] - uf["r"]) / uf["val2"]
        # erro "geográfico": o que sobra depois de tirar o deslocamento do país inteiro (a campanha move todo mundo junto)
        desloc = float(np.average(e, weights=w))
        g = e - desloc
        g_uf = e_uf - desloc
        out[c] = {"nacional": nacional(df, c), "erro_nacional": nacional(df, c) - out["real"],
                  "mae_municipio": float(np.average(e.abs(), weights=w)), "rmse_municipio": float(np.sqrt(np.average(e ** 2, weights=w))),
                  "mae_uf": float(e_uf.abs().mean()), "max_uf": float(e_uf.abs().max()), "uf_max": e_uf.abs().idxmax(),
                  "geo_mae_municipio": float(np.average(g.abs(), weights=w)), "geo_mae_uf": float(g_uf.abs().mean()),
                  "geo_max_uf": float(g_uf.abs().max()), "geo_uf_max": g_uf.abs().idxmax(),
                  "geo_mun_10": float(np.average((g.abs() > 0.10), weights=w)), "erro_uf": {k: float(v) for k, v in e_uf.items()}}
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = carregar()
    hist = d[d["ano"].isin(ANOS)]
    res = {"teste": {}, "coef": {}}
    prevs = []
    for ano in ANOS + [2026]:
        treino = hist[hist["ano"] != ano]
        alvo_df = d[d["ano"] == ano].copy()
        coef = transferencia(treino)
        res["coef"][str(ano)] = {k: dict(zip(G1, map(float, v))) for k, v in coef.items()}
        alvo_df["prev_a"] = prever_a(coef, alvo_df)
        alvo_df["prev_b"] = gbm(treino, "y").predict(alvo_df[FEATS])
        alvo_df["prev_dcomp"] = gbm(treino, "dcomp").predict(alvo_df[FEATS])
        prevs.append(alvo_df)
        tem_2t = alvo_df.dropna(subset=["y"])
        if len(tem_2t):
            r = resumo(tem_2t, ["base", "prev_a", "prev_b"])
            r["comparecimento"] = {"real": float((tem_2t["dcomp"] * tem_2t["QT_APTOS_1"]).sum() / tem_2t["QT_APTOS_1"].sum()),
                                   "previsto": float((tem_2t["prev_dcomp"] * tem_2t["QT_APTOS_1"]).sum() / tem_2t["QT_APTOS_1"].sum())}
            r["municipios"] = int(len(tem_2t))
            res["teste"][str(ano)] = r
            print(ano, f"real {100 * r['real']:.2f}", *(f"{c}: {100 * r[c]['nacional']:.2f} (erro {100 * r[c]['erro_nacional']:+.2f}; "
                  f"mun {100 * r[c]['mae_municipio']:.2f}; UF {100 * r[c]['mae_uf']:.2f})" for c in ("base", "prev_a", "prev_b")),
                  f"| comparecimento real {100 * r['comparecimento']['real']:+.2f} prev {100 * r['comparecimento']['previsto']:+.2f}",
                  f"| {r['municipios']} mun", sep="  ")
    pd.concat(prevs).to_csv(OUT / "previsoes.csv", index=False)
    json.dump(res, open(OUT / "resultados.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res["coef"], indent=1)[:1500])


if __name__ == "__main__":
    main()
