"""Biometria no 2º turno de 2026, a partir de secoes.jsonl (extract.py): ao longo do dia, tentativas de digital e por estado.
Gera b1-ao-longo-do-dia.png, b2-tentativas.png, b3-estados.png e biometria.json em DADOS/derivados/comparecimento_dia/ (a mesma
pasta de secoes.jsonl). Sem o exterior.

Tipos de habilitação (cada voto): "bio" = habilitado pela digital; "falhou" = tem biometria, a urna pediu a digital, ela não foi
reconhecida e o voto foi liberado depois que o mesário conferiu um dado do eleitor e pôs a própria digital; "semcad" = sem biometria
cadastrada (a urna não pede digital; o mesário confere o ano de nascimento). Hora: horário de Brasília da identificação do eleitor.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
sys.path.insert(0, str(HERE.parent / "abstencao"))
import caminhos  # noqa: E402
import charts_v2 as cv  # noqa: E402
import matplotlib  # noqa: E402
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

OUT = caminhos.saida("comparecimento_dia")
cv.KICKER = "Eleições 2026 · biometria no 2º turno"
cv.FONTE = ("Fonte: logs das urnas do 2º turno (TSE), seção por seção; inclui o log da urna original onde houve troca. Hora de Brasília em "
            "que o eleitor foi identificado. Sem o exterior.")
cv.MUTED = cv.INK2
FONTE_UF = ("Fonte: logs das urnas do 2º turno (TSE), seção por seção; inclui o log da urna original onde houve troca. "
            "Sem o exterior.")
C_SEMCAD, C_FALHOU = "#6250d6", "#e34948"  # violeta: sem biometria cadastrada; vermelho: digital não reconhecida
C_T1, C_T24 = "#1c5cab", "#86b6ef"  # reconhecida na 1ª tentativa; da 2ª à 4ª


def load():
    nat = {"votos": 0, "bio": 0, "falhou": 0, "semcad": 0, "ok": [0] * 9, "nok": [0] * 9, "secoes": 0, "max_de": defaultdict(int)}
    hora = defaultdict(lambda: {"bio": 0, "falhou": 0, "semcad": 0})
    uf = defaultdict(lambda: {"votos": 0, "bio": 0, "falhou": 0, "semcad": 0, "ok": [0] * 9})
    for line in open(OUT / "secoes.jsonl", encoding="utf-8"):
        s = json.loads(line)
        if s["uf"] == "ZZ" or not s["votos"]:
            continue
        nat["secoes"] += 1
        u = uf[s["uf"]]
        for k in ("bio", "falhou", "semcad"):
            nat[k] += s["tipo"][k]; u[k] += s["tipo"][k]
        nat["votos"] += s["votos"]; u["votos"] += s["votos"]
        for i, v in enumerate(s["tent_ok"]):
            nat["ok"][i] += v; u["ok"][i] += v
        for i, v in enumerate(s["tent_falhou"]):
            nat["nok"][i] += v
        for m, v in s["max_de"].items():
            nat["max_de"][m] += v
        for h, t in s["hora"].items():
            hh = min(max(int(h), 8), 17)  # 17 = 17h ou depois
            for k, v in t.items():
                hora[hh][k] += v
    return nat, dict(sorted(hora.items())), dict(uf)


def pct(a, b, d=1):
    return cv.br(100 * a / b, d, False) + "%"


def ao_longo_do_dia(nat, hora):
    hs = list(hora)
    tot = [sum(hora[h].values()) for h in hs]
    p_sem = [100 * hora[h]["semcad"] / t for h, t in zip(hs, tot)]
    p_fal = [100 * hora[h]["falhou"] / t for h, t in zip(hs, tot)]
    lab = [f"{h}h" if h < 17 else f"17h+\n({cv.n(round(sum(hora[h].values()) / 1000))} mil)" for h in hs]
    fig = cv.figure(12, 13.2)
    i_max = max(range(len(hs)), key=lambda i: p_sem[i] + p_fal[i])
    i_min = min(range(len(hs)), key=lambda i: p_sem[i] + p_fal[i])
    top = cv.frame(fig, "Votos sem a digital ao longo do dia",
                   "Em cima, quantos eleitores foram identificados em cada hora. Embaixo, a parte desses votos que foi liberada sem a digital, "
                   "separando quem não tem biometria cadastrada de quem tem, mas não foi reconhecido pela urna.",
                   [(pct(nat["semcad"] + nat["falhou"], nat["votos"], 2), "dos votos do 2º turno foram liberados sem a digital", None),
                    (pct(nat["semcad"], nat["votos"], 2), "dos votos: eleitores sem biometria cadastrada (a urna não pede a digital)", C_SEMCAD),
                    (pct(nat["falhou"], nat["votos"], 2), f"dos votos: eleitores com biometria não reconhecida "
                     f"({pct(nat['falhou'], nat['bio'] + nat['falhou'])} de quem teve a digital pedida)", C_FALHOU)])
    W, H = fig.get_figwidth(), fig.get_figheight()
    body = top * H - 1.95
    h1 = body * 0.36
    ax1 = fig.add_axes([1.25 / W, (1.95 + body - h1) / H, 1 - 1.8 / W, (h1 - 0.15) / H])
    ax2 = fig.add_axes([1.25 / W, 1.95 / H, 1 - 1.8 / W, (body - h1 - 0.55) / H])
    x = range(len(hs))
    ax1.bar(x, [t / 1e6 for t in tot], width=0.72, color="#cfcdc7", zorder=2)
    for i, t in enumerate(tot):
        ax1.text(i, t / 1e6, cv.br(t / 1e6, 1, False) if t >= 1e5 else f"{cv.n(round(t / 1e3))} mil", ha="center", va="bottom",
                 fontsize=10.5, color=cv.INK2)
    ax1.set_ylim(0, max(tot) / 1e6 * 1.22)
    ax1.set_xticks(list(x), [""] * len(hs))
    ax1.set_ylabel("milhões de eleitores", fontsize=11.5)
    ax1.spines[["top", "right", "left"]].set_visible(False)
    ax1.tick_params(axis="y", length=0)
    ax1.grid(axis="y", color=cv.GRID, linewidth=0.9)
    ax1.set_axisbelow(True)
    for vals, color, name in ((p_sem, C_SEMCAD, "sem biometria\ncadastrada"), (p_fal, C_FALHOU, "com biometria,\nnão reconhecida")):
        ax2.plot(list(x)[:-1], vals[:-1], color=color, linewidth=2.4, marker="o", markersize=8, markeredgecolor=cv.SURFACE, markeredgewidth=2, zorder=3)
        # 17h ou depois: poucos eleitores (cerca de 26 mil), ponto vazado e linha tracejada
        ax2.plot(list(x)[-2:], vals[-2:], color=color, linewidth=1.6, linestyle=(0, (3, 3)), zorder=2)
        ax2.plot([list(x)[-1]], [vals[-1]], marker="o", markersize=8, markerfacecolor=cv.SURFACE, markeredgecolor=color, markeredgewidth=2, zorder=3)
        for i in (0, len(hs) - 1):
            ax2.text(i, vals[i] + 0.35, cv.br(vals[i], 1, False) + "%", ha="center", va="bottom", fontsize=10.5, color=cv.INK)
        ax2.text(len(hs) - 0.55, vals[-1], name, va="center", ha="left", fontsize=11.5, color=cv.INK, fontweight="bold", linespacing=1.15)
    ax2.set_xticks(list(x), lab)
    ax2.set_xlim(-0.5, len(hs) - 0.5 + 1.9)
    ax1.set_xlim(ax2.get_xlim())  # barras alinhadas com as horas de baixo
    ax2.set_ylim(0, max(max(p_sem), max(p_fal)) * 1.3)
    ax2.set_ylabel("% dos votos da hora", fontsize=11.5)
    ax2.spines[["top", "right", "left"]].set_visible(False)
    ax2.tick_params(axis="y", length=0)
    ax2.grid(axis="y", color=cv.GRID, linewidth=0.9)
    ax2.set_axisbelow(True)
    ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.set_xlabel("hora de Brasília em que o eleitor foi identificado (17h+ = 17h ou depois)", fontsize=11.5, labelpad=10)
    fig.savefig(OUT / "b1-ao-longo-do-dia.png", facecolor=cv.SURFACE)
    plt.close(fig)
    return {"horas": lab, "total": tot, "p_semcad": p_sem, "p_falhou": p_fal, "i_max": i_max, "i_min": i_min}


def tentativas(nat, uf):
    pediu = sum(nat["ok"]) + sum(nat["nok"])
    t1 = nat["ok"][1]
    t24 = sum(nat["ok"][2:])
    nao = sum(nat["nok"])
    rows = {u: (d["ok"][1], sum(d["ok"][2:]), d["falhou"]) for u, d in uf.items()}
    order = sorted(rows, key=lambda u: rows[u][2] / sum(rows[u]), reverse=True)  # mais digitais não reconhecidas em cima
    cv.FONTE = FONTE_UF
    fig = cv.figure(12, 16.8)
    top = cv.frame(fig, "De quantas tentativas a digital precisou, por UF",
                   "Eleitores com biometria cadastrada: a urna pede a digital até 4 vezes. Quando ela não é reconhecida, o mesário confere um "
                   "dado do eleitor e a urna pede a digital do mesário para liberar o voto.",
                   [(pct(t1, pediu), "reconhecidos na 1ª tentativa", C_T1),
                    (pct(t24, pediu), "reconhecidos da 2ª à 4ª tentativa", C_T24),
                    (pct(nao, pediu), f"não reconhecidos ({cv.n(nao)} eleitores): voto liberado pelo mesário", C_FALHOU)])
    ax = cv.axes_below(fig, top, left=0.95, right=0.6)
    for i, u in enumerate(order):
        a, b, c = rows[u]
        tot = a + b + c
        left = 0
        for v, color, txt in ((a, C_T1, "#ffffff"), (b, C_T24, cv.INK), (c, C_FALHOU, "#ffffff")):
            w = 100 * v / tot
            ax.barh(i, w, left=left, height=0.72, color=color, edgecolor=cv.SURFACE, linewidth=2, zorder=2)
            if w >= 3.6:
                ax.text(left + w / 2, i, cv.br(w, 1, False), ha="center", va="center", fontsize=10 if w >= 4.5 else 9, color=txt,
                        fontweight="bold", zorder=3)
            left += w
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    cv.xstyle(ax, "% dos eleitores com biometria cadastrada que votaram (em cima, as UFs com mais digitais não reconhecidas)")
    ax.grid(axis="x", visible=False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.savefig(OUT / "b2-tentativas.png", facecolor=cv.SURFACE)
    plt.close(fig)
    return {"pediu": pediu, "t1": t1, "t24": t24, "nao": nao, "por_tentativa": nat["ok"], "max_de": dict(nat["max_de"]),
            "uf": {u: {"t1": a, "t24": b, "nao": c} for u, (a, b, c) in rows.items()}}


def estados(nat, uf):
    order = sorted(uf, key=lambda u: (uf[u]["semcad"] + uf[u]["falhou"]) / uf[u]["votos"], reverse=True)
    cv.FONTE = FONTE_UF
    fig = cv.figure(12, 16.8)
    sem = lambda u: 100 * (uf[u]["semcad"] + uf[u]["falhou"]) / uf[u]["votos"]
    top = cv.frame(fig, "Votos liberados sem a digital, por UF",
                   "Percentual dos votos do 2º turno em cada UF, somando quem não tem biometria cadastrada (violeta) e quem tem, mas não "
                   "foi reconhecido pela urna (vermelho).",
                   [(pct(nat["semcad"] + nat["falhou"], nat["votos"]), "no país, somando os dois grupos", None),
                    (f"{order[0]} e {order[-1]}", f"maior e menor percentual ({cv.br(sem(order[0]), 1, False)}% e {cv.br(sem(order[-1]), 1, False)}%)", None),
                    (cv.n(nat["semcad"] + nat["falhou"]), "votos liberados sem a digital no 2º turno", None)])
    ax = cv.axes_below(fig, top, left=0.95, right=1.6)
    for i, u in enumerate(order):
        a = 100 * uf[u]["semcad"] / uf[u]["votos"]
        b = 100 * uf[u]["falhou"] / uf[u]["votos"]
        ax.barh(i, a, height=0.72, color=C_SEMCAD, edgecolor=cv.SURFACE, linewidth=2, zorder=2)
        ax.barh(i, b, left=a, height=0.72, color=C_FALHOU, edgecolor=cv.SURFACE, linewidth=2, zorder=2)
        for left, w in ((0, a), (a, b)):
            if w >= 1.5:
                ax.text(left + w / 2, i, cv.br(w, 1, False), ha="center", va="center", fontsize=10 if w >= 2.2 else 8.5, color="#ffffff",
                        fontweight="bold", zorder=3)
        extra = f"  (violeta {cv.br(a, 1, False)})" if a < 1.5 else ""  # segmento estreito demais para o número
        ax.text(a + b + 0.25, i, cv.br(a + b, 1, False) + "%" + extra, va="center", fontsize=11, fontweight="bold", color=cv.INK)
    ax.set_yticks(range(len(order)), order, fontweight="bold")
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.invert_yaxis()
    ax.set_xlim(0, max(sem(u) for u in uf) * 1.12)
    cv.xstyle(ax, "% dos votos do 2º turno")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(handles=[matplotlib.patches.Patch(color=C_SEMCAD, label="sem biometria cadastrada"),
                       matplotlib.patches.Patch(color=C_FALHOU, label="com biometria, não reconhecida")],
              loc="lower right", frameon=True, facecolor=cv.SURFACE, edgecolor=cv.GRID, fontsize=11)
    fig.savefig(OUT / "b3-estados.png", facecolor=cv.SURFACE)
    plt.close(fig)
    return {u: {"votos": d["votos"], "semcad": d["semcad"], "falhou": d["falhou"]} for u, d in uf.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    nat, hora, uf = load()
    out = {"nat": {k: (dict(v) if isinstance(v, defaultdict) else v) for k, v in nat.items()},
           "hora": ao_longo_do_dia(nat, hora), "tentativas": tentativas(nat, uf), "uf": estados(nat, uf)}
    json.dump(out, open(OUT / "biometria.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = out["nat"]
    print({k: n[k] for k in ("secoes", "votos", "bio", "falhou", "semcad")}, "ok", n["ok"], "nok", n["nok"], "max_de", n["max_de"])
    print([(l, t, round(a, 2), round(b, 2)) for l, t, a, b in zip(out["hora"]["horas"], out["hora"]["total"], out["hora"]["p_semcad"], out["hora"]["p_falhou"])])


if __name__ == "__main__":
    main()
