"""Versão final: abstenção do 1º para o 2º turno (2026, com 2022 como referência). Imagens + resumo em texto.

Gera em DADOS/derivados/abstencao/final/: 0-capa.png, 1-estados.png, 2-municipios.png, 3-dentro-dos-estados.png,
4-municipios-2022x2026.png e resumo.md. Imagens e textos saem dos mesmos números (nada digitado à mão). Títulos descrevem o
que o gráfico mostra.
Entradas: DADOS/derivados/abstencao/abst_municipios.csv (build_data.py) e, para os totais com o exterior e o resultado
nacional, DADOS/tse/ab/*-ab.json, DADOS/tse/detalhe_votacao_munzona_2022.zip e DADOS/tse/br-c0001-e006258-u.json (baixar.py).
Cores: 2026 = azul #2a78d6, 2022 = laranja #eb6834, Centro-Sul = verde #1baf7a (só no gráfico 4, com rótulo).

Também é o módulo de estilo dos gráficos das outras análises (import charts_v2 as cv): cores, br/n/pontos/mi/lista, figure,
frame, axes_below e xstyle. Importar o módulo não lê dados nem cria pastas.
"""
import csv
import io
import json
import math
import random
import statistics as st
import sys
import textwrap
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
RAW = caminhos.TSE / "ab"
OUT = None  # pasta de saída (DADOS/derivados/abstencao/final), definida em main(): importar o módulo não cria pastas
RESULTADO_BR = caminhos.TSE / "br-c0001-e006258-u.json"  # resultado nacional oficial do 2º turno (Presidente)
UFS_RAW = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz".split()

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8d8b85", "#e6e4df"
TILE, BAND = "#f2f0eb", "#f3f1ec"
C26, C22, C_CS = "#2a78d6", "#eb6834", "#1baf7a"
C_NNE = "#6250d6"  # roxo: no gráfico por região o azul ficaria parecendo "2026"
NORTE = {"AC", "AP", "AM", "PA", "RO", "RR", "TO"}
NORDESTE = {"AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"}
KICKER = "Eleições 2026 · abstenção entre o 1º e o 2º turno"
FONTE = ("Fonte: TSE, resultados oficiais por município (2026: arquivos de resultado do 1º e do 2º turno; 2022: dados abertos). "
         "Abstenção = eleitores aptos que não votaram ÷ aptos. Sem o exterior, salvo indicação.")
# Segoe UI (Windows); onde não houver, DejaVu Sans (vem com o matplotlib) — as imagens mudam um pouco.
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 12, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "xtick.labelsize": 11.5, "ytick.labelsize": 12})


def br(x, digits=1, sign=True):
    if round(x, digits) == 0:
        x = 0.0
    s = (f"{x:+.{digits}f}" if x else f"{0:.{digits}f}") if sign else f"{x:.{digits}f}"
    return s.replace("-", "−").replace(".", ",")


def n(x):
    return f"{x:,}".replace(",", ".")


def pontos(x, digits=1):
    return f"{br(abs(x), digits, False)} {'ponto' if abs(round(x, digits)) < 2 else 'pontos'}"


def mi(x):
    return f"{x / 1e6:.2f}".replace(".", ",") + (" milhão" if x < 2e6 else " milhões")


def lista(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


SCALE = 0.82  # figuras em polegadas menores com a mesma largura em pixels: o texto fica ~22% maior em relação ao gráfico


def figure(w, h):
    return plt.figure(figsize=(w * SCALE, h * SCALE), dpi=150 / SCALE)


def dot(fig, x_in, y_in, r_in, color):
    """Marcador redondo em coordenadas de figura (polegadas a partir do topo esquerdo), sem virar elipse."""
    W, H = fig.get_figwidth(), fig.get_figheight()
    fig.add_artist(Ellipse((x_in / W, 1 - y_in / H), 2 * r_in / W, 2 * r_in / H, transform=fig.transFigure, color=color))


def wrap_label(label, chars):
    return [p for line in label.split("\n") for p in textwrap.wrap(line, chars)]


def corr(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


# ---------------------------------------------------------------- dados
def load():
    data = {2026: {}, 2022: {}}
    for r in csv.DictReader(open(caminhos.saida("abstencao") / "abst_municipios.csv", encoding="utf-8")):
        if r["uf"] != "ZZ":
            data[int(r["ano"])][(r["uf"], r["cd_municipio"])] = tuple(int(r[k]) for k in ("aptos_1t", "abst_1t", "aptos_2t", "abst_2t"))
    return data


def rate(items):
    a1, b1, a2, b2 = (sum(x[i] for x in items) for i in range(4))
    return 100 * b1 / a1, 100 * b2 / a2, 100 * b2 / a2 - 100 * b1 / a1


def totals_with_abroad(election):
    te = a = 0
    for uf in UFS_RAW:
        for it in json.loads((RAW / f"{uf}-e00{election}-ab.json").read_text(encoding="utf-8"))["abr"]:
            if it.get("tpabr") == "mun":
                te += int(it["e"]["te"]); a += int(it["e"]["a"])
    return te, a


def totals_2022_with_abroad():
    acc = {1: 0, 2: 0}
    # CSV lido de dentro do zip de dados abertos do TSE (latin-1).
    with zipfile.ZipFile(caminhos.TSE / "detalhe_votacao_munzona_2022.zip") as z, \
            io.TextIOWrapper(z.open("detalhe_votacao_munzona_2022_BRASIL.csv"), encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            if row["CD_CARGO"] == "1":
                acc[int(row["NR_TURNO"])] += int(row["QT_ABSTENCOES"])
    return acc


def compute():
    data = load()
    S = {"data": data}
    ufs = sorted({k[0] for k in data[2026]})
    S["ufs"] = ufs
    S["by_uf"] = {y: {u: rate([v for k, v in data[y].items() if k[0] == u]) for u in ufs} for y in data}
    S["nat"] = {y: rate(list(data[y].values())) for y in data}
    S["d26"] = {k: 100 * v[3] / v[2] - 100 * v[1] / v[0] for k, v in data[2026].items()}
    S["d22"] = {k: 100 * v[3] / v[2] - 100 * v[1] / v[0] for k, v in data[2022].items()}
    du = {u: S["by_uf"][2026][u][2] for u in ufs}
    aptos_uf = {u: sum(v[0] for k, v in data[2026].items() if k[0] == u) for u in ufs}
    S["grupo"] = [u for u in ufs if du[u] <= -1]
    S["grupo_share"] = 100 * sum(aptos_uf[u] for u in S["grupo"]) / sum(aptos_uf.values())
    S["grupo_rng"] = (max(du[u] for u in S["grupo"]), min(du[u] for u in S["grupo"]))
    S["queda"] = [u for u in ufs if du[u] < -0.1]
    S["estavel_alta"] = sorted(set(ufs) - set(S["queda"]))
    S["mais_que_2022"] = [u for u in ufs if du[u] < S["by_uf"][2022][u][2]]
    d26, d22 = S["d26"], S["d22"]
    S["mun_queda"] = sum(v < 0 for v in d26.values())
    S["med26"], S["med22"] = st.median(d26.values()), st.median(d22.values())
    S["q26"] = tuple(st.quantiles(d26.values(), n=4, method="inclusive")[i] for i in (0, 2))
    cs_vals = [v for k, v in d26.items() if k[0] not in NORTE | NORDESTE]
    S["cs_queda"] = 100 * sum(v < 0 for v in cs_vals) / len(cs_vals)
    S["quase_todos"] = [u for u in ufs if sum(k[0] == u for k in d26) > 1
                        and sum(v < 0 for k, v in d26.items() if k[0] == u) >= 0.95 * sum(k[0] == u for k in d26)]
    norte = [v for k, v in d26.items() if k[0] in NORTE]
    S["norte_alta"] = 100 * sum(v > 0 for v in norte) / len(norte)
    S["med_mais"] = sum(st.median([v for k, v in d26.items() if k[0] == u]) < st.median([v for k, v in d22.items() if k[0] == u]) for u in ufs)
    common = [k for k in d26 if k in d22]
    S["common"] = common
    nne = [k for k in common if k[0] in NORTE | NORDESTE]; cs = [k for k in common if k[0] not in NORTE | NORDESTE]
    S["r_nne"] = corr([d22[k] for k in nne], [d26[k] for k in nne])
    S["r_cs"] = corr([d22[k] for k in cs], [d26[k] for k in cs])
    S["abaixo"] = sum(d26[k] < d22[k] for k in common)
    # Votos: totais com o exterior (a vantagem final inclui o exterior).
    te1, a1 = totals_with_abroad(6257); te2, a2 = totals_with_abroad(6258)
    S["abst26"] = (a1, a2, a1 - a2, 100 * a1 / te1, 100 * a2 / te2)
    a22 = totals_2022_with_abroad()
    S["abst22"] = (a22[1], a22[2], a22[1] - a22[2])
    # Votos de cada candidato no país (2º turno), do arquivo de resultado do TSE: carg -> agr -> par -> cand (nmu = nome na
    # urna, vap = votos apurados). Exige o arquivo oficial (f = "o") com todas as seções totalizadas (snt = 0, st = ts).
    res = json.loads(RESULTADO_BR.read_text(encoding="utf-8-sig"))
    secoes = res["s"]
    assert res["f"] == "o" and int(secoes["snt"]) == 0 and int(secoes["st"]) == int(secoes["ts"])
    cargo = [c for c in res["carg"] if int(c["cd"]) == 1][0]
    cands = sorted(({"name": c.get("nmu") or c.get("nm"), "votes": int(c["vap"])}
                    for agr in cargo["agr"] for par in agr["par"] for c in par["cand"]), key=lambda c: -c["votes"])
    S["cand"] = [(c["name"], c["votes"]) for c in cands]
    S["margem"] = cands[0]["votes"] - cands[1]["votes"]
    return S


# ---------------------------------------------------------------- moldura comum
def frame(fig, title, subtitle, tiles, title_chars=None, sub_chars=None):
    """Cabeçalho (rótulo, título, subtítulo, faixa de números-chave) e rodapé. Devolve o topo livre para o gráfico (fração)."""
    W, H = fig.get_figwidth(), fig.get_figheight()
    x0, usable = 0.55 / W, W - 1.1
    y = 0.5
    fig.text(x0, 1 - y / H, KICKER.upper(), fontsize=10.5, fontweight="bold", color=INK2, va="top")
    y += 0.32
    tl = textwrap.wrap(title, title_chars or int(usable * 5.9))
    fig.text(x0, 1 - y / H, "\n".join(tl), fontsize=23, fontweight="bold", va="top", linespacing=1.12)
    y += 0.4 * len(tl) + 0.16
    if subtitle:
        sl = [p for line in subtitle.split("\n") for p in textwrap.wrap(line, sub_chars or int(usable * 10.6))]
        fig.text(x0, 1 - y / H, "\n".join(sl), fontsize=13, color=INK2, va="top", linespacing=1.5)
        y += 0.29 * len(sl) + 0.28
    if tiles:
        gap = 0.22
        tw = (usable - gap * (len(tiles) - 1)) / len(tiles)
        # Altura pela legenda mais longa: nenhum texto de bloco é cortado.
        th = 0.74 + 0.2 * max(len(wrap_label(label, int(tw * 10.8))) for _, label, _ in tiles)
        for i, (value, label, mark) in enumerate(tiles):
            tx = 0.55 + i * (tw + gap)
            fig.add_artist(FancyBboxPatch((tx / W, 1 - (y + th) / H), tw / W, th / H, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, facecolor=TILE, edgecolor="none"))
            vx = tx + 0.2
            if mark:
                dot(fig, tx + 0.29, y + 0.36, 0.08, mark)
                vx = tx + 0.47
            fig.text(vx / W, 1 - (y + 0.15) / H, value, fontsize=24, fontweight="bold", va="top")
            ll = wrap_label(label, int(tw * 10.8))
            fig.text((tx + 0.2) / W, 1 - (y + 0.68) / H, "\n".join(ll), fontsize=10.8, color=INK2, va="top", linespacing=1.3)
        y += th + 0.32
    fl = textwrap.wrap(FONTE, int(usable * 13.5))
    fig.text(x0, 0.32 / H, "\n".join(fl), fontsize=9.5, color=MUTED, va="bottom", linespacing=1.35)
    return 1 - y / H


def axes_below(fig, top, left=1.05, right=0.55, bottom=1.55):
    W, H = fig.get_figwidth(), fig.get_figheight()
    return fig.add_axes([left / W, bottom / H, 1 - (left + right) / W, top - bottom / H])


def xstyle(ax, label):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)
    ax.set_xlabel(label, color=INK2, fontsize=12, labelpad=10)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v, 0) if v else "0"))


# ---------------------------------------------------------------- 0) capa
def capa(S):
    fig = plt.figure(figsize=(12, 6.75), dpi=150)
    a1, a2, dif, p1, p2 = S["abst26"]
    nat = S["nat"]
    frame(fig, "Em 2026, a abstenção caiu mais entre os turnos do que em 2022", None, [])
    W, H = 12, 6.75
    rows = [
        (f"{br(nat[2026][2], 2)} ponto", f"variação da abstenção no país do 1º para o 2º turno de 2026 ({br(nat[2026][0], 2, False)}% → {br(nat[2026][1], 2, False)}%)", C26),
        (f"{br(nat[2022][2], 2)} ponto", f"a mesma variação em 2022 ({br(nat[2022][0], 2, False)}% → {br(nat[2022][1], 2, False)}%)", C22),
        (mi(dif), f"de eleitores a mais votaram no 2º turno de 2026, contando o exterior (em 2022, {mi(S['abst22'][2])})", None),
        (mi(S["margem"]), "foi a vantagem final de Lula sobre Flávio Bolsonaro: maior que o saldo de eleitores a mais", None),
    ]
    tw, th, gx, gy = (12 - 1.1 - 0.3) / 2, 1.55, 0.3, 0.26
    y0 = 1.42
    for i, (value, label, mark) in enumerate(rows):
        cx, cy = 0.55 + (i % 2) * (tw + gx), y0 + (i // 2) * (th + gy)
        fig.add_artist(FancyBboxPatch((cx / W, 1 - (cy + th) / H), tw / W, th / H, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, facecolor=TILE, edgecolor="none"))
        vx = cx + 0.28
        if mark:
            dot(fig, cx + 0.4, cy + 0.47, 0.1, mark)
            vx = cx + 0.62
        fig.text(vx / W, 1 - (cy + 0.2) / H, value, fontsize=34, fontweight="bold", va="top")
        fig.text((cx + 0.28) / W, 1 - (cy + 0.95) / H, "\n".join(textwrap.wrap(label, int(tw * 9.2))), fontsize=12.5, color=INK2, va="top", linespacing=1.3)
    # Ressalva: é saldo líquido, não um grupo identificado de eleitores.
    ny = y0 + 2 * th + gy + 0.24
    fig.text(0.55 / W, 1 - ny / H, "A queda da abstenção é um saldo entre os dois turnos: não dá para saber quem são os eleitores a mais nem em quem votaram.",
             fontsize=12, color=INK2, va="top", style="italic")
    fig.savefig(OUT / "0-capa.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- 1) estados
def estados(S):
    by_uf, nat, ufs = S["by_uf"], S["nat"], S["ufs"]
    order = sorted(ufs, key=lambda u: by_uf[2026][u][2], reverse=True)
    fig = figure(12, 16)
    resto = sorted(set(S["estavel_alta"]) - NORTE)
    outras = [u for u in ufs if u not in S["grupo"] and u not in S["estavel_alta"]]
    top = frame(fig, "Como a abstenção mudou do 1º para o 2º turno, estado por estado",
                f"Variação da abstenção entre os turnos, em pontos percentuais (p.p.): em azul, 2026; em laranja, 2022. "
                f"A abstenção caiu em {len(S['queda'])} UFs: em {len(S['grupo'])} delas ({br(S['grupo_share'], 0, False)}% do eleitorado), de "
                f"{br(abs(S['grupo_rng'][0]), 1, False)} a {br(abs(S['grupo_rng'][1]), 1, False)} pontos"
                + "".join(f"; em {u}, {br(abs(by_uf[2026][u][2]), 1, False)}" for u in outras) + ". "
                f"Nos estados do Norte (faixa cinza) e em {lista(resto)}, ficou estável ou subiu, como em 2022.",
                [(br(nat[2026][2], 2), f"p.p. em 2026\n{br(nat[2026][0], 2, False)}% → {br(nat[2026][1], 2, False)}%", C26),
                 (br(nat[2022][2], 2), f"p.p. em 2022\n{br(nat[2022][0], 2, False)}% → {br(nat[2022][1], 2, False)}%", C22),
                 (str(len(S["queda"])), "UFs com queda da abstenção em 2026", None),
                 (str(len(S["estavel_alta"])), f"com estabilidade ou alta: os {len(NORTE)} do Norte, {lista(resto)}", None)])
    ax = axes_below(fig, top, left=0.95, right=2.05)
    for i, u in enumerate(order):
        if u in NORTE:
            ax.add_patch(Rectangle((-100, i - 0.5), 200, 1, facecolor=BAND, edgecolor="none", zorder=0))
        a, b = by_uf[2022][u][2], by_uf[2026][u][2]
        ax.plot([a, b], [i, i], color="#d9d6cf", linewidth=2.4, zorder=1, solid_capstyle="round")
        ax.scatter([a], [i], s=85, color=C22, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter([b], [i], s=110, color=C26, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.text(1.03, i, br(b), transform=ax.get_yaxis_transform(), va="center", fontsize=12.5, fontweight="bold")
        ax.text(1.115, i, br(a), transform=ax.get_yaxis_transform(), va="center", fontsize=12, color=INK2)
    ax.text(1.03, len(order) - 0.35, "2026", transform=ax.get_yaxis_transform(), fontsize=11, fontweight="bold", color=INK2, va="bottom")
    ax.text(1.115, len(order) - 0.35, "2022", transform=ax.get_yaxis_transform(), fontsize=11, color=INK2, va="bottom")
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.axvline(0, color=INK2, linewidth=1, zorder=0.5)
    for y, color in ((2026, C26), (2022, C22)):
        ax.axvline(nat[y][2], color=color, linewidth=1.3, linestyle=(0, (4, 3)), zorder=0.5)
        ax.text(nat[y][2], len(order) - 0.35, f"Brasil {y}\n{br(nat[y][2], 2)}", ha="center", va="bottom", fontsize=10.5, color=INK2,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=SURFACE, edgecolor="none"))
    lo = min(min(by_uf[y][u][2] for u in ufs) for y in by_uf); hi = max(max(by_uf[y][u][2] for u in ufs) for y in by_uf)
    ax.set_xlim(lo - 0.6, hi + 0.6); ax.set_ylim(-0.6, len(order) + 0.9)
    xstyle(ax, "pontos percentuais  ·  à esquerda do zero a abstenção caiu; à direita, subiu")
    ax.scatter([], [], s=110, color=C26, label="2026"); ax.scatter([], [], s=85, color=C22, label="2022")
    ax.add_patch(Rectangle((0, 0), 0, 0, facecolor=BAND, edgecolor=GRID, label="estados do Norte"))
    ax.legend(loc="lower left", frameon=False, fontsize=12, borderaxespad=0.2)
    fig.savefig(OUT / "1-estados.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- 2) municípios (histograma)
def municipios(S):
    d26, d22 = S["d26"], S["d22"]
    fig = figure(12, 11.8)
    top = frame(fig, f"A variação da abstenção nos {n(len(d26))} municípios",
                "Quantos municípios tiveram cada variação de abstenção entre os turnos (barras de 0,5 ponto). "
                "Em 2026 (azul) a distribuição está à esquerda da de 2022 (linha laranja): mais municípios com queda, e quedas maiores.",
                [(f"{br(100 * S['mun_queda'] / len(d26), 0, False)}%", f"dos municípios tiveram queda da abstenção em 2026", None),
                 (f"{br(S['med26'], 2)} p.p.", "variação do município típico (mediana) em 2026", C26),
                 (f"{br(S['med22'], 2)} p.p.", "variação do município típico (mediana) em 2022", C22)])
    ax = axes_below(fig, top, left=1.05, right=0.55, bottom=1.9)
    lo, hi, w = -8, 14, 0.5
    edges = [lo + i * w for i in range(int((hi - lo) / w) + 1)]
    clip = lambda vs: [min(max(x, lo + 1e-9), hi - 1e-9) for x in vs]
    ax.hist(clip(d26.values()), bins=edges, color=C26, edgecolor=SURFACE, linewidth=1.6, zorder=2, label="2026")
    ax.hist(clip(d22.values()), bins=edges, histtype="step", color=C22, linewidth=2.2, zorder=3, label="2022")
    ax.axvline(0, color=INK2, linewidth=1, zorder=1)
    ymax = ax.get_ylim()[1]
    for med, color, label, ha in ((S["med26"], C26, "mediana 2026", "right"), (S["med22"], C22, "mediana 2022", "left")):
        ax.axvline(med, color=color, linewidth=1.3, linestyle=(0, (4, 3)), zorder=4)
        ax.text(med + (-0.18 if ha == "right" else 0.18), ymax * 0.96, f"{label}\n{br(med, 2)}", ha=ha, va="top", fontsize=11, color=INK2,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=SURFACE, edgecolor="none"), zorder=5)
    ax.text(-0.25, -ymax * 0.12, "← queda", ha="right", va="top", fontsize=11, color=INK2, clip_on=False)
    ax.text(0.25, -ymax * 0.12, "alta →", ha="left", va="top", fontsize=11, color=INK2, clip_on=False)
    xstyle(ax, "pontos percentuais (os poucos municípios fora da faixa estão somados nas barras das pontas)")
    ax.xaxis.labelpad = 38
    ax.grid(axis="x", visible=False); ax.grid(axis="y", color=GRID, linewidth=0.9)
    ax.set_ylabel("número de municípios", fontsize=12)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: n(int(v))))
    ax.legend(loc="upper right", frameon=False, fontsize=12)
    fig.savefig(OUT / "2-municipios.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- 3) dentro de cada estado
def dentro(S):
    d26, d22, ufs = S["d26"], S["d22"], S["ufs"]
    order = sorted(ufs, key=lambda u: st.median([v for k, v in d26.items() if k[0] == u]), reverse=True)
    fig = figure(12, 17)
    top = frame(fig, "A variação da abstenção dentro de cada estado",
                "Cada ponto é um município; a caixa marca a metade central deles e o traço, a mediana. "
                "O losango laranja é a mediana do estado em 2022. Estados do Norte na faixa cinza.",
                [(f"{len(S['quase_todos'])} estados", f"com queda em 95% ou mais dos municípios: {lista(S['quase_todos'])}", None),
                 (f"{br(S['norte_alta'], 0, False)}%", "dos municípios do Norte tiveram alta da abstenção", None),
                 (f"{S['med_mais']} de {len(ufs)}", "UFs com variação mediana menor que em 2022 (queda maior ou alta menor)", None)])
    ax = axes_below(fig, top, left=0.95, right=2.35)
    lo, hi = -8, 20
    rnd = random.Random(26)
    for i, u in enumerate(order):
        if u in NORTE:
            ax.add_patch(Rectangle((-100, i - 0.5), 200, 1, facecolor=BAND, edgecolor="none", zorder=0))
        vals = sorted(v for k, v in d26.items() if k[0] == u)
        q1, q2, q3 = st.quantiles(vals, n=4, method="inclusive") if len(vals) > 1 else (vals[0],) * 3
        ax.scatter([min(max(v, lo), hi) for v in vals], [i + rnd.uniform(-0.27, 0.27) for _ in vals], s=7, color=C26, alpha=0.38, linewidth=0, zorder=2)
        ax.add_patch(FancyBboxPatch((q1, i - 0.3), max(q3 - q1, 0.05), 0.6, boxstyle="round,pad=0,rounding_size=0.1",
                                    facecolor="none", edgecolor=INK, linewidth=1.4, zorder=3))
        ax.plot([q2, q2], [i - 0.3, i + 0.3], color=INK, linewidth=2.4, zorder=4)
        ax.scatter([st.median([v for k, v in d22.items() if k[0] == u])], [i], marker="D", s=52, color=C22, edgecolor=SURFACE, linewidth=1.5, zorder=5)
        ax.text(1.03, i, br(q2), transform=ax.get_yaxis_transform(), va="center", fontsize=12.5, fontweight="bold")
        ax.text(1.14, i, f"{br(q1)} a {br(q3)}" if len(vals) > 1 else "um só município", transform=ax.get_yaxis_transform(), va="center", fontsize=11, color=INK2)
    ax.text(1.03, len(order) - 0.3, "mediana", transform=ax.get_yaxis_transform(), fontsize=10.5, color=INK2, fontweight="bold", va="bottom")
    ax.text(1.14, len(order) - 0.3, "metade central", transform=ax.get_yaxis_transform(), fontsize=10.5, color=INK2, va="bottom")
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.6, len(order) + 0.5); ax.set_xlim(lo - 0.4, hi + 0.4)
    ax.axvline(0, color=INK2, linewidth=1, zorder=1)
    xstyle(ax, "pontos percentuais  ·  à esquerda do zero a abstenção caiu; à direita, subiu")
    ax.scatter([], [], s=40, color=C26, label="um município (2026)")
    ax.plot([], [], color=INK, linewidth=2.4, label="mediana e metade central (2026)")
    ax.scatter([], [], marker="D", s=52, color=C22, label="mediana do estado em 2022")
    ax.add_patch(Rectangle((0, 0), 0, 0, facecolor=BAND, edgecolor=GRID, label="estados do Norte"))
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=11)
    fig.savefig(OUT / "3-dentro-dos-estados.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- 4) 2022 × 2026 por município
def comparacao(S):
    d26, d22, common, data = S["d26"], S["d22"], S["common"], S["data"]
    fig = figure(12, 15.5)
    top = frame(fig, "Cada município em 2022 e em 2026",
                "Cada ponto é um município (maior = mais eleitores): na horizontal, a variação da abstenção entre os turnos em 2022; "
                "na vertical, em 2026. Abaixo da linha tracejada, a variação de 2026 foi menor que a de 2022 (queda maior ou alta menor). "
                "Municípios fora da faixa do gráfico aparecem na borda.",
                [(br(S["r_nne"], 2, False), "correlação entre 2022 e 2026 no Norte e Nordeste (1 = mesma ordem; 0 = nenhuma relação)", C_NNE),
                 (br(S["r_cs"], 2, False), "a mesma correlação no Centro-Sul (Sul, Sudeste e Centro-Oeste)", C_CS),
                 (f"{br(100 * S['abaixo'] / len(common), 0, False)}%", "dos municípios com variação menor que em 2022", None)])
    W, H = fig.get_figwidth(), fig.get_figheight()
    side = min(W - 1.6, top * H - 1.75)
    ax = fig.add_axes([(W - side) / 2 / W + 0.2 / W, 1.55 / H, side / W, side / H])
    lo, hi = -8, 14
    for flag, color, label, z in ((True, C_NNE, "Norte e Nordeste", 2), (False, C_CS, "Centro-Sul", 3)):
        ks = [k for k in common if (k[0] in NORTE | NORDESTE) == flag]
        ax.scatter([min(max(d22[k], lo), hi) for k in ks], [min(max(d26[k], lo), hi) for k in ks],
                   s=[max(5, math.sqrt(data[2026][k][0]) / 5.5) for k in ks], color=color, alpha=0.35, linewidth=0, zorder=z, label=label)
    ax.plot([lo, hi], [lo, hi], color=INK2, linewidth=1.3, linestyle=(0, (4, 3)), zorder=4)
    ax.text(hi - 0.5, hi - 1.3, "mesma variação de 2022", ha="right", fontsize=11, color=INK2, rotation=45, rotation_mode="anchor")
    ax.axhline(0, color=GRID, linewidth=1, zorder=1); ax.axvline(0, color=GRID, linewidth=1, zorder=1)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.spines[["top", "right"]].set_visible(False)
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(matplotlib.ticker.MultipleLocator(4))
        axis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v, 0) if v else "0"))
    ax.set_xlabel("variação em 2022 (pontos percentuais)", fontsize=12, labelpad=8)
    ax.set_ylabel("variação em 2026 (pontos percentuais)", fontsize=12, labelpad=8)
    ax.grid(color=GRID, linewidth=0.7); ax.set_axisbelow(True)
    ax.text(-1.0, -6.7, f"Centro-Sul: {br(S['cs_queda'], 0, False)}% dos\nmunicípios tiveram queda", fontsize=11.5, ha="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor=SURFACE, edgecolor=C_CS, linewidth=1.4), zorder=6)
    ax.text(8.6, 0.6, "Norte e Nordeste: onde mais\nsubiu em 2022, voltou a subir mais", fontsize=11.5, ha="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor=SURFACE, edgecolor=C_NNE, linewidth=1.4), zorder=6)
    leg = ax.legend(loc="upper left", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=11.5)
    for handle in leg.legend_handles:
        handle.set_alpha(1); handle.set_sizes([60])
    fig.savefig(OUT / "4-municipios-2022x2026.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- textos
def textos(S):
    nat, by_uf = S["nat"], S["by_uf"]
    a1, a2, dif, p1, p2 = S["abst26"]
    (n1, v1), (n2, v2) = S["cand"][:2]
    resto = sorted(set(S["estavel_alta"]) - NORTE)
    top_queda = sorted(S["ufs"], key=lambda u: by_uf[2026][u][2])[:3]
    top_alta = sorted(S["ufs"], key=lambda u: -by_uf[2026][u][2])[:3]
    f = lambda u: f"{u} {br(by_uf[2026][u][2])}"
    # Nomes com acento (a API do TSE devolve em maiúsculas sem acento).
    nome = {"LULA": "Lula", "FLAVIO BOLSONARO": "Flávio Bolsonaro"}
    n1, n2 = nome.get(n1, n1.title()), nome.get(n2, n2.title())
    alta22 =[u for u in S["estavel_alta"] if by_uf[2022][u][2] > 0]
    outras = [u for u in S["ufs"] if u not in S["grupo"] and u not in S["estavel_alta"]]  # nem no grupo de queda forte nem entre as que subiram (AL)
    partes = [
        ("0-capa.png",
         f"A abstenção caiu de {br(nat[2026][0], 2, False)}% para {br(nat[2026][1], 2, False)}% entre o 1º e o 2º turno de 2026 (sem o exterior): "
         f"{br(abs(nat[2026][2]), 2, False)} ponto, contra {br(abs(nat[2022][2]), 2, False)} em 2022. Contando o exterior, foram {mi(dif)} "
         f"de eleitores a mais no 2º turno. É menos que a vantagem final de {n1} sobre {n2} ({mi(v1 - v2)})."),
        ("1-estados.png",
         f"Por estado: em {len(S['grupo'])}, que reúnem {br(S['grupo_share'], 0, False)}% do eleitorado, a abstenção caiu entre "
         f"{br(abs(S['grupo_rng'][0]), 1, False)} e {br(abs(S['grupo_rng'][1]), 1, False)} pontos ({'; '.join(f(u) for u in top_queda)})"
         + "".join(f"; em {u}, {br(abs(by_uf[2026][u][2]), 1, False)}" for u in outras) + ". "
         f"Nos {len(NORTE)} do Norte e em {lista(resto)}, ficou estável ou subiu ({'; '.join(f(u) for u in top_alta)})"
         + (f"; esses {len(alta22)} também tiveram alta em 2022." if len(alta22) == len(S["estavel_alta"]) else f"; {len(alta22)} deles também tiveram alta em 2022.")),
        ("2-municipios.png",
         f"Nos {n(len(S['d26']))} municípios, a abstenção caiu em {br(100 * S['mun_queda'] / len(S['d26']), 0, False)}% deles. "
         f"No município típico (mediana), a variação foi de {br(S['med26'], 2)} ponto, contra {br(S['med22'], 2)} em 2022. "
         f"Metade dos municípios ficou entre {br(S['q26'][0])} e {br(S['q26'][1])} pontos."),
        ("3-dentro-dos-estados.png",
         f"Dentro dos estados: em {lista(S['quase_todos'])}, a abstenção caiu em 95% ou mais dos municípios, com a maioria deles perto da mediana do estado. "
         f"No Norte, subiu em {br(S['norte_alta'], 0, False)}% dos municípios, com diferenças grandes de um para outro."),
        ("4-municipios-2022x2026.png",
         f"Município a município, 2026 lembra 2022: no Norte e no Nordeste, onde a abstenção mais subiu em 2022, tendeu a subir mais de novo "
         f"(correlação de {br(S['r_nne'], 2, False)}). No Centro-Sul, a ligação é mais fraca ({br(S['r_cs'], 2, False)}) e "
         f"{br(S['cs_queda'], 0, False)}% tiveram queda. No país, {br(100 * S['abaixo'] / len(S['common']), 0, False)}% tiveram variação menor que em 2022."),
        (None,
         f"Os {mi(dif)} de eleitores a mais no 2º turno são um saldo: quem se absteve no 1º e votou no 2º, menos quem votou no 1º e se "
         f"absteve no 2º. Os dados não mostram quantos eleitores há de cada lado nem em quem votaram."),
    ]
    longo = "\n\n".join([
        f"Abstenção entre o 1º e o 2º turno de 2026",
        f"No país (sem o exterior), a abstenção caiu de {br(nat[2026][0], 2, False)}% para {br(nat[2026][1], 2, False)}%: "
        f"{br(abs(nat[2026][2]), 2, False)} ponto, contra {br(abs(nat[2022][2]), 2, False)} ponto em 2022. Contando o exterior, foram "
        f"{mi(dif)} de eleitores a mais votando no 2º turno; em 2022, {mi(S['abst22'][2])}.",
        partes[1][1], partes[2][1], partes[3][1], partes[4][1], partes[5][1],
        "Fonte: TSE, resultados oficiais por município do 1º e do 2º turno (2026) e dados abertos de 2022. Abstenção = eleitores aptos que não votaram ÷ aptos.",
    ])
    md = ["# Resumo — abstenção entre os turnos (2026)", "", "Textos gerados a partir dos mesmos números das imagens.", "",
          "## Por imagem", ""]
    for img, txt in partes:
        md += [f"### `{img}`" if img else "### Ressalva", "", txt, ""]
    md += ["## Texto corrido", "", longo, ""]
    (OUT / "resumo.md").write_text("\n".join(md), encoding="utf-8")
    return partes, longo


def main():
    global OUT
    OUT = caminhos.saida("abstencao") / "final"
    OUT.mkdir(exist_ok=True)
    S = compute()
    capa(S); estados(S); municipios(S); dentro(S); comparacao(S)
    partes, longo = textos(S)
    for img, txt in partes:
        print(f"[{img}] {txt}\n")
    print({"margem": S["margem"], "dif": S["abst26"][2], "dif22": S["abst22"][2], "grupo": len(S["grupo"]), "share": round(S["grupo_share"], 1),
           "queda": len(S["queda"]), "estavel_alta": S["estavel_alta"], "mun_queda": S["mun_queda"], "r_nne": round(S["r_nne"], 3), "r_cs": round(S["r_cs"], 3)})


if __name__ == "__main__":
    main()
