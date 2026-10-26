"""Resumo em texto do modelo histórico, gerado de resultados.json, previsoes.csv, municipios.csv e exibidos.json (o que os
gráficos mostram), todos em DADOS/derivados/modelo_historico/. Grava texto.json (resumo + as imagens a que ele se refere) e
texto.txt (só o resumo), e mostra o resumo.
Convenção: toda diferença escrita é a subtração dos números arredondados que aparecem (49,5 → 51,8 = +2,3)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

OUT = caminhos.saida("modelo_historico")
R = json.load(open(OUT / "resultados.json", encoding="utf-8"))
T = R["teste"]
EXIB = json.load(open(OUT / "exibidos.json", encoding="utf-8"))
ANOS = ["2002", "2006", "2010", "2014", "2018", "2022"]
G1 = ["pt", "adv", "outros", "bn", "abs"]
P = pd.read_csv(OUT / "previsoes.csv", dtype={"CD_MUNICIPIO": str})
M = pd.read_csv(OUT / "municipios.csv", dtype={"CD_MUNICIPIO": str})


def r(x, d=1):
    return round(x, d)


def p(x, d=1):
    return f"{abs(x):.{d}f}".replace(".", ",")


def s(x, d=1):
    return ("+" if x > 0 else "−" if x < 0 else "") + p(x, d)


def br(n):
    return f"{n:,}".replace(",", ".")


def lista(us):
    return ", ".join(us[:-1]) + " e " + us[-1]


# comparecimento: os percentuais arredondados de cada turno e a diferença deles (iguais à imagem 1)
niv = EXIB["comparecimento"]["niveis"]
var = EXIB["comparecimento"]["variacao"]
assert all(var[a] == r(niv[a][1] - niv[a][0]) for a in var)
caiu = [a for a in ANOS if var[a] < 0]
subiu = [a for a in ANOS if var[a] > 0]
assert subiu == ["2022"] and var["2026"] > max(var[a] for a in ANOS)
assert niv["2022"][0] == niv["2026"][0]
lula_c, flavio_c = r(EXIB["comparecimento"]["lula"]), r(EXIB["comparecimento"]["flavio"])

# voto: estimado e resultado arredondados; a diferença é a dos arredondados (igual às imagens 2 e 3)
est = {a: r(100 * T[a]["prev_a"]["nacional"]) for a in ANOS + ["2026"]}
res = {a: r(100 * T[a]["real"]) for a in ANOS + ["2026"]}
gap = {a: r(res[a] - est[a]) for a in est}
assert gap == EXIB["gaps"]
lo, hi = min(gap[a] for a in ANOS), max(gap[a] for a in ANOS)
a_lo, a_hi = min(ANOS, key=gap.get), max(ANOS, key=gap.get)
faixa = (r(est["2026"] + lo), r(est["2026"] + hi))
maiores = sum(abs(gap[a]) > abs(gap["2026"]) for a in ANOS)

# 1º turno de 2026 e conta simples só com Lula e Flávio
x26 = M[M["ano"] == 2026]
val1 = x26["pt_1"].sum() + x26["adv_1"].sum() + x26["outros_1"].sum()
lula1, flavio1 = r(100 * x26["pt_1"].sum() / val1), r(100 * x26["adv_1"].sum() / val1)
dois = r(100 * x26["pt_1"].sum() / (x26["pt_1"].sum() + x26["adv_1"].sum()))
outros = {a: r(100 * g["outros_1"].sum() / (g["pt_1"] + g["adv_1"] + g["outros_1"]).sum()) for a, g in M.groupby(M["ano"].astype(str))}
assert outros["2026"] == min(outros.values())

# regra média usada em 2026 (estimada com os seis anos anteriores)
c26 = R["coef"]["2026"]
o_pt, o_adv = round(100 * c26["pt"]["outros"]), round(100 * c26["adv"]["outros"])

# robustez: total do país somando os votos estimados, em vez de pesar cada município pelos válidos do 2º turno
soma = {}
for a, x in P.groupby(P["ano"].astype(str)):
    c = R["coef"][a]
    X = x[[f"s_{g}" for g in G1]].to_numpy() * x[["QT_APTOS_1"]].to_numpy()
    pt, adv = X @ np.array([c["pt"][g] for g in G1]), X @ np.array([c["adv"][g] for g in G1])
    soma[a] = r(res[a] - r(100 * pt.sum() / (pt.sum() + adv.sum())))
assert soma["2026"] == gap["2026"]
muda = max(abs(r(soma[a] - gap[a])) for a in ANOS)

# municípios
p26 = P[P["ano"] == 2026]
n_mun = len(p26)
n_acima = int((p26["y"] > p26["prev_a"]).sum())
geo = {a: r(100 * T[a]["prev_a"]["geo_mae_municipio"]) for a in ANOS + ["2026"]}
assert geo["2026"] < min(geo[a] for a in ANOS)

# anos em que a nuvem ficou quase toda de um lado da linha (≥ 95% dos municípios)
um_lado = {a: max((g["y"] > g["prev_a"]).mean(), (g["y"] < g["prev_a"]).mean())
           for a, g in P.dropna(subset=["y", "prev_a"]).groupby(P["ano"].astype(str))}
lado_unico = [a for a in ANOS if um_lado[a] >= 0.95]
assert lado_unico == ["2006", "2022"]

# 1º turno: parte dos votantes que escolheu outros candidatos, branco ou nulo
ob = {a: 100 * (g["outros_1"].sum() + g["branco_1"].sum() + g["nulo_1"].sum()) / g["QT_COMPARECIMENTO_1"].sum()
      for a, g in M.groupby(M["ano"].astype(str))}
assert round(ob["2022"]) == round(ob["2026"]) == 12
ob_min, ob_max = min(ob[a] for a in ANOS if a != "2022"), max(ob[a] for a in ANOS if a != "2022")

# UFs: distância média de cada UF ao país (cada UF conta igual)
geo_uf = {a: r(100 * T[a]["prev_a"]["geo_mae_uf"]) for a in ANOS + ["2026"]}

# UFs (ordem pelo valor sem arredondar)
uf_bruto = {u: -100 * e for u, e in T["2026"]["prev_a"]["erro_uf"].items()}
acima_uf = {u: r(v) for u, v in uf_bruto.items()}
assert len(acima_uf) == 27 and min(acima_uf.values()) > 0
ordem = sorted(uf_bruto, key=uf_bruto.get)
baixo4, alto4 = ordem[:4], ordem[::-1][:4]

texto = (
    "Terminamos de analisar os dados de todos os 2º turnos para presidente de 2002 a 2026, município por município. O que "
    f"encontramos: em 2026, o comparecimento subiu do 1º para o 2º turno, de {p(niv['2026'][0])}% para {p(niv['2026'][1])}% dos "
    f"eleitores ({s(var['2026'])} ponto percentual), o maior aumento desde 2002; em {len(caiu)} dos 6 segundos turnos anteriores, "
    f"ele caiu. Já o voto de Lula ficou {p(gap['2026'])} pontos acima do estimado a partir do 1º turno ({p(est['2026'])}% estimado; "
    f"{p(res['2026'])}% no resultado), uma diferença menor que a de {maiores} dos 6 anos anteriores.\n"
    f"Comparecimento (imagem 1): de 2002 a 2022, ele só subiu do 1º para o 2º turno em {subiu[0]} ({s(var[subiu[0]])} ponto). Em "
    f"2026, o aumento foi praticamente igual nos municípios onde Lula venceu o 1º turno ({s(lula_c)}) e onde Flávio Bolsonaro venceu "
    f"({s(flavio_c)}). Pelo 1º turno, o ano mais parecido com 2026 é 2022: nos dois, {p(niv['2026'][0])}% dos eleitores foram "
    f"votar e só cerca de {ob['2026']:.0f}% dos votantes escolheram outros candidatos, branco ou nulo (de {ob_min:.0f}% a "
    f"{ob_max:.0f}% nos demais anos). Os dados não mostram o motivo do aumento.\n"
    f"Votos (imagem 2): no 1º turno, Flávio teve {p(flavio1)}% dos votos válidos e Lula, {p(lula1)}%. Com esse 1º turno, a regra "
    f"dos anos anteriores dava {p(est['2026'])}% dos votos válidos para Lula no 2º turno: praticamente um empate. Ele teve "
    f"{p(res['2026'])}%: {p(gap['2026'])} pontos acima. De 2002 a 2022, o candidato do PT terminou entre {p(lo)} pontos abaixo "
    f"({a_lo}) e {p(hi)} acima ({a_hi}) do estimado; se 2026 tivesse o desvio de qualquer um desses anos, Lula terminaria entre "
    f"{p(faixa[0])}% e {p(faixa[1])}%. Numa conta ainda mais simples, contando só os votos de Lula e Flávio no 1º turno, Lula tinha "
    f"{p(dois)}% da soma dos dois e foi a {p(res['2026'])}% no 2º turno ({s(r(res['2026'] - dois))} pontos).\n"
    "Como estimamos os votos: não é pesquisa nem previsão feita antes da eleição. A estimativa de cada município foi calculada "
    "depois, só com os votos do 1º turno, para servir de régua. De um turno para o outro, quase todo eleitor de um finalista vota "
    "nele de novo, e quem votou nos outros candidatos se divide. Pelos totais de cada município nos 2º turnos de 2002 a 2022 (o PT "
    f"esteve em todos), a regra estima que, em média, uns {o_pt}% dos eleitores dos outros candidatos vão para o PT, uns {o_adv}% "
    "para o adversário, e o resto não vota em nenhum dos dois (o voto é secreto: é uma estimativa a partir dos totais, não um "
    f"levantamento de quem votou em quem). Aplicamos a regra ao 1º turno de cada um dos {br(n_mun)} municípios e juntamos os "
    "resultados para o país. Para saber quanto a régua costuma errar, testamos a regra em cada ano anterior, sempre calculada sem "
    "os dados do próprio ano.\n"
    "Município a município (imagem 3): cada bolinha é um município; sobre a linha, ele votou exatamente como estimado. Em 2026, a "
    f"nuvem ficou quase inteira logo acima da linha: Lula ficou acima do estimado em {br(n_acima)} dos {br(n_mun)} municípios (em "
    f"{lista(lado_unico)}, a nuvem também ficou quase toda de um lado da linha). Somando a cada estimativa esses {p(gap['2026'])} "
    f"pontos do país todo, cada município ficou, em média, a {p(geo['2026'])} ponto do resultado (pesando pelos votos), a menor "
    f"distância desde 2002 (de {p(min(geo[a] for a in ANOS))} a "
    f"{p(max(geo[a] for a in ANOS))} entre 2002 e 2022). Ou seja, os municípios se moveram de forma mais parecida entre si do que em "
    "qualquer 2º turno desde 2002. Isso acompanha o padrão da série: em geral, quanto menos votos foram para outros candidatos no 1º "
    f"turno, menor essa distância. Em 2026, só {p(outros['2026'])}% dos votos válidos do 1º turno foram para outros candidatos, a "
    f"menor fatia desde 2002 (em 2022, {p(outros['2022'])}%).\n"
    f"Por estado (imagem 4): Lula ficou acima do estimado nas 27 UFs, de {p(acima_uf[ordem[0]])} ponto em {ordem[0]} a "
    f"{p(acima_uf[ordem[-1]])} pontos em {ordem[-1]}. Onde mais: {lista(alto4)}; onde menos: {lista(baixo4)}. Em média, cada UF "
    f"ficou a {p(geo_uf['2026'])} ponto dos {s(gap['2026'])} do país (cada UF contando igual), contra {p(min(geo_uf[a] for a in ANOS))} "
    f"a {p(max(geo_uf[a] for a in ANOS))} entre 2002 e 2022.\n"
    "O que isso não diz: não é auditoria. A comparação mede o quanto o resultado se afastou do padrão dos anos anteriores; não "
    "explica o motivo e não serve para dizer se houve ou não irregularidade.\n"
    "Detalhe técnico: a regra dos votos é uma regressão sem constante, com cada município em cada eleição como uma observação e os "
    "mesmos coeficientes para o país todo: ela explica a fração do eleitorado que votou em cada finalista no 2º turno a partir das "
    "frações do 1º (PT, adversário, outros, brancos e nulos, abstenção), com coeficientes não negativos e cada município pesando na "
    "proporção do seu eleitorado. "
    "No total do país e de cada UF, cada município pesa pelos votos válidos que teve no 2º turno; somando os votos estimados, 2026 "
    f"fica igual ({s(soma['2026'])}) e os desvios de 2002 a 2022 mudam no máximo {p(muda)} ponto. Também tentamos estimar o "
    "comparecimento esperado com gradient boosting (1º turno, UF, região e tamanho de cada município), mas o resultado para 2026 "
    "dependia de incluir 2022, o único 2º turno anterior com aumento (com 2022, a variação esperada era de −0,1 ponto; sem 2022, de "
    "−2,1); por isso não usamos "
    "essa estimativa. Todos os números são sem o exterior. Os dados são públicos, no site do TSE, e qualquer pessoa pode refazer a "
    "conta.")
json.dump({"texto": texto, "imagens": ["1-comparecimento.png", "2-setas.png", "3-municipios.png", "4-mapa-2026.png"]},
          open(OUT / "texto.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(OUT / "texto.txt", "w", encoding="utf-8") as f:
    f.write(texto + "\n")
sys.stdout.reconfigure(encoding="utf-8")
print("soma:", soma, "| muda", muda)
print(texto)
