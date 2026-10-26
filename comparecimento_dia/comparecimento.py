"""Comparecimento seção a seção, 1º × 2º turno de 2026 (sem o exterior). Gera c1-histograma.png, c2-estados.png e
comparecimento.json em DADOS/derivados/comparecimento_dia/.

1º turno: boletins de urna (dados abertos: QT_APTOS e QT_COMPARECIMENTO). 2º turno: votos contados nos logs das urnas, com o
log da urna original nas seções com urna substituída.
Variação = (votos no 2º − comparecimento no 1º) / aptos do 1º, em pontos percentuais. O log não traz os aptos da seção; os aptos
mudam pouco entre os turnos (voto em trânsito; textos.py calcula a diferença no país pelos arquivos de resultado do TSE: −149).

Entradas, em DADOS/derivados/biometria/ (pasta biometria/ deste repositório):
- bio_1t_secoes.csv (bio_1t.py) e bio_2t_secoes_v2.csv (bio_nested.py): aptos e comparecimento do 1º turno, votos do 2º;
- cobertura.json (reconcile.py): votos oficiais do 2º turno × votos contados nos logs, citados no rodapé
  (nesta apuração, faltam 508 dos 127.854.631).
E nomes.json (nomes.py), nesta pasta de saída, para os nomes dos municípios.
"""
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
sys.path.insert(0, str(HERE.parent / "abstencao"))
import caminhos  # noqa: E402
import charts_v2 as cv  # noqa: E402
import matplotlib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = caminhos.saida("comparecimento_dia")
BIO = caminhos.saida("biometria")
COB = json.load(open(BIO / "cobertura.json", encoding="utf-8"))  # {"oficial", "logs", "falta", ...}
cv.KICKER = "Eleições 2026 · comparecimento no 1º e no 2º turno"
cv.FONTE = ("Fonte: TSE. 1º turno: boletins de urna (dados abertos). 2º turno: logs das urnas, contando os votos de cada seção (inclui o "
            f"log da urna original onde houve troca; faltam {cv.n(COB['falta'])} dos {cv.n(COB['oficial'])} votos oficiais). Variação "
            "sobre os eleitores aptos do 1º turno. Sem o exterior.")
cv.MUTED = cv.INK2
NAME = json.load(open(OUT / "nomes.json", encoding="utf-8"))
LIGHT = "#9ec5f4"  # barras do lado da queda: mesmo azul, mais claro


def load():
    s1 = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]): r for r in csv.DictReader(open(BIO / "bio_1t_secoes.csv", encoding="utf-8"))
          if r["uf"] != "ZZ"}
    s2 = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]): int(r["votos"])
          for r in csv.DictReader(open(BIO / "bio_2t_secoes_v2.csv", encoding="utf-8")) if r["uf"] != "ZZ"}
    rows = []
    for k, r in s1.items():
        ap = int(r["aptos"])
        if k in s2 and ap:
            c1, c2 = int(r["comparecimento"]), s2[k]
            rows.append({"k": k, "aptos": ap, "c1": c1, "c2": c2, "d": 100 * (c2 - c1) / ap})
    return rows, len(s1) - len(rows)


def titulo(nome):
    """'CRUZEIRO DO SUL' -> 'Cruzeiro do Sul'."""
    return " ".join(w if w in ("do", "da", "de", "dos", "das", "e") else w.capitalize() for w in nome.lower().split())


def stats(rows):
    d = [r["d"] for r in rows]
    q1, med, q3 = st.quantiles(d, n=4, method="inclusive")
    by_uf, by_mun = defaultdict(list), defaultdict(list)
    for r in rows:
        by_uf[r["k"][0]].append(r["d"])
        by_mun[(r["k"][0], r["k"][1])].append(r["d"])
    ufs = {}
    for u, v in by_uf.items():
        a, m, b = st.quantiles(v, n=4, method="inclusive")
        vig = st.quantiles(v, n=20, method="inclusive")
        ufs[u] = {"n": len(v), "q1": a, "med": m, "q3": b, "p5": vig[0], "p95": vig[-1], "subiu": sum(x > 0 for x in v) / len(v),
                  "queda20": sum(x < -20 for x in v), "alta20": sum(x > 20 for x in v)}
    quedas = sorted(((sum(x < -20 for x in v), mk, len(v), st.median(v)) for mk, v in by_mun.items()), reverse=True)
    altas = sorted(((sum(x > 15 for x in v), mk, len(v), st.median(v)) for mk, v in by_mun.items()), reverse=True)
    nome = lambda u, c: f"{titulo(NAME.get(f'{u}-{c}', c))} ({u})"
    return {"n": len(rows), "subiu": sum(x > 0 for x in d), "caiu": sum(x < 0 for x in d), "igual": sum(x == 0 for x in d),
            "q1": q1, "med": med, "q3": q3, "abs20": sum(abs(x) > 20 for x in d), "abs10": sum(abs(x) > 10 for x in d),
            "queda20": sum(x < -20 for x in d), "alta20": sum(x > 20 for x in d), "faixa_m5_10": sum(-5 <= x <= 10 for x in d),
            "c1": sum(r["c1"] for r in rows), "c2": sum(r["c2"] for r in rows), "aptos": sum(r["aptos"] for r in rows), "ufs": ufs,
            "mun_quedas": [(nome(u, c), q, n, m) for q, (u, c), n, m in quedas[:12]],
            "mun_altas": [(nome(u, c), q, n, m) for q, (u, c), n, m in altas[:8]]}


def histograma(rows, S):
    fig = cv.figure(12, 11.2)
    pct = lambda a, b: cv.br(100 * a / b, 0, False) + "%"
    top = cv.frame(fig, "Comparecimento seção por seção: do 1º para o 2º turno",
                   f"Quantas das {cv.n(S['n'])} seções eleitorais tiveram cada variação no comparecimento (barras de 1 ponto percentual). "
                   "À direita do zero, mais eleitores votaram no 2º turno do que no 1º; em cinza, as seções sem nenhuma variação.",
                   [(pct(S["subiu"], S["n"]), "das seções tiveram mais eleitores votando no 2º turno", None),
                    (f"{cv.br(S['med'], 1)} p.p.", f"variação da seção típica (mediana); metade ficou entre {cv.br(S['q1'], 1)} e {cv.br(S['q3'], 1)}", None),
                    (cv.n(S["abs20"]), f"seções ({cv.br(100 * S['abs20'] / S['n'], 2, False)}%) variaram mais de 20 pontos, para cima ou para baixo", None)])
    ax = cv.axes_below(fig, top, left=1.25, right=0.55, bottom=2.0)
    lo, hi, w = -20, 20, 1
    edges = [lo + i * w for i in range(int((hi - lo) / w) + 1)]
    vals = [min(max(r["d"], lo + 1e-9), hi - 1e-9) for r in rows]
    zero = sum(1 for r in rows if r["d"] == 0)
    counts, _, patches = ax.hist(vals, bins=edges, color=cv.C26, edgecolor=cv.SURFACE, linewidth=1.6, zorder=2)
    for p, left in zip(patches, edges):
        if left < 0:
            p.set_facecolor(LIGHT)
    # seções sem nenhuma variação: parte de baixo da barra [0, 1), em cinza, separada das que subiram
    ax.bar(0.5, zero, width=1, color="#cfcdc7", edgecolor=cv.SURFACE, linewidth=1.6, zorder=2.5)
    ax.axvline(0, color=cv.INK2, linewidth=1, zorder=3)
    ymax = max(counts) * 1.22  # folga em cima para o rótulo da mediana não cobrir as barras
    ax.set_ylim(0, ymax)
    ax.axvline(S["med"], color=cv.INK, linewidth=1.3, linestyle=(0, (4, 3)), zorder=4)
    ax.text(S["med"] + 0.35, ymax * 0.99, f"mediana\n{cv.br(S['med'], 2)}", ha="left", va="top", fontsize=11, color=cv.INK2,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=cv.SURFACE, edgecolor="none"), zorder=5)
    ax.annotate(f"{cv.n(zero)} seções\nsem variação", xy=(0.5, zero * 0.5), xytext=(-6.5, ymax * 0.62), ha="center", va="center", fontsize=10.5,
                color=cv.INK2, arrowprops=dict(arrowstyle="-", color=cv.INK2, linewidth=0.8), zorder=6)
    for x, txt in ((lo + 0.5, f"{cv.n(S['queda20'])} seções\nabaixo de −20"), (hi - 0.5, f"{cv.n(S['alta20'])} seções\nacima de +20")):
        ax.annotate(txt, xy=(x, 0), xytext=(x, ymax * 0.22), ha="center", va="bottom", fontsize=10.5, color=cv.INK2,
                    arrowprops=dict(arrowstyle="-", color=cv.INK2, linewidth=0.8), zorder=6)
    ax.text(-0.4, -ymax * 0.1, "← menos eleitores votaram no 2º turno", ha="right", va="top", fontsize=11, color=cv.INK2, clip_on=False)
    ax.text(0.4, -ymax * 0.1, "mais eleitores votaram no 2º turno →", ha="left", va="top", fontsize=11, color=cv.INK2, clip_on=False)
    cv.xstyle(ax, "pontos percentuais (as seções fora da faixa de −20 a +20 estão nas barras das pontas)")
    ax.xaxis.labelpad = 36
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=cv.GRID, linewidth=0.9)
    ax.set_ylabel("número de seções", fontsize=12)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: cv.n(int(v))))
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: cv.br(v, 0) if v else "0"))
    fig.savefig(OUT / "c1-histograma.png", facecolor=cv.SURFACE)
    plt.close(fig)


def estados(S):
    U = S["ufs"]
    order = sorted(U, key=lambda u: U[u]["med"])
    negativos = [u for u in order if U[u]["med"] < 0]
    norte3 = sum(U[u]["queda20"] for u in ("AP", "AC", "RR"))
    fig = cv.figure(12, 16.5)
    top = cv.frame(fig, "A variação do comparecimento por seção, dentro de cada UF",
                   "Para cada UF (26 estados e o DF): a caixa marca a metade central das seções, o traço é a mediana e a linha vai de 5% a 95% das seções. "
                   "À direita, a mediana e quantas seções tiveram queda de mais de 20 pontos.",
                   [(f"{sum(U[u]['med'] > 0 for u in U)} de {len(U)}", "UFs com alta na seção típica (mediana)", None),
                    (f"{len(negativos)} UFs", "com queda na seção típica: " + (" e ".join([", ".join(negativos[:-1]), negativos[-1]])
                                                                            if len(negativos) > 1 else negativos[0]), None),
                    (cv.n(S["queda20"]), f"seções com queda de mais de 20 pontos; {cv.br(100 * norte3 / S['queda20'], 0, False)}% delas no AP, no AC e em RR", None)])
    ax = cv.axes_below(fig, top, left=0.95, right=2.2)
    lo, hi = -25, 15
    for i, u in enumerate(order):
        d = U[u]
        ax.plot([max(d["p5"], lo), min(d["p95"], hi)], [i, i], color=cv.C26, linewidth=1.6, zorder=2)
        ax.add_patch(FancyBboxPatch((d["q1"], i - 0.3), max(d["q3"] - d["q1"], 0.05), 0.6, boxstyle="round,pad=0,rounding_size=0.1",
                                    facecolor="#cde2fb", edgecolor=cv.C26, linewidth=1.4, zorder=3))
        ax.plot([d["med"], d["med"]], [i - 0.3, i + 0.3], color=cv.INK, linewidth=2.6, zorder=4)
        ax.text(1.03, i, cv.br(d["med"], 1), transform=ax.get_yaxis_transform(), va="center", fontsize=12.5, fontweight="bold")
        ax.text(1.17, i, cv.n(d["queda20"]) if d["queda20"] else "–", transform=ax.get_yaxis_transform(), va="center", fontsize=12, color=cv.INK2)
    ax.text(1.03, len(order) - 0.3, "mediana", transform=ax.get_yaxis_transform(), fontsize=10.5, color=cv.INK2, fontweight="bold", va="bottom")
    ax.text(1.17, len(order) - 0.3, "quedas >20", transform=ax.get_yaxis_transform(), fontsize=10.5, color=cv.INK2, va="bottom")
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.6, len(order) + 0.5)
    ax.set_xlim(lo, hi)
    ax.axvline(0, color=cv.INK2, linewidth=1, zorder=1)
    cv.xstyle(ax, "pontos percentuais  ·  à direita do zero, mais eleitores votaram no 2º turno")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: cv.br(v, 0) if v else "0"))
    fig.savefig(OUT / "c2-estados.png", facecolor=cv.SURFACE)
    plt.close(fig)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows, faltam = load()
    S = stats(rows)
    histograma(rows, S)
    estados(S)
    json.dump(S, open(OUT / "comparecimento.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in S.items() if k not in ("ufs", "mun_quedas", "mun_altas")}, "sem par:", faltam)
    print(S["mun_quedas"][:10])
    print(S["mun_altas"][:6])


if __name__ == "__main__":
    main()
