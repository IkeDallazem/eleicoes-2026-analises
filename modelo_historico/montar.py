"""Base municipal de presidente, 1º e 2º turno, 2002–2026 (sem o exterior). Grava municipios.csv: uma linha por ano × município,
com aptos, comparecimento e votos de cada grupo nos dois turnos.

Grupos: pt = candidato do PT (número 13, que esteve em todos os 2º turnos desde 2002); adv = o outro finalista; outros = demais
candidatos do 1º turno; branco (95); nulo (96 e anulados). Fontes:
- 2002–2022 e 1º turno de 2026: votacao_secao_<ano>_BR (votos por seção, somados por município) e detalhe_votacao_munzona
  (aptos e comparecimento, somados por município).
- 2º turno de 2026: arquivo de resultado de cada município no site de resultados do TSE (DADOS/tse/res2026_2t), já que os dados
  abertos de 2026 usados aqui só trazem o 1º turno.
Entradas (baixar.py e abstencao/baixar.py): DADOS/tse/hist/*.zip, DADOS/tse/votacao_secao_2026_BR.zip,
DADOS/tse/detalhe_votacao_munzona_2026.zip e DADOS/tse/res2026_2t/. Saída: DADOS/derivados/modelo_historico/municipios.csv.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

HIST = caminhos.TSE / "hist"
OUT = caminhos.saida("modelo_historico")
ANOS = (2002, 2006, 2010, 2014, 2018, 2022)


def secao(src):
    """Votos de presidente por (turno, uf, município, número), de um CSV ou zip de votação por seção."""
    cols = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"]
    parts = []
    if str(src).lower().endswith(".zip"):  # o zip traz também o leiame.pdf
        z = zipfile.ZipFile(src)
        src = z.open(next(n for n in z.namelist() if n.lower().endswith(".csv")))
    reader = pd.read_csv(src, sep=";", encoding="latin-1", usecols=cols, dtype=str, chunksize=2_000_000)
    for chunk in reader:
        chunk = chunk[(chunk["CD_CARGO"].astype(int) == 1) & (chunk["SG_UF"] != "ZZ")]
        chunk = chunk.assign(QT_VOTOS=chunk["QT_VOTOS"].astype(int), NR_TURNO=chunk["NR_TURNO"].astype(int),
                             CD_MUNICIPIO=chunk["CD_MUNICIPIO"].str.zfill(5), NR_VOTAVEL=chunk["NR_VOTAVEL"].astype(int))
        parts.append(chunk.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum())
    return pd.concat(parts).groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()


def detalhe(zip_path):
    """Aptos e comparecimento de presidente por (turno, uf, município). Lê os CSVs por UF (sem o BRASIL, que repete)."""
    z = zipfile.ZipFile(zip_path)
    names = [n for n in z.namelist() if n.lower().endswith(".csv") and "BRASIL" not in n.upper()]
    frames = []
    for n in names:
        df = pd.read_csv(z.open(n), sep=";", encoding="latin-1", dtype=str,
                         usecols=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO", "ST_VOTO_EM_TRANSITO"])
        frames.append(df[(df["CD_CARGO"].astype(int) == 1) & (df["SG_UF"] != "ZZ")])
    df = pd.concat(frames).drop_duplicates()  # o arquivo _BR e os das UFs podem trazer as mesmas linhas de presidente
    for c in ("QT_APTOS", "QT_COMPARECIMENTO", "NR_TURNO"):
        df[c] = df[c].astype(int)
    df["CD_MUNICIPIO"] = df["CD_MUNICIPIO"].str.zfill(5)
    return df.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"], as_index=False)[["QT_APTOS", "QT_COMPARECIMENTO"]].sum()


def largo(votos, det, ano, adv):
    """Uma linha por município: aptos/comparecimento e grupos de votos nos dois turnos."""
    v = votos.copy()
    v["grupo"] = "outros"
    v.loc[v["NR_VOTAVEL"] == 13, "grupo"] = "pt"
    v.loc[v["NR_VOTAVEL"] == adv, "grupo"] = "adv"
    v.loc[v["NR_VOTAVEL"] == 95, "grupo"] = "branco"
    v.loc[v["NR_VOTAVEL"].isin([96, 97]), "grupo"] = "nulo"
    g = v.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "grupo"])["QT_VOTOS"].sum().unstack("grupo", fill_value=0)
    g = g.join(det.set_index(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"]))
    t1, t2 = g.xs(1, level="NR_TURNO"), g.xs(2, level="NR_TURNO")
    out = t1.add_suffix("_1").join(t2.add_suffix("_2"), how="inner").reset_index()
    out.insert(0, "ano", ano)
    return out


def finalista(votos):
    """Número do outro finalista: o mais votado no 2º turno que não é o 13 nem branco/nulo."""
    t2 = votos[(votos["NR_TURNO"] == 2) & (~votos["NR_VOTAVEL"].isin([13, 95, 96, 97]))]
    return int(t2.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().idxmax())


def res2026_2t():
    rows = []
    for f in sorted((caminhos.TSE / "res2026_2t").glob("*.json")):
        d = json.load(open(f, encoding="utf-8"))
        cand = {}
        for agr in d["carg"][0]["agr"]:
            for par in agr["par"]:
                for c in par["cand"]:
                    cand[int(c["n"])] = int(c["vap"])
        e, v = d["e"], d["v"]
        rows.append({"NR_TURNO": 2, "SG_UF": f.stem[:2].upper(), "CD_MUNICIPIO": d["cdabr"].zfill(5), "QT_APTOS": int(e["te"]),
                     "QT_COMPARECIMENTO": int(e["c"]), "pt": cand.get(13, 0), "adv": cand.get(22, 0), "branco": int(v["vb"]),
                     "nulo": int(v["tvn"]), "outros": 0})
    return pd.DataFrame(rows)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    bases, check = [], []
    for ano in ANOS:
        votos = secao(HIST / f"votacao_secao_{ano}_BR.zip")
        det = detalhe(HIST / f"detalhe_votacao_munzona_{ano}.zip")
        adv = finalista(votos)
        base = largo(votos, det, ano, adv)
        base["adv_num"] = adv
        bases.append(base)
        for t in (1, 2):
            sv = votos[votos["NR_TURNO"] == t]["QT_VOTOS"].sum()
            dc = det[det["NR_TURNO"] == t]["QT_COMPARECIMENTO"].sum()
            check.append((ano, t, int(sv), int(dc), int(det[det["NR_TURNO"] == t]["QT_APTOS"].sum())))
        print(ano, "finalista", adv, "municípios", len(base), flush=True)
    # 2026: 1º turno do arquivo por seção (mesmo formato do histórico); 2º turno dos resultados por município
    votos26 = secao(caminhos.TSE / "votacao_secao_2026_BR.zip")
    det26 = detalhe_csv(caminhos.TSE / "detalhe_votacao_munzona_2026.zip")
    t1 = votos26[votos26["NR_TURNO"] == 1]
    g1 = largo_um(t1, det26[det26["NR_TURNO"] == 1], adv=22)
    r2 = res2026_2t().set_index(["SG_UF", "CD_MUNICIPIO"]).drop(columns="NR_TURNO")
    b26 = g1.join(r2.add_suffix("_2"), how="left").reset_index()
    b26.insert(0, "ano", 2026)
    b26["adv_num"] = 22
    bases.append(b26)
    check.append((2026, 1, int(t1["QT_VOTOS"].sum()), int(det26[det26["NR_TURNO"] == 1]["QT_COMPARECIMENTO"].sum()),
                  int(det26[det26["NR_TURNO"] == 1]["QT_APTOS"].sum())))
    df = pd.concat(bases, ignore_index=True)
    df.to_csv(OUT / "municipios.csv", index=False)
    print(pd.DataFrame(check, columns=["ano", "turno", "votos_secao", "comparecimento_detalhe", "aptos"]).to_string())
    print("2026 municípios com 2º turno:", int(b26["pt_2"].notna().sum()), "de", len(b26))


def detalhe_csv(src):
    """Aptos e comparecimento de presidente por (turno, uf, município), do arquivo _BR (só presidente) do detalhe de 2026."""
    if str(src).lower().endswith(".zip"):  # o zip traz um CSV por UF, o _BR, o _BRASIL e o leiame.pdf: usa só o _BR
        z = zipfile.ZipFile(src)
        src = z.open(next(n for n in z.namelist() if n.upper().endswith("_BR.CSV")))
    df = pd.read_csv(src, sep=";", encoding="latin-1", dtype=str,
                     usecols=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO"])
    df = df[(df["CD_CARGO"].astype(int) == 1) & (df["SG_UF"] != "ZZ")].drop_duplicates()
    for c in ("QT_APTOS", "QT_COMPARECIMENTO", "NR_TURNO"):
        df[c] = df[c].astype(int)
    df["CD_MUNICIPIO"] = df["CD_MUNICIPIO"].str.zfill(5)
    return df.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"], as_index=False)[["QT_APTOS", "QT_COMPARECIMENTO"]].sum()


def largo_um(votos, det, adv):
    v = votos.copy()
    v["grupo"] = "outros"
    v.loc[v["NR_VOTAVEL"] == 13, "grupo"] = "pt"
    v.loc[v["NR_VOTAVEL"] == adv, "grupo"] = "adv"
    v.loc[v["NR_VOTAVEL"] == 95, "grupo"] = "branco"
    v.loc[v["NR_VOTAVEL"].isin([96, 97]), "grupo"] = "nulo"
    g = v.groupby(["SG_UF", "CD_MUNICIPIO", "grupo"])["QT_VOTOS"].sum().unstack("grupo", fill_value=0)
    g = g.join(det.drop(columns="NR_TURNO").set_index(["SG_UF", "CD_MUNICIPIO"]))
    return g.add_suffix("_1")


if __name__ == "__main__":
    main()
