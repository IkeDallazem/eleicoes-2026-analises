"""Gera os textos de resumo a partir dos números finais (nada digitado à mão): um resumo em 4 partes (mapas, variação entre
os turnos, estados, método) e um texto completo para cada imagem.
Lê numeros.json (bio_charts.py), cobertura.json (reconcile.py) e o CSV do 2º turno (para o total sem habilitação pela digital),
todos em DADOS/derivados/biometria, e grava textos.json na mesma pasta: {chave: {"image": imagem, "text": texto}}.
Uso: textos.py [bio_2t_secoes_v2.csv]"""
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

PASTA = caminhos.saida("biometria")
num = json.load(open(PASTA / "numeros.json", encoding="utf-8"))
S, nat = num["uf"], num["nat"]
cob = json.load(open(PASTA / "cobertura.json", encoding="utf-8"))
csv2 = sys.argv[1] if len(sys.argv) > 1 else "bio_2t_secoes_v2.csv"
v = sb = cb = 0
for r in csv.DictReader(open(PASTA / csv2, encoding="utf-8")):
    if r["uf"] != "ZZ":
        v += int(r["votos"]); sb += int(r["sem_bio_total"]); cb += int(r["com_biometria"])
nobio = v - cb  # votos de eleitores sem biometria cadastrada (a urna não pediu a digital)
assert nobio + nat["b2"] == sb
assert v == nat["v2"], (v, nat["v2"])


def n(x):
    return f"{x:,}".replace(",", ".")


def p(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def s(x, d=2):
    return ("+" if x > 0 else "−" if x < 0 else "") + p(abs(x), d)


def lista(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


up = sorted((u for u, d in S.items() if d["dp"] > 0.05), key=lambda u: -S[u]["dp"])
down = sorted((u for u, d in S.items() if d["dp"] < -0.05), key=lambda u: S[u]["dp"])
same = sorted(u for u, d in S.items() if abs(d["dp"]) <= 0.05)
r1 = sorted(S, key=lambda u: -S[u]["p1"])
r2 = sorted(S, key=lambda u: -S[u]["p2"])
top = r2[:3]
bot = sorted(r2[-3:], key=lambda u: S[u]["p2"])
assert set(r1[:3]) == set(top) and set(r1[-3:]) == set(bot), "topo/base mudaram entre os turnos: reescrever a frase"
by_b2 = sorted(S, key=lambda u: -S[u]["b2"])
maxabs = max(abs(d["dp"]) for d in S.values())
lim = (int(maxabs * 10) + 1) / 10
n_down = f"{len(down) - 1} estados e no DF" if "DF" in down else f"{len(down)} estados"
dp = nat["p2"] - nat["p1"]
fmt_dp = lambda u: f"{u} ({s(S[u]['dp'])})"

DEF = ("eleitores que têm biometria cadastrada, mas não foram habilitados pela digital. Isso acontece quando a digital não é "
       "reconhecida: o mesário confere os dados do eleitor e libera o voto")
RES = f"{n(nat['b1'])} votos no 1º turno ({p(nat['p1'])}% dos votos no Brasil, sem o exterior) e {n(nat['b2'])} no 2º ({p(nat['p2'])}%)"
CAVEAT = ("Não entram aqui os eleitores sem biometria cadastrada, que também votam sem a digital "
          f"(no 2º turno, outros {n(nobio)} votos).")
mi = lambda x: f"{x / 1e6:.1f}".replace(".", ",") + " milhões"
MUDOU = (f"O percentual subiu em {len(up)} estados, com as maiores altas em {lista([fmt_dp(u) for u in up[:3]])}. "
         f"Caiu em {n_down}, com as maiores quedas em {lista([fmt_dp(u) for u in down[:3]])}. "
         f"Em {lista(same)}, ficou praticamente igual (variação de até 0,05 ponto).")
FONTE = ("Como contamos: no 1º turno, o número está nos boletins de urna (planilha dos dados abertos do TSE). No 2º, essa planilha "
         "ainda não saiu, então lemos os logs das urnas, publicados seção por seção no site do TSE, e contamos o mesmo caso. Testamos o "
         "método no 1º turno: em 300 seções sorteadas, o log bateu com o boletim em todas. No 2º, comparamos com o boletim de 4.000 "
         "seções, baixado do mesmo site: bateu em todas. Tudo é público e qualquer pessoa pode conferir.")

# t1 a t4: o resumo em partes, na ordem; s1 a s3: um texto completo (definição, ressalva e método) para cada imagem
t = {}
t["t1"] = ("Biometria no 1º e no 2º turno, estado por estado.\n"
           f"Usamos duas fontes públicas do TSE (os boletins de urna do 1º turno e os logs das urnas do 2º) para contar os votos de {DEF}.\n"
           f"Resultado: {RES}. No país, o percentual ficou praticamente estável ({s(dp)} ponto).\n"
           f"Nos mapas, o percentual de cada estado, com a mesma escala de cor. Os maiores, nos dois turnos, ficam em {lista(top)}; "
           f"os menores, em {lista(bot)}.")
t["t2"] = ("O que mudou do 1º para o 2º turno, em pontos percentuais.\n"
           f"{MUDOU}\n"
           f"Nenhum estado variou mais que {p(lim, 1)} ponto, e a ordem quase não mudou: quem tinha os maiores percentuais no 1º turno "
           "continuou no topo no 2º.")
t["t3"] = ("Estado por estado, com os dois turnos lado a lado.\n"
           f"No 2º turno, o maior percentual foi no {top[0]} ({p(S[top[0]]['p2'], 1)}%) e o menor em {bot[0]} ({p(S[bot[0]]['p2'], 1)}%). "
           f"Em número de votos, os maiores são {by_b2[0]} ({n(S[by_b2[0]]['b2'])}), {by_b2[1]} ({n(S[by_b2[1]]['b2'])}) "
           f"e {by_b2[2]} ({n(S[by_b2[2]]['b2'])}), os três maiores eleitorados do país.\n"
           "À direita do gráfico, o número desses votos em cada estado, nos dois turnos.")
t["t4"] = (f"{FONTE}\n"
           "Em seções em que a urna foi substituída durante a votação, lemos também o log da urna original, que vem dentro do arquivo da "
           f"urna nova. Assim, os logs somam {n(cob['logs'])} votos, contra {n(cob['oficial'])} no resultado oficial (sem o exterior). "
           f"Faltam {n(cob['falta'])}; a maior parte vem de duas seções sem log no site do TSE.\n"
           f"Atenção: esses números ({mi(nat['b1'])} no 1º turno e {mi(nat['b2'])} no 2º) não são o total de votos sem biometria. Quem não "
           "tem biometria cadastrada também vota sem a digital e fica fora desta conta. Somando os dois grupos, "
           f"{n(sb)} eleitores votaram no 2º turno sem ser habilitados pela digital ({p(100 * sb / v, 1)}% dos votos). A planilha de "
           "boletins do 1º turno não traz esse total, só o número de eleitores com biometria que não foram habilitados por ela; por isso "
           "a comparação entre os turnos usa só esse grupo.")
t["s1"] = ("Biometria no 1º e no 2º turno, estado por estado.\n"
           f"Contamos os votos de {DEF}. {CAVEAT}\n"
           f"Resultado: {RES}. No país, o percentual ficou praticamente estável ({s(dp)} ponto).\n"
           f"Os maiores percentuais, nos dois turnos, ficam em {lista(top)}; os menores, em {lista(bot)}.\n"
           f"{FONTE}")
t["s2"] = ("Biometria: o que mudou do 1º para o 2º turno, estado por estado.\n"
           f"O mapa mostra quanto variou, em pontos percentuais, a fatia dos votos de {DEF}. {CAVEAT}\n"
           f"No país, o percentual foi de {p(nat['p1'])}% para {p(nat['p2'])}% dos votos ({s(dp)} ponto), sem o exterior.\n"
           f"{MUDOU}\n"
           f"Nenhum estado variou mais que {p(lim, 1)} ponto.\n"
           f"{FONTE}")
t["s3"] = ("Biometria por estado, no 1º e no 2º turno.\n"
           f"O gráfico mostra o percentual dos votos de {DEF}. {CAVEAT}\n"
           f"No país: {RES}.\n"
           f"No 2º turno, o maior percentual foi no {top[0]} ({p(S[top[0]]['p2'], 1)}%) e o menor em {bot[0]} ({p(S[bot[0]]['p2'], 1)}%). "
           f"Em nenhum estado a variação entre os turnos passou de {p(lim, 1)} ponto.\n"
           f"{FONTE}")
IMG = {"t1": "1-mapas-1t-2t.png", "t2": "2-mapa-diferenca.png", "t3": "3-barras-estados.png", "t4": None,
       "s1": "1-mapas-1t-2t.png", "s2": "2-mapa-diferenca.png", "s3": "3-barras-estados.png"}
NOME = {"t1": "resumo_1_mapas", "t2": "resumo_2_variacao", "t3": "resumo_3_estados", "t4": "resumo_4_metodo",
        "s1": "texto_mapas", "s2": "texto_variacao", "s3": "texto_estados"}
out = {NOME[k]: {"image": IMG[k], "text": v} for k, v in t.items()}
json.dump(out, open(PASTA / "textos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in t.items():
    print(f"## {NOME[k]}\n{v}\n")
