"""Gráficos da variação da abstenção entre o 1º e o 2º turno (2026, com 2022 como referência). Brasil, sem exterior.

1) por estado (halteres 2026 × 2022), 2) histograma dos municípios, 3) municípios dentro de cada estado, 4) municípios 2022 × 2026.
Cores: 2026 = azul #2a78d6, 2022 = laranja #eb6834; textos em tinta neutra.
Lê DADOS/derivados/abstencao/abst_municipios.csv (de build_data.py) e grava as imagens em DADOS/derivados/abstencao/v1/.
"""
import csv
import math
import random
import statistics as st
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
SAIDA = caminhos.saida("abstencao")
OUT = SAIDA / "v1"
OUT.mkdir(exist_ok=True)
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8d8b85", "#e6e4df"
C26, C22 = "#2a78d6", "#eb6834"
NORTE = {"AC", "AP", "AM", "PA", "RO", "RR", "TO"}
NORDESTE = {"AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"}
C_CS = "#1baf7a"  # verde, só no gráfico por região; leva rótulo de texto
FONTE = "Fonte: TSE — resultados oficiais por município (1º e 2º turno). Abstenção = eleitores aptos que não votaram ÷ aptos. Sem o exterior."
# Segoe UI (Windows); onde não houver, DejaVu Sans (vem com o matplotlib) — as imagens mudam um pouco.
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def br(x, digits=1, sign=True):
    if round(x, digits) == 0:
        x = 0.0
    s = (f"{x:+.{digits}f}" if x else f"{0:.{digits}f}") if sign else f"{x:.{digits}f}"
    return s.replace("-", "−").replace(".", ",")


def n(x):
    return f"{x:,}".replace(",", ".")


def pontos(x, digits=1):
    return f"{br(abs(x), digits, False)} {'ponto' if abs(round(x, digits)) < 2 else 'pontos'}"


def load():
    rows = list(csv.DictReader(open(SAIDA / "abst_municipios.csv", encoding="utf-8")))
    data = {2026: {}, 2022: {}}
    for r in rows:
        if r["uf"] == "ZZ":
            continue
        a1, b1, a2, b2 = (int(r[k]) for k in ("aptos_1t", "abst_1t", "aptos_2t", "abst_2t"))
        data[int(r["ano"])][(r["uf"], r["cd_municipio"])] = (a1, b1, a2, b2)
    return data


def rate_change(items):
    a1 = sum(x[0] for x in items); b1 = sum(x[1] for x in items); a2 = sum(x[2] for x in items); b2 = sum(x[3] for x in items)
    return 100 * b1 / a1, 100 * b2 / a2, 100 * b2 / a2 - 100 * b1 / a1


def style(ax, xlabel):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel, color=INK2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v, 0) if v else "0"))


def header(fig, title, subtitle):
    # Posições em polegadas a partir do topo, para o espaço título/subtítulo não depender da altura da figura.
    # Quebra automática pela largura da figura (~12,5 caracteres por polegada no corpo 11,5): nenhuma linha passa da borda.
    h, w = fig.get_figheight(), fig.get_figwidth()
    lines = [part for line in subtitle.split("\n") for part in textwrap.wrap(line, int(w * 12.5))]
    fig.text(0.03, 1 - 0.18 / h, title, fontsize=17, fontweight="bold", va="top")
    fig.text(0.03, 1 - 0.6 / h, "\n".join(lines), fontsize=11.5, color=INK2, va="top", linespacing=1.45)
    fig.text(0.03, 0.012, FONTE, fontsize=9, color=MUTED)


def main():
    data = load()
    ufs = sorted({k[0] for k in data[2026]})
    by_uf = {y: {u: rate_change([v for k, v in data[y].items() if k[0] == u]) for u in ufs} for y in data}
    nat = {y: rate_change(list(data[y].values())) for y in data}
    d26 = {k: 100 * v[3] / v[2] - 100 * v[1] / v[0] for k, v in data[2026].items()}
    d22 = {k: 100 * v[3] / v[2] - 100 * v[1] / v[0] for k, v in data[2022].items()}
    xs = [by_uf[2022][u][2] for u in ufs]; ys = [by_uf[2026][u][2] for u in ufs]
    mx, my = st.mean(xs), st.mean(ys)
    r_uf = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    common = [k for k in d26 if k in d22]
    cx, cy = [d22[k] for k in common], [d26[k] for k in common]
    mx, my = st.mean(cx), st.mean(cy)
    r_mun = sum((x - mx) * (y - my) for x, y in zip(cx, cy)) / math.sqrt(sum((x - mx) ** 2 for x in cx) * sum((y - my) ** 2 for y in cy))
    lo_uf = min(ufs, key=lambda u: by_uf[2026][u][2]); hi_uf = max(ufs, key=lambda u: by_uf[2026][u][2])
    # Leitura: queda parecida na maior parte do país, exceção no Norte (+ AL, MA, PI).
    aptos_uf = {u: sum(v[0] for k, v in data[2026].items() if k[0] == u) for u in ufs}
    grupo = [u for u in ufs if by_uf[2026][u][2] <= -1]
    grupo_share = 100 * sum(aptos_uf[u] for u in grupo) / sum(aptos_uf.values())
    grupo_min = min(by_uf[2026][u][2] for u in grupo); grupo_max = max(by_uf[2026][u][2] for u in grupo)
    resto = sorted(set(ufs) - set(grupo))
    resto_txt = ("no Norte e em " + ", ".join(sorted(set(resto) - NORTE)[:-1]) + " e " + sorted(set(resto) - NORTE)[-1]) if NORTE <= set(resto) else ", ".join(resto)
    mais = [u for u in ufs if by_uf[2026][u][2] < by_uf[2022][u][2]]
    excecoes = sorted(set(ufs) - set(mais))
    stats = {"nat": nat, "by_uf": by_uf, "r_uf": r_uf, "r_mun": r_mun, "n_mun": len(d26)}

    # 1) Por estado: halteres 2026 (azul) × 2022 (laranja), ordenados pela variação de 2026.
    order = sorted(ufs, key=lambda u: by_uf[2026][u][2], reverse=True)
    fig, ax = plt.subplots(figsize=(11, 12.5), dpi=150)
    fig.subplots_adjust(left=0.07, right=0.83, top=0.86, bottom=0.07)
    for i, u in enumerate(order):
        a, b = by_uf[2022][u][2], by_uf[2026][u][2]
        ax.plot([a, b], [i, i], color=GRID, linewidth=2, zorder=1, solid_capstyle="round")
        ax.scatter([a], [i], s=70, color=C22, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter([b], [i], s=90, color=C26, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.text(1.02, i, f"{br(b)} pp", transform=ax.get_yaxis_transform(), va="center", fontsize=11, fontweight="bold", color=INK)
        ax.text(1.115, i, f"{br(a)}", transform=ax.get_yaxis_transform(), va="center", fontsize=10.5, color=INK2)
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.axvline(0, color=INK2, linewidth=1, zorder=0)
    for y, color, label, dy in ((2026, C26, "Brasil 2026", 0), (2022, C22, "Brasil 2022", 0)):
        ax.axvline(nat[y][2], color=color, linewidth=1.2, linestyle=(0, (4, 3)), zorder=0)
        ax.text(nat[y][2], len(order) - 0.2 + dy, f"{label}\n{br(nat[y][2], 2)} pp", ha="center", va="bottom", fontsize=9.5, color=INK2,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=SURFACE, edgecolor="none"))
    ax.text(1.02, len(order) - 0.1, "2026", transform=ax.get_yaxis_transform(), fontsize=10, fontweight="bold", color=INK2, va="bottom")
    ax.text(1.115, len(order) - 0.1, "2022", transform=ax.get_yaxis_transform(), fontsize=10, color=INK2, va="bottom")
    ax.set_ylim(-0.7, len(order) + 1.2)
    style(ax, "Variação da abstenção do 1º para o 2º turno (pontos percentuais; à esquerda caiu, à direita subiu)")
    ax.scatter([], [], s=90, color=C26, label="2026"); ax.scatter([], [], s=70, color=C22, label="2022")
    ax.legend(loc="lower left", frameon=False, fontsize=11)
    header(fig, "Abstenção do 1º para o 2º turno, por estado",
           f"No Brasil a abstenção caiu {pontos(nat[2026][2], 2)} percentual ({br(nat[2026][0], 2, False)}% → {br(nat[2026][1], 2, False)}%); em 2022 tinha caído {br(abs(nat[2022][2]), 2, False)}.\n"
           f"Em {len(grupo)} estados, com {br(grupo_share, 0, False)}% dos eleitores, a queda foi parecida: de {br(abs(grupo_max), 1, False)} a {br(abs(grupo_min), 1, False)} pontos. "
           f"Já {resto_txt} a abstenção caiu pouco,\nficou estável ou subiu, como já tinha acontecido em 2022. "
           f"Em {len(mais)} dos {len(ufs)} estados a queda foi maior que em 2022 (exceções: {', '.join(excecoes[:-1])} e {excecoes[-1]}).")
    fig.savefig(OUT / "1-estados.png", facecolor=SURFACE)
    plt.close(fig)

    # 2) Histograma dos municípios: 2026 em barras, 2022 em linha de contorno.
    lo, hi, w = -10, 16, 0.5
    edges = [lo + i * w for i in range(int((hi - lo) / w) + 1)]
    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=150)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.76, bottom=0.12)
    v26 = [min(max(x, lo + 1e-9), hi - 1e-9) for x in d26.values()]
    v22 = [min(max(x, lo + 1e-9), hi - 1e-9) for x in d22.values()]
    ax.hist(v26, bins=edges, color=C26, edgecolor=SURFACE, linewidth=1.5, label="2026", zorder=2)
    ax.hist(v22, bins=edges, histtype="step", color=C22, linewidth=2, label="2022", zorder=3)
    med26, med22 = st.median(d26.values()), st.median(d22.values())
    top = ax.get_ylim()[1]
    for med, color, label, ha in ((med26, C26, "mediana 2026", "right"), (med22, C22, "mediana 2022", "left")):
        ax.axvline(med, color=color, linewidth=1.3, linestyle=(0, (4, 3)), zorder=4)
        ax.text(med + (-0.15 if ha == "right" else 0.15), top * 0.97, f"{label}\n{br(med, 2)} pp", ha=ha, va="top", fontsize=10, color=INK2,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=SURFACE, edgecolor="none"), zorder=5)
    ax.axvline(0, color=INK2, linewidth=1, zorder=1)
    out26 = sum(x < lo or x > hi for x in d26.values())
    style(ax, "Variação da abstenção do 1º para o 2º turno em cada município (pontos percentuais)")
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.grid(axis="x", visible=False)
    ax.spines["left"].set_visible(False)
    ax.set_ylabel("número de municípios")
    ax.legend(loc="upper right", frameon=False, fontsize=11)
    caiu = sum(x < 0 for x in d26.values())
    header(fig, f"Os {n(stats['n_mun'])} municípios: a maioria caiu, mas não todos na mesma medida",
           f"Em 2026, a abstenção caiu em {n(caiu)} municípios ({br(100 * caiu / len(d26), 0, False)}%) e subiu nos demais. Metade dos municípios ficou entre "
           f"{br(sorted(d26.values())[len(d26) // 4])} e {br(sorted(d26.values())[3 * len(d26) // 4])} ponto.\n"
           f"A curva de 2026 está cerca de {pontos(med22 - med26)} à esquerda da de 2022 (mais queda) e um pouco mais espalhada.\n"
           f"Cada barra cobre 0,5 ponto; os {out26} municípios fora da faixa do gráfico estão somados nas barras das pontas.")
    fig.savefig(OUT / "2-municipios-histograma.png", facecolor=SURFACE)
    plt.close(fig)

    # 3) Municípios dentro de cada estado: pontos (2026), caixa = metade central, losango = mediana de 2022.
    lo, hi = -8, 20
    order = sorted(ufs, key=lambda u: st.median([v for k, v in d26.items() if k[0] == u]), reverse=True)
    rnd = random.Random(26)
    fig, ax = plt.subplots(figsize=(11, 13.5), dpi=150)
    fig.subplots_adjust(left=0.07, right=0.84, top=0.855, bottom=0.07)
    clipped = 0
    for i, u in enumerate(order):
        vals = sorted(v for k, v in d26.items() if k[0] == u)
        q1, q2, q3 = vals[len(vals) // 4], st.median(vals), vals[(3 * len(vals)) // 4]
        shown = [min(max(v, lo), hi) for v in vals]
        clipped += sum(v < lo or v > hi for v in vals)
        ax.scatter(shown, [i + rnd.uniform(-0.28, 0.28) for _ in shown], s=6, color=C26, alpha=0.35, linewidth=0, zorder=2)
        ax.add_patch(matplotlib.patches.FancyBboxPatch((q1, i - 0.3), q3 - q1, 0.6, boxstyle="round,pad=0,rounding_size=0.08",
                                                       facecolor="none", edgecolor=INK, linewidth=1.3, zorder=3))
        ax.plot([q2, q2], [i - 0.3, i + 0.3], color=INK, linewidth=2.2, zorder=4)
        m22 = st.median([v for k, v in d22.items() if k[0] == u])
        ax.scatter([m22], [i], marker="D", s=46, color=C22, edgecolor=SURFACE, linewidth=1.5, zorder=5)
        ax.text(1.02, i, f"{br(q2)}", transform=ax.get_yaxis_transform(), va="center", fontsize=11, fontweight="bold")
        ax.text(1.095, i, f"{br(q1)} a {br(q3)}", transform=ax.get_yaxis_transform(), va="center", fontsize=10, color=INK2)
    ax.text(1.02, len(order) - 0.2, "mediana", transform=ax.get_yaxis_transform(), fontsize=9.5, color=INK2, fontweight="bold", va="bottom")
    ax.text(1.095, len(order) - 0.2, "metade central", transform=ax.get_yaxis_transform(), fontsize=9.5, color=INK2, va="bottom")
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.7, len(order) + 0.4); ax.set_xlim(lo - 0.4, hi + 0.4)
    ax.axvline(0, color=INK2, linewidth=1, zorder=1)
    style(ax, "Variação da abstenção do 1º para o 2º turno em cada município (pontos percentuais)")
    ax.scatter([], [], s=30, color=C26, label="cada ponto = um município (2026)")
    ax.plot([], [], color=INK, linewidth=2.2, label="mediana e metade central de 2026")
    ax.scatter([], [], marker="D", s=46, color=C22, label="mediana dos municípios em 2022")
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=10)
    med_more = sum(st.median([v for k, v in d26.items() if k[0] == u]) < st.median([v for k, v in d22.items() if k[0] == u]) for u in ufs)
    norte_sobe = [v > 0 for k, v in d26.items() if k[0] in NORTE]
    # Estados (com mais de um município) onde a abstenção caiu em 95% ou mais dos municípios, na ordem do gráfico.
    quase_todos = [u for u in order if sum(k[0] == u for k in d26) > 1
                   and sum(v < 0 for k, v in d26.items() if k[0] == u) >= 0.95 * sum(k[0] == u for k in d26)]
    header(fig, f"Por estado: em {len(quase_todos)}, quase todos os municípios caíram; no Norte, a maioria subiu",
           "Cada ponto é um município; a caixa marca a metade central deles, e o traço, a mediana. O losango laranja é a mediana do estado em 2022.\n"
           f"Em {', '.join(quase_todos[:-1])} e {quase_todos[-1]}, a abstenção caiu em 95% ou mais dos municípios, com pouca diferença entre eles.\n"
           f"No Norte ela subiu em {br(100 * sum(norte_sobe) / len(norte_sobe), 0, False)}% dos municípios, com grande variação. "
           f"Em {med_more} dos {len(ufs)} estados a mediana caiu mais que em 2022. {clipped} municípios fora da faixa aparecem na borda.")
    fig.savefig(OUT / "3-municipios-por-estado.png", facecolor=SURFACE)
    plt.close(fig)

    # 4) Mesmo município em 2022 (x) × 2026 (y), tamanho pelo eleitorado.
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    fig.subplots_adjust(left=0.1, right=0.96, top=0.81, bottom=0.09)
    lo, hi = -8, 14
    sizes = [max(4, math.sqrt(data[2026][k][0]) / 6) for k in common]
    clip4 = sum(not (lo <= x <= hi and lo <= y <= hi) for x, y in zip(cx, cy))
    nne = [k[0] in NORTE | NORDESTE for k in common]

    def corr(pairs):
        xs_, ys_ = [p[0] for p in pairs], [p[1] for p in pairs]
        mx_, my_ = st.mean(xs_), st.mean(ys_)
        return sum((x - mx_) * (y - my_) for x, y in pairs) / math.sqrt(sum((x - mx_) ** 2 for x in xs_) * sum((y - my_) ** 2 for y in ys_))

    r_nne = corr([(x, y) for x, y, f in zip(cx, cy, nne) if f])
    r_cs = corr([(x, y) for x, y, f in zip(cx, cy, nne) if not f])
    for flag, color, label, z in ((True, C26, "Norte e Nordeste", 2), (False, C_CS, "Centro-Sul (Sul, Sudeste e Centro-Oeste)", 3)):
        idx = [i for i, f in enumerate(nne) if f == flag]
        ax.scatter([min(max(cx[i], lo), hi) for i in idx], [min(max(cy[i], lo), hi) for i in idx], s=[sizes[i] for i in idx],
                   color=color, alpha=0.35, linewidth=0, zorder=z, label=label)
    ax.plot([lo, hi], [lo, hi], color=INK2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=4)
    ax.text(-1.2, -6.6, "Centro-Sul:\nquase todos caíram\nde forma parecida", fontsize=10, color=INK, ha="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=SURFACE, edgecolor=C_CS, linewidth=1.2), zorder=6)
    ax.text(6.5, 1.0, "Norte e Nordeste:\nrepetem 2022 de perto", fontsize=10, color=INK, ha="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=SURFACE, edgecolor=C26, linewidth=1.2), zorder=6)
    leg = ax.legend(loc="upper left", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=10, markerscale=1.5)
    for handle in leg.legend_handles:
        handle.set_alpha(1); handle.set_sizes([40])
    ax.text(hi - 0.3, hi - 1.0, "igual a 2022", ha="right", fontsize=10, color=INK2, rotation=45, rotation_mode="anchor")
    ax.axhline(0, color=GRID, linewidth=1, zorder=1); ax.axvline(0, color=GRID, linewidth=1, zorder=1)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.spines[["top", "right"]].set_visible(False)
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(matplotlib.ticker.MultipleLocator(4))
        axis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v, 0) if v else "0"))
    ax.set_xlabel("Variação em 2022 (pontos percentuais)"); ax.set_ylabel("Variação em 2026 (pontos percentuais)")
    ax.grid(color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    below = sum(y < x for x, y in zip(cx, cy))
    header(fig, "Município a município, 2026 lembra 2022 — sobretudo no Norte e no Nordeste",
           f"Cada ponto é um município (maior = mais eleitores). Correlação entre a variação de 2022 e a de 2026: {br(r_nne, 2, False)} no Norte e Nordeste, "
           f"{br(r_cs, 2, False)} no Centro-Sul. {n(below)} dos {n(len(common))} municípios ({br(100 * below / len(common), 0, False)}%) ficaram abaixo da linha tracejada: "
           f"neles a abstenção variou para menos em 2026 do que em 2022. "
           f"{clip4} municípios fora da faixa de {br(lo, 0)} a {br(hi, 0)} pontos aparecem encostados na borda.")
    fig.savefig(OUT / "4-municipios-2022x2026.png", facecolor=SURFACE)
    plt.close(fig)
    print({"nat": {y: [round(v, 2) for v in nat[y]] for y in nat}, "r_uf": round(r_uf, 3), "r_mun": round(r_mun, 3),
           "med26": round(med26, 2), "med22": round(med22, 2), "caiu": caiu, "below": below, "n": len(d26),
           "grupo": (len(grupo), round(grupo_share, 1), round(grupo_max, 2), round(grupo_min, 2), resto_txt), "mais": len(mais), "excecoes": excecoes,
           "r_nne": round(r_nne, 3), "r_cs": round(r_cs, 3)})


if __name__ == "__main__":
    main()
