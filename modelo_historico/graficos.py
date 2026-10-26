"""Gráficos do modelo histórico (resultados.json e previsoes.csv de modelo.py): 1-comparecimento.png, 2-setas.png,
3-municipios.png, 4-mapa-2026.png e 5-municipios-2026.png, em DADOS/derivados/modelo_historico/. Grava também exibidos.json
(os números arredondados que aparecem nos gráficos, usados por texto.py).
Estilo e moldura de ../abstencao/charts_v2.py; mapa por UF de ../biometria/bio_charts.py (contornos em ../comum/ufs.json).

Convenção de arredondamento: toda diferença mostrada é a conta dos números mostrados (resultado arredondado − estimativa
arredondada), para que o leitor possa refazer a subtração e chegar no mesmo número.
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
sys.path.insert(0, str(HERE.parent / "abstencao"))
sys.path.insert(0, str(HERE.parent / "biometria"))
import caminhos  # noqa: E402
import charts_v2 as cv  # noqa: E402
import matplotlib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
import bio_charts as bc  # noqa: E402  (mapa do Brasil, rótulos e barra de cor)

OUT = caminhos.saida("modelo_historico")
cv.KICKER = "Eleições 2026 · o 2º turno comparado aos anteriores"
FONTE_VOTO = ("Fonte: TSE (dados abertos de 2002 a 2022 e 1º turno de 2026; 2º turno de 2026 por município no site de resultados). "
              "Estimativa de cada município feita depois da eleição, só com o 1º turno, pela regra média de transferência de votos dos "
              "outros 2º turnos (cada ano é estimado sem os próprios dados); no total do país e das UFs, cada município pesa pelos votos "
              "válidos do 2º turno. Sem o exterior.")
FONTE_COMP = ("Fonte: TSE (dados abertos de 2002 a 2022 e 1º turno de 2026; 2º turno de 2026 por município no site de resultados). "
              "Comparecimento: votantes ÷ eleitores aptos, somando todos os municípios. Sem o exterior.")
cv.FONTE = FONTE_VOTO
cv.MUTED = cv.INK2
R = json.load(open(OUT / "resultados.json", encoding="utf-8"))
T = R["teste"]
ANOS = [2002, 2006, 2010, 2014, 2018, 2022, 2026]
NOMES = {2002: "Lula × Serra", 2006: "Lula × Alckmin", 2010: "Dilma × Serra", 2014: "Dilma × Aécio", 2018: "Haddad × Bolsonaro",
         2022: "Lula × Bolsonaro", 2026: "Lula × Flávio"}
C_PREV, C_REAL, C_PONTO, C_26 = "#86b6ef", "#1c5cab", "#8f9aa6", "#1c5cab"
# divergente sem cor de partido: roxo = mais acima do estimado que o país; laranja = menos
DIV = LinearSegmentedColormap.from_list("div", ["#b35806", "#f1a340", "#fee0b6", "#f0efec", "#d8daeb", "#998ec3", "#542788"])


def r1(x):
    """Porcentagem com 1 casa (número), a mesma que aparece escrita."""
    return round(100 * x, 1)


def est(a):
    return r1(T[str(a)]["prev_a"]["nacional"])


def res(a):
    return r1(T[str(a)]["real"])


def gap(a):
    return round(res(a) - est(a), 1)


GAPS = {a: gap(a) for a in ANOS}
HIST = [GAPS[a] for a in ANOS[:-1]]
FUNDO = dict(boxstyle="square,pad=0.15", facecolor=cv.SURFACE, edgecolor="none")


def f1(x):
    return cv.br(x, 1, False)


def nuvens():
    """Um gráfico por 2º turno: cada bolinha é um município (estimativa × resultado). A diagonal é 'exatamente como estimado'."""
    P = pd.read_csv(OUT / "previsoes.csv", dtype={"CD_MUNICIPIO": str}).dropna(subset=["y", "prev_a"])
    geo = {a: 100 * T[str(a)]["prev_a"]["geo_mae_municipio"] for a in ANOS}
    fig = cv.figure(12, 14.2)
    top = cv.frame(fig, "Cada bolinha é um município: o 2º turno estimado pelo 1º e o resultado, de 2002 a 2026",
                   "Em cada ano, estimamos o voto no candidato do PT em cada município usando só o 1º turno e a regra média dos outros 2º "
                   "turnos. Bolinha sobre a linha: o município votou como estimado. Acima da linha, o PT teve mais votos do que o "
                   "estimado; abaixo, menos. "
                   "Tamanho da bolinha: número de eleitores.",
                   [(f"{cv.br(GAPS[2026], 1)} p.p.", "o quanto Lula ficou acima do estimado no país em 2026", None),
                    (f"{f1(geo[2026])} p.p.", "a distância média (pesando pelos votos) entre o resultado de cada município e a "
                     "estimativa somada aos +2,3 do país todo, em 2026", None),
                    (f"{f1(min(geo[a] for a in ANOS[:-1]))} a {f1(max(geo[a] for a in ANOS[:-1]))}", "a mesma medida de 2002 a 2022 "
                     "(quanto menor, mais o país se moveu por igual)", None)])
    W, H = fig.get_figwidth(), fig.get_figheight()
    cols, rows, gapx, gapy = 4, 2, 0.32, 0.75
    left, right, bottom = 0.75, 0.35, 1.45
    pw = (W - left - right - gapx * (cols - 1)) / cols
    ph = min(pw, (top * H - bottom - 0.25 - gapy * (rows - 1) - 0.55) / rows)
    y0 = top * H - 0.55 - ph
    for k, a in enumerate(ANOS + ["ler"]):
        r, c = divmod(k, cols)
        ax = fig.add_axes([(left + c * (pw + gapx)) / W, (y0 - r * (ph + gapy)) / H, pw / W, ph / H])
        ax.set_xlim(0, 100); ax.set_ylim(0, 100)
        ax.set_aspect("equal")
        if a == "ler":
            como_ler(ax)
            continue
        d = P[P["ano"] == a]
        cor = C_26 if a == 2026 else C_PONTO
        ax.scatter(100 * d["prev_a"], 100 * d["y"], s=(d["QT_APTOS_1"] / 4000).clip(0.6, 40), color=cor, alpha=0.32 if a == 2026 else 0.25,
                   linewidth=0, zorder=2, rasterized=True)
        ax.plot([0, 100], [0, 100], color=cv.INK, linewidth=1.1, zorder=3)
        ax.set_title(f"{a} · {NOMES[a]}", fontsize=11.5 if a != 2026 else 12.5, fontweight="bold", loc="left", pad=6, color=cv.INK)
        # canto de baixo à direita: quase não tem municípios, a caixa não esconde pontos
        ax.text(97, 4, f"país: estimado {f1(est(a))}%\nresultado {f1(res(a))}% ({cv.br(GAPS[a], 1)})", fontsize=9.3, va="bottom",
                ha="right", color=cv.INK, linespacing=1.3, bbox=dict(boxstyle="round,pad=0.25", facecolor=cv.SURFACE, edgecolor="none",
                                                                       alpha=0.9), zorder=4)
        ax.tick_params(labelsize=8.5, length=0, colors=cv.INK2)
        ax.set_xticks([0, 50, 100]); ax.set_yticks([0, 50, 100])
        for sp in ax.spines.values():
            sp.set_color("#d8d6d0" if a != 2026 else C_26)
            sp.set_linewidth(0.8 if a != 2026 else 2)
        ax.set_facecolor("#ffffff")
        if r == rows - 1:
            ax.set_xlabel("estimado (%)", fontsize=9.5, color=cv.INK2)
        if c == 0:
            ax.set_ylabel("resultado (%)", fontsize=9.5, color=cv.INK2)
    fig.savefig(OUT / "3-municipios.png", facecolor=cv.SURFACE)
    plt.close(fig)


def como_ler(ax, fs=1.0, quem="PT"):
    """Quadro explicativo no 8º espaço: acima, abaixo ou sobre a linha. fs aumenta as fontes na versão só de 2026."""
    ax.set_facecolor(cv.TILE)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.plot([44, 96], [44, 96], color=cv.INK, linewidth=1.1)
    for x, y in ((50, 84), (84, 62)):
        ax.scatter([x], [y], s=60 * fs ** 2, color=C_26, zorder=3)
    ax.text(46, 84, f"{quem} acima\ndo estimado", ha="right", va="center", fontsize=9.2 * fs, color=cv.INK)
    ax.text(66, 71, "linha: como estimado", rotation=45, rotation_mode="anchor", ha="center", va="bottom", fontsize=9.2 * fs,
            color=cv.INK)
    ax.text(84, 56, f"{quem} abaixo\ndo estimado", ha="center", va="top", fontsize=9.2 * fs, color=cv.INK)
    ax.text(5, 4, "Nuvem toda acima ou abaixo da\nlinha: o país mudou junto.\nNuvem larga: os municípios\nmudaram de jeitos diferentes.",
            ha="left", va="bottom", fontsize=8.8 * fs, color=cv.INK2, linespacing=1.25)
    ax.set_title("Como ler", fontsize=12 * fs, fontweight="bold", loc="left", pad=6, color=cv.INK)


def nuvem_2026():
    """Só 2026: cada bolinha é um município (estimativa × resultado), com o quadro 'Como ler' ao lado."""
    P = pd.read_csv(OUT / "previsoes.csv", dtype={"CD_MUNICIPIO": str}).dropna(subset=["y", "prev_a"])
    d = P[P["ano"] == 2026]
    geo = {a: 100 * T[str(a)]["prev_a"]["geo_mae_municipio"] for a in ANOS}
    n_acima = int((d["y"] > d["prev_a"]).sum())
    # medidas na escala real da figura (12 × cv.SCALE de largura): gráfico de 2026 e 'Como ler' lado a lado, sem passar da borda
    left, right, gap, bottom = 0.75, 0.45, 0.45, 1.55
    livre = 12 * cv.SCALE - left - right - gap
    pw, lw = 0.63 * livre, 0.37 * livre
    fig, top = bc.framed(12, bottom + pw + 0.6, lambda fig: cv.frame(
        fig, "2026: cada bolinha é um município, com o 2º turno estimado pelo 1º e o resultado",
        "Estimamos o voto em Lula em cada município usando só o 1º turno e a regra média dos 2º turnos de 2002 a 2022. Bolinha sobre "
        "a linha: o município votou como estimado. Acima da linha, Lula teve mais votos do que o estimado; abaixo, menos. Tamanho "
        "da bolinha: número de eleitores.",
        [(f"{cv.br(GAPS[2026], 1)} p.p.", "o quanto Lula ficou acima do estimado no país", None),
         (f"{n_acima:,} de {len(d):,}".replace(",", "."), "municípios com Lula acima do estimado", None),
         (f"{f1(geo[2026])} p.p.", f"a distância média (pesando pelos votos) entre o resultado de cada município e a estimativa somada "
          f"aos {cv.br(GAPS[2026], 1)} do país; de {f1(min(geo[a] for a in ANOS[:-1]))} a {f1(max(geo[a] for a in ANOS[:-1]))} "
          "entre 2002 e 2022", None)]))
    W, H = fig.get_figwidth(), fig.get_figheight()
    y0 = top * H - 0.6 - pw
    ax = fig.add_axes([left / W, y0 / H, pw / W, pw / H])
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    ax.scatter(100 * d["prev_a"], 100 * d["y"], s=(d["QT_APTOS_1"] / 4000).clip(0.6, 40) * 5, color=C_26, alpha=0.3, linewidth=0,
               zorder=2, rasterized=True)
    ax.plot([0, 100], [0, 100], color=cv.INK, linewidth=1.3, zorder=3)
    ax.set_title(f"2026 · {NOMES[2026]}", fontsize=14, fontweight="bold", loc="left", pad=8, color=cv.INK)
    ax.text(97, 4, f"país: estimado {f1(est(2026))}%\nresultado {f1(res(2026))}% ({cv.br(GAPS[2026], 1)})", fontsize=12, va="bottom",
            ha="right", color=cv.INK, linespacing=1.3, bbox=dict(boxstyle="round,pad=0.3", facecolor=cv.SURFACE, edgecolor="none",
                                                                   alpha=0.9), zorder=4)
    ax.tick_params(labelsize=10.5, length=0, colors=cv.INK2)
    ax.set_xticks([0, 25, 50, 75, 100]); ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(color=cv.GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_color(C_26)
        sp.set_linewidth(2)
    ax.set_facecolor("#ffffff")
    ax.set_xlabel("estimado (%)", fontsize=11, color=cv.INK2)
    ax.set_ylabel("resultado (%)", fontsize=11, color=cv.INK2)
    lx = left + pw + gap
    ler = fig.add_axes([lx / W, (y0 + pw - lw) / H, lw / W, lw / H])
    ler.set_xlim(0, 100); ler.set_ylim(0, 100)
    ler.set_aspect("equal")
    como_ler(ler, fs=1.22, quem="Lula")
    fig.savefig(OUT / "5-municipios-2026.png", facecolor=cv.SURFACE)
    plt.close(fig)


def setas():
    """Uma seta por 2º turno, da estimativa (só com o 1º turno) ao resultado; em 2026, a faixa dos desvios de 2002 a 2022."""
    fig = cv.figure(12, 13.0)
    lo, hi = est(2026) + min(HIST), est(2026) + max(HIST)
    top = cv.frame(fig, "Quanto o 2º turno se afastou do estimado pelo 1º, de 2002 a 2026",
                   "Cada seta sai da estimativa para o candidato do PT, feita depois da eleição com o 1º turno de cada município e a regra "
                   "média dos outros 2º turnos, e chega ao resultado. Seta para a direita: o PT terminou acima do estimado; para a esquerda, abaixo. Em 2026, "
                   "a faixa azul mostra onde o resultado cairia se o desvio fosse igual ao de qualquer ano entre 2002 e 2022.",
                   [(f"{f1(est(2026))}% → {f1(res(2026))}%", "estimado e resultado de Lula em 2026 (sem o exterior)", None),
                    (f"{cv.br(GAPS[2026], 1)} p.p.", f"o tamanho da seta de 2026; com o desvio de algum ano de 2002 a 2022, ficaria entre {f1(lo)}% e {f1(hi)}%", None),
                    (f"{cv.br(min(HIST), 1)} a {cv.br(max(HIST), 1)}", "o tamanho das setas de 2002 a 2022, em pontos", None)])
    ax = cv.axes_below(fig, top, left=2.6, right=0.6, bottom=1.6)
    n = len(ANOS)
    for i, a in enumerate(ANOS):
        p, r = est(a), res(a)
        y = n - 1 - i
        if a == 2026:
            ax.add_patch(matplotlib.patches.FancyBboxPatch((lo, y - 0.32), hi - lo, 0.64, boxstyle="round,pad=0,rounding_size=0.15",
                                                           facecolor="#dfe9f7", edgecolor="none", zorder=0))
            ax.text(hi - 0.2, y + 0.42, "faixa dos desvios de 2002 a 2022", fontsize=9.5, color=cv.INK2, ha="right", va="bottom",
                    bbox=FUNDO, zorder=5)
        cor = C_26 if a == 2026 else "#4d5560"
        ax.annotate("", xy=(r, y), xytext=(p, y), arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.4", color=cor, linewidth=2.6,
                                                                  shrinkA=0, shrinkB=0), zorder=3)
        ax.scatter([p], [y], s=55, color="#ffffff", edgecolor=cor, linewidth=2, zorder=4)
        fundo = None if a == 2026 else FUNDO
        ax.text(max(p, r) + 0.7, y, f"{cv.br(GAPS[a], 1)} p.p.", va="center", fontsize=12, fontweight="bold", color=cv.INK, bbox=fundo, zorder=5)
        ax.text(min(p, r) - 0.7, y, f"{f1(p)}% → {f1(r)}%", va="center", ha="right", fontsize=10, color=cv.INK2, bbox=fundo, zorder=5)
    ax.set_yticks(range(n), [f"{a}\n{NOMES[a]}" for a in reversed(ANOS)], fontsize=11)
    ax.set_ylim(-0.7, n - 0.3)
    ax.axvline(50, color=cv.INK2, linewidth=1, linestyle=(0, (3, 3)), zorder=0)
    ax.text(50.3, n - 0.45, "50%", fontsize=9.5, color=cv.INK2, va="bottom")
    ax.set_xlim(30, 72)
    cv.xstyle(ax, "candidato do PT, % dos votos válidos no 2º turno  ·  bolinha: estimado; ponta da seta: resultado")
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.savefig(OUT / "2-setas.png", facecolor=cv.SURFACE)
    plt.close(fig)


def mapa():
    """Quanto Lula ficou acima do estimado em cada UF (rótulos), com a cor dizendo se foi mais ou menos que no país inteiro.
    Os rótulos são o próprio desvio da UF: o leitor compara com o +2,3 do país sem precisar subtrair."""
    t26 = T["2026"]["prev_a"]
    acima = {u: -100 * e for u, e in t26["erro_uf"].items()}  # resultado − estimado, por UF (todas positivas)
    desloc = 100 * (T["2026"]["real"] - t26["nacional"])
    geo_hist = [100 * T[str(a)]["prev_a"]["geo_mae_uf"] for a in ANOS[:-1]]
    umin, umax = min(acima, key=acima.get), max(acima, key=acima.get)
    assert min(acima.values()) > 0
    lim = math.ceil(max(abs(v - desloc) for v in acima.values()) * 2) / 2
    mw = 6.0
    mh = mw * bc.MAP_RATIO
    fig, top = bc.framed(12, 1.95 + mh + 0.3, lambda fig: cv.frame(
        fig, "2026: Lula acima do estimado em cada UF",
        f"Em pontos percentuais: resultado de Lula menos o estimado pelo 1º turno. Ele ficou acima do estimado nas 27 UFs. "
        f"A cor compara com o país ({cv.br(GAPS[2026], 1)}): roxo, acima mais que isso; laranja, acima menos que isso; cinza, perto "
        f"de {cv.br(GAPS[2026], 1)}.",
        [("27 de 27", f"UFs com Lula acima do estimado, de {cv.br(acima[umin], 1)} ponto em {umin} a {cv.br(acima[umax], 1)} em {umax}", None),
         (f"{cv.br(GAPS[2026], 1)} p.p.", "no país inteiro, a referência das cores", None),
         (f"{f1(100 * t26['geo_mae_uf'])} p.p.", f"quanto, em média, cada UF ficou longe dos {cv.br(GAPS[2026], 1)} do país em 2026, cada UF contando igual (de {f1(min(geo_hist))} a "
          f"{f1(max(geo_hist))} entre 2002 e 2022)", None)]))
    W, H = fig.get_figwidth(), fig.get_figheight()
    ax = fig.add_axes([(W - mw - 1.1) / 2 / W, 1.9 / H, mw / W, mh / H])
    norm = TwoSlopeNorm(vmin=desloc - lim, vcenter=desloc, vmax=desloc + lim)
    bc.draw_map(ax, bc.shapes(), acima, DIV, norm, lambda v: cv.br(v, 1), label_size=10)
    ticks = [t / 2 for t in range(math.ceil(2 * (desloc - lim)), math.floor(2 * (desloc + lim)) + 1)]
    bc.colorbar(fig, [0.55 / W, 1.32 / H, 4.6 / W, 0.14 / H], DIV, norm, ticks, lambda t: cv.br(t, 1),
                f"pontos acima do estimado na UF (país: {cv.br(GAPS[2026], 1)})")
    fig.savefig(OUT / "4-mapa-2026.png", facecolor=cv.SURFACE)
    plt.close(fig)


def comparecimento():
    """Gráfico 1: uma seta por 2º turno, da parcela do eleitorado que votou no 1º turno até a do 2º. Os rótulos de variação são a
    subtração dos percentuais arredondados que aparecem ao lado."""
    cv.FONTE = FONTE_COMP
    P = pd.read_csv(OUT / "previsoes.csv", dtype={"CD_MUNICIPIO": str})
    P = P.dropna(subset=["QT_COMPARECIMENTO_2", "QT_APTOS_2"])
    niv = {}
    for a, g in P.groupby("ano"):
        niv[int(a)] = (round(100 * g["QT_COMPARECIMENTO_1"].sum() / g["QT_APTOS_1"].sum(), 1),
                       round(100 * g["QT_COMPARECIMENTO_2"].sum() / g["QT_APTOS_2"].sum(), 1))
    var = {a: round(c2 - c1, 1) for a, (c1, c2) in niv.items()}
    caiu = [a for a in ANOS[:-1] if var[a] < 0]
    subiu = [a for a in ANOS[:-1] if var[a] > 0]
    assert var[2026] > max(var[a] for a in ANOS[:-1]) and len(subiu) == 1
    x = P[P["ano"] == 2026]
    lado = {}
    for nome, g in (("lula", x[x["pt_1"] > x["adv_1"]]), ("flavio", x[x["pt_1"] < x["adv_1"]])):
        lado[nome] = 100 * (g["dcomp"] * g["QT_APTOS_1"]).sum() / g["QT_APTOS_1"].sum()
    fig = cv.figure(12, 11.4)
    top = cv.frame(fig, f"Do 1º para o 2º turno, o comparecimento costuma cair. Em 2026, subiu {f1(var[2026])} ponto percentual",
                   "Parcela dos eleitores aptos que foi votar no 1º e no 2º turno de cada eleição para presidente (sem o exterior). Cada "
                   "seta vai do 1º para o 2º turno: para a esquerda, menos gente votou no 2º turno; para a direita, mais. Em azul-claro, "
                   f"{subiu[0]}, o único outro 2º turno com aumento.",
                   [(f"{cv.br(var[2026], 1)} p.p.", f"em 2026: de {f1(niv[2026][0])}% para {f1(niv[2026][1])}% dos eleitores, o maior "
                     "aumento desde 2002", C_26),
                    (f"{len(caiu)} de {len(ANOS) - 1}", f"2º turnos de 2002 a 2022 em que menos gente votou do que no 1º; a exceção foi "
                     f"{subiu[0]} ({cv.br(var[subiu[0]], 1)})", None),
                    (f"{cv.br(lado['lula'], 1)} e {cv.br(lado['flavio'], 1)}", "o aumento em 2026 nos municípios onde Lula e onde Flávio "
                     "venceram o 1º turno", None)])
    ax = cv.axes_below(fig, top, left=2.6, right=0.6, bottom=1.5)
    n = len(ANOS)
    for i, a in enumerate(ANOS):
        c1, c2 = niv[a]
        y = n - 1 - i
        cor = C_26 if a == 2026 else (C_PREV if c2 > c1 else "#4d5560")
        ax.annotate("", xy=(c2, y), xytext=(c1, y), arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.4", color=cor,
                                                                    linewidth=3 if a == 2026 else 2.6, shrinkA=0, shrinkB=0), zorder=3)
        ax.scatter([c1], [y], s=55, color="#ffffff", edgecolor=cor, linewidth=2, zorder=4)
        rot = f"{cv.br(var[a], 1)} p.p." + ("  (o maior aumento)" if a == 2026 else "")
        ax.text(max(c1, c2) + 0.18, y, rot, va="center", fontsize=12.5 if a == 2026 else 12, fontweight="bold",
                color=cv.INK, zorder=5)
        ax.text(min(c1, c2) - 0.18, y, f"{f1(c1)}% → {f1(c2)}%", va="center", ha="right", fontsize=10.5, color=cv.INK2, zorder=5)
    ax.set_yticks(range(n), [f"{a}\n{NOMES[a]}" for a in reversed(ANOS)], fontsize=11)
    ax.set_ylim(-0.7, n - 0.3)
    xs = [v for c in niv.values() for v in c]
    ax.set_xlim(math.floor(min(xs)) - 1.6, math.ceil(max(xs)) + 2.2)
    cv.xstyle(ax, "% dos eleitores aptos que foram votar  ·  bolinha: 1º turno; ponta da seta: 2º turno")
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.savefig(OUT / "1-comparecimento.png", facecolor=cv.SURFACE)
    plt.close(fig)
    cv.FONTE = FONTE_VOTO
    return {"lula": lado["lula"], "flavio": lado["flavio"], "niveis": {str(a): v for a, v in niv.items()},
            "variacao": {str(a): v for a, v in var.items()}}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    nuvens()
    setas()
    mapa()
    nuvem_2026()
    extra = comparecimento()
    json.dump({"gaps": GAPS, "comparecimento": extra}, open(OUT / "exibidos.json", "w", encoding="utf-8"), indent=1)
    print("ok", GAPS, extra)
