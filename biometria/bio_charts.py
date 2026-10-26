"""Biometria no 1º e no 2º turno de 2026, por estado: mapas (1º e 2º turno; diferença) e barras.
Lê bio_uf.json e cobertura.json e grava 1-mapas-1t-2t.png, 2-mapa-diferenca.png, 3-barras-estados.png e numeros.json, tudo em
DADOS/derivados/biometria. Contornos dos estados: ../comum/ufs.json.

Medida (a mesma do boletim de urna do TSE): votos de eleitores que têm biometria cadastrada mas não foram habilitados pela digital.
1º turno: campo QT_ELEI_BIOM_SEM_HABILITACAO dos boletins de urna (dados abertos do TSE).
2º turno: os logs de todas as urnas, contando a mesma coisa. Conferido no 1º turno em 300 seções sorteadas (bio_sample_1t.py):
299 iguais ao boletim só com o log principal; a outra, de urna substituída, fica igual ao contar também o log aninhado.
Estilo e moldura reaproveitados de ../abstencao/charts_v2.py.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
sys.path.insert(0, str(HERE.parent / "abstencao"))
import caminhos  # noqa: E402
import charts_v2 as cv  # noqa: E402
import matplotlib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, Normalize  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

OUT = caminhos.saida("biometria")
GEO = HERE.parent / "comum" / "ufs.json"
cv.KICKER = "Eleições 2026 · biometria no 1º e no 2º turno"
FONTE = ("Fonte: TSE. 1º turno: boletins de urna (campo QT_ELEI_BIOM_SEM_HABILITACAO). 2º turno: logs das urnas, contando o mesmo caso "
         "(inclui o log da urna original onde houve troca; {cobertura}). Método conferido em 300 seções sorteadas do 1º turno: todas iguais "
         "ao boletim. Percentual sobre os votos. Sem o exterior.")
cv.MUTED = cv.INK2  # rodapé com mais contraste
SEQ = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
# Divergente azul (menos votos sem habilitação pela digital) -> vermelho (mais), com cinza no meio; claros simétricos.
DIV = LinearSegmentedColormap.from_list("div", ["#184f95", "#2a78d6", "#c6daf6", "#f0efec", "#f6c4c3", "#e34948", "#a8302f"])
MEIO = 6.7  # percentual do país nos dois turnos (6,68% e 6,75%), arredondado: centro da escala dos mapas de nível
C1, C2 = cv.C22, cv.C26  # 1º turno laranja, 2º turno azul (a mesma lógica "referência × atual" da análise de abstenção)
# Estados pequenos: rótulo no mar, com linha fina até o estado.
FORA = {"CE": (-37.4, -1.4), "RN": (-33.4, -4.6), "PB": (-33.0, -6.6), "PE": (-33.0, -8.6), "AL": (-33.4, -10.6), "SE": (-34.2, -12.6),
        "ES": (-37.4, -20.2), "RJ": (-40.2, -24.8), "DF": (-37.8, -16.6), "SC": (-46.2, -29.2)}


def load():
    acc = json.load(open(OUT / "bio_uf.json", encoding="utf-8"))
    S = {uf: {"v1": a[0], "b1": a[1], "v2": a[2], "b2": a[3]} for uf, a in acc.items()}
    for d in S.values():
        d["p1"], d["p2"] = 100 * d["b1"] / d["v1"], 100 * d["b2"] / d["v2"]
        d["dp"] = d["p2"] - d["p1"]
    nat = {k: sum(d[k] for d in S.values()) for k in ("v1", "b1", "v2", "b2")}
    nat["p1"], nat["p2"] = 100 * nat["b1"] / nat["v1"], 100 * nat["b2"] / nat["v2"]
    return S, nat


def shapes():
    out = {}
    for item in json.load(open(GEO, encoding="utf-8")):
        polys = item["coordinates"] if item["type"] == "MultiPolygon" else [item["coordinates"]]
        out[item["sigla"]] = [p[0] for p in polys]
    return out


def centroid(rings):
    ring = max(rings, key=lambda r: abs(area(r)))
    a = area(ring)
    cx = sum((x0 + x1) * (x0 * y1 - x1 * y0) for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1])) / (6 * a)
    cy = sum((y0 + y1) * (x0 * y1 - x1 * y0) for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1])) / (6 * a)
    return cx, cy


def area(ring):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1])) / 2


ADJ = {"PA": (0.4, 0.6), "AM": (0.0, 0.6), "MG": (0.3, 0.0), "GO": (-0.3, 0.6), "PI": (0.0, -0.7), "AC": (0.6, -0.2), "TO": (0.2, 0.0),
       "BA": (0.3, 0.0), "MA": (-0.6, 0.7), "SP": (0.4, 0.5), "PR": (-0.3, -0.3)}


def draw_map(ax, geo, values, cmap, norm, fmt, label_size=9.0):
    for rings in geo.values():  # contorno cinza-claro por baixo: estado de cor quase igual ao fundo continua visível
        for ring in rings:
            ax.add_patch(Polygon(ring, closed=True, facecolor="none", edgecolor="#cfcdc7", linewidth=2.2, zorder=1, clip_on=False))
    for uf, rings in geo.items():
        color = cmap(norm(values[uf]))
        for ring in rings:
            ax.add_patch(Polygon(ring, closed=True, facecolor=color, edgecolor=cv.SURFACE, linewidth=0.9, zorder=2, clip_on=False))
    for uf, rings in geo.items():
        cx, cy = centroid(rings)
        dx, dy = ADJ.get(uf, (0, 0))
        cx, cy = cx + dx, cy + dy
        fill = cmap(norm(values[uf]))
        lum = 0.2126 * fill[0] + 0.7152 * fill[1] + 0.0722 * fill[2]
        if uf in FORA:
            lx, ly = FORA[uf]
            ax.plot([cx, lx - 0.9], [cy, ly], color=cv.MUTED, linewidth=0.7, zorder=3, clip_on=False)
            ax.text(lx, ly, f"{uf} {fmt(values[uf])}", fontsize=label_size, va="center", ha="left", color=cv.INK, zorder=4)
        else:
            ax.text(cx, cy, f"{uf}\n{fmt(values[uf])}", fontsize=label_size, ha="center", va="center", linespacing=1.05,
                    color="#ffffff" if lum < 0.45 else cv.INK, fontweight="bold", zorder=4)
    ax.set_xlim(*XLIM); ax.set_ylim(*YLIM)  # eixo justo no continente; rótulos do litoral e Noronha ficam à direita, fora do eixo
    ax.set_aspect(ASPECT)
    ax.axis("off")


XLIM, YLIM, ASPECT = (-74.3, -34.6), (-34.0, 5.5), 1 / math.cos(math.radians(15))
MAP_RATIO = (YLIM[1] - YLIM[0]) * ASPECT / (XLIM[1] - XLIM[0])  # altura / largura do mapa


def framed(w, body_in, header):
    """Figura com a altura exata: cabeçalho medido numa primeira passada + corpo (mapa, legenda de cor e rodapé), em polegadas."""
    fig = cv.figure(w, 10)
    head = (1 - header(fig)) * fig.get_figheight()
    plt.close(fig)
    fig = cv.figure(w, (head + body_in) / cv.SCALE)
    return fig, header(fig)


def colorbar(fig, rect, cmap, norm, ticks, fmt, label):
    cax = fig.add_axes(rect)
    cb = matplotlib.colorbar.ColorbarBase(cax, cmap=cmap, norm=norm, orientation="horizontal", ticks=ticks)
    cb.ax.set_xticklabels([fmt(t) for t in ticks], fontsize=10.5, color=cv.INK2)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0)
    cb.ax.set_title(label, fontsize=11, color=cv.INK2, loc="left", pad=6)


def mapas(S, nat, geo):
    pct = lambda v: cv.br(v, 1, False) + "%"
    pct2 = lambda v: cv.br(v, 2, False) + "%"
    left, gap, right = 0.4, 0.9, 0.85  # gap e right: espaço dos rótulos do litoral
    mw = (12 * cv.SCALE - left - gap - right) / 2
    mh = mw * MAP_RATIO
    bottom = 1.9
    fig, top = framed(12, bottom + mh + 0.5, lambda fig: cv.frame(fig, "Votos de eleitores com biometria que não foram habilitados pela digital",
                   "Percentual dos votos, por estado, em que o eleitor tinha biometria cadastrada, mas foi habilitado sem a digital: "
                   "o mesário confere os dados do eleitor e libera o voto. Vermelho: acima de 6,7% (o percentual do país nos dois turnos); "
                   "azul: abaixo. Mesma escala nos dois mapas.",
                   [(cv.n(nat["b1"]), f"votos no 1º turno ({pct2(nat['p1'])} do total)", None),
                    (cv.n(nat["b2"]), f"votos no 2º turno ({pct2(nat['p2'])} do total)", None),
                    (f"{cv.br(nat['p2'] - nat['p1'], 2)} p.p.", "variação do percentual no país", None)]))
    W, H = fig.get_figwidth(), fig.get_figheight()
    lo = math.floor(min(min(d["p1"], d["p2"]) for d in S.values()))
    hi = math.ceil(max(max(d["p1"], d["p2"]) for d in S.values()))
    norm = TwoSlopeNorm(vmin=lo, vcenter=MEIO, vmax=hi)
    for i, (key, title) in enumerate((("p1", "1º turno"), ("p2", "2º turno"))):
        ax = fig.add_axes([(left + i * (mw + gap)) / W, bottom / H, mw / W, mh / H])
        draw_map(ax, geo, {uf: d[key] for uf, d in S.items()}, DIV, norm, pct, label_size=8.6)
        fig.text((left + i * (mw + gap) + 0.15) / W, (bottom + mh + 0.12) / H, title, fontsize=17, fontweight="bold", va="bottom")
    colorbar(fig, [0.55 / W, 1.32 / H, 4.2 / W, 0.14 / H], DIV, norm, [lo, MEIO, hi], lambda t: cv.br(t, 1 if t % 1 else 0, False) + "%",
             "percentual dos votos")
    fig.savefig(OUT / "1-mapas-1t-2t.png", facecolor=cv.SURFACE)
    plt.close(fig)


def mapa_diferenca(S, nat, geo):
    sobe = sorted((u for u, d in S.items() if d["dp"] > 0.05), key=lambda u: -S[u]["dp"])
    desce = sorted((u for u, d in S.items() if d["dp"] < -0.05), key=lambda u: S[u]["dp"])
    mw = 6.0
    mh = mw * MAP_RATIO
    bottom = 1.95
    fig, top = framed(12, bottom + mh + 0.25, lambda fig: cv.frame(fig, "Do 1º para o 2º turno: onde o percentual subiu e onde caiu",
                   "Diferença, em pontos percentuais, entre o 2º e o 1º turno no percentual de votos de eleitores com biometria que "
                   "não foram habilitados pela digital. Vermelho: subiu; azul: caiu. Variações de até 0,05 ponto contam como "
                   f"quase iguais ({', '.join(sorted(u for u, d in S.items() if abs(d['dp']) <= 0.05))}).",
                   [(f"{cv.br(nat['p2'] - nat['p1'], 2)} p.p.", f"no país ({cv.br(nat['p1'], 2, False)}% → {cv.br(nat['p2'], 2, False)}%)", None),
                    (str(len(sobe)), f"{uf_word(sobe)} com alta de mais de 0,05 p.p.; a maior em {sobe[0]} ({cv.br(S[sobe[0]]['dp'], 2)} p.p.)", None),
                    (str(len(desce)), f"{uf_word(desce)} com queda de mais de 0,05 p.p.; a maior em {desce[0]} ({cv.br(S[desce[0]]['dp'], 2)} p.p.)", None)]))
    W, H = fig.get_figwidth(), fig.get_figheight()
    lim = math.ceil(max(abs(d["dp"]) for d in S.values()) * 10) / 10
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
    ax = fig.add_axes([(W - mw - 1.1) / 2 / W, bottom / H, mw / W, mh / H])  # centrado com os rótulos do litoral (~1,1 pol. à direita)
    draw_map(ax, geo, {uf: d["dp"] for uf, d in S.items()}, DIV, norm, lambda v: cv.br(v, 2), label_size=10)
    ticks = [round(-lim + i * lim / 2, 2) for i in range(5)]
    colorbar(fig, [0.55 / W, 1.32 / H, 4.6 / W, 0.14 / H], DIV, norm, ticks, lambda t: cv.br(t, 2) if t else "0",
             "diferença em pontos percentuais (2º − 1º turno)")
    fig.savefig(OUT / "2-mapa-diferenca.png", facecolor=cv.SURFACE)
    plt.close(fig)


def barras(S, nat):
    order = sorted(S, key=lambda u: S[u]["p2"])
    fig = cv.figure(12, 16.5)
    top = cv.frame(fig, "Votos de eleitores com biometria não habilitados pela digital, por estado",
                   "Percentual dos votos no 1º turno (laranja) e no 2º turno (azul); ao lado das barras, os dois valores. À direita, o número desses votos "
                   f"em cada turno. Em nenhum estado a variação entre os turnos passou de {cv.br(math.ceil(max(abs(d['dp']) for d in S.values()) * 10) / 10, 1, False)} "
                   "ponto percentual, para cima ou para baixo.",
                   [(f"{cv.br(nat['p1'], 2, False)}%", f"no 1º turno ({cv.n(nat['b1'])} votos)", C1),
                    (f"{cv.br(nat['p2'], 2, False)}%", f"no 2º turno ({cv.n(nat['b2'])} votos)", C2),
                    (f"{max(S, key=lambda u: S[u]['p2'])} e {min(S, key=lambda u: S[u]['p2'])}",
                     f"maior e menor percentual no 2º turno ({cv.br(max(d['p2'] for d in S.values()), 1, False)}% e "
                     f"{cv.br(min(d['p2'] for d in S.values()), 1, False)}%)", None)])
    ax = cv.axes_below(fig, top - 0.3 / fig.get_figheight(), left=0.95, right=2.85, bottom=1.95)
    for i, u in enumerate(order):
        d = S[u]
        ax.barh(i + 0.2, d["p1"], height=0.37, color=C1, zorder=2)
        ax.barh(i - 0.2, d["p2"], height=0.37, color=C2, zorder=2)
        # um rótulo por linha, depois da barra mais longa: "1º → 2º turno"
        ax.text(max(d["p1"], d["p2"]) + 0.1, i, f"{cv.br(d['p1'], 2, False)} → {cv.br(d['p2'], 2, False)}%", va="center", fontsize=9.4,
                color=cv.INK)
        ax.text(1.03, i, cv.n(d["b1"]), transform=ax.get_yaxis_transform(), va="center", fontsize=11, color=cv.INK2)
        ax.text(1.2, i, cv.n(d["b2"]), transform=ax.get_yaxis_transform(), va="center", fontsize=11, fontweight="bold")
    ax.text(1.03, len(order) - 0.2, "1º turno", transform=ax.get_yaxis_transform(), fontsize=10.5, color=cv.INK2, va="bottom")
    ax.text(1.2, len(order) - 0.2, "2º turno", transform=ax.get_yaxis_transform(), fontsize=10.5, color=cv.INK2, fontweight="bold", va="bottom")
    ax.text(1.03, len(order) + 0.45, "votos", transform=ax.get_yaxis_transform(), fontsize=10.5, color=cv.INK2, va="bottom")
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.7, len(order) + 0.2)
    ax.set_xlim(0, max(max(d["p1"], d["p2"]) for d in S.values()) + 2.2)
    cv.xstyle(ax, "percentual dos votos")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(handles=[matplotlib.patches.Patch(color=C1, label="1º turno"), matplotlib.patches.Patch(color=C2, label="2º turno")],
              loc="lower right", frameon=True, facecolor=cv.SURFACE, edgecolor=cv.GRID, fontsize=11)
    fig.savefig(OUT / "3-barras-estados.png", facecolor=cv.SURFACE)
    plt.close(fig)


def uf_word(ufs):
    """Rótulo do número de UFs: o DF entra na conta, mas não é estado."""
    return f"UFs ({len(ufs) - 1} estados e o DF)" if "DF" in ufs else "estados"


def main():
    cobertura = json.load(open(OUT / "cobertura.json", encoding="utf-8"))
    cv.FONTE = FONTE.format(cobertura=cobertura["texto"])
    S, nat = load()
    geo = shapes()
    assert set(geo) == set(S), (set(geo) ^ set(S))
    mapas(S, nat, geo)
    mapa_diferenca(S, nat, geo)
    barras(S, nat)
    json.dump({"nat": nat, "uf": S}, open(OUT / "numeros.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in nat.items()})


if __name__ == "__main__":
    main()
