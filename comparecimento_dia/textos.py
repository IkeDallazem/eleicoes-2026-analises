"""Resumos em texto das duas partes (comparecimento por seção; biometria ao longo do dia), gerados só a partir dos números:
comparecimento.json e biometria.json (comparecimento.py e biometria_dia.py), bio_1t_secoes.csv e bio_2t_secoes_v2.csv
(DADOS/derivados/biometria/) e os arquivos de resultado do TSE por município (DADOS/tse/ab/, baixados por abstencao/baixar.py).
Grava textos.json em DADOS/derivados/comparecimento_dia/ e mostra os textos na tela."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
import caminhos  # noqa: E402

OUT = caminhos.saida("comparecimento_dia")
C = json.load(open(OUT / "comparecimento.json", encoding="utf-8"))
B = json.load(open(OUT / "biometria.json", encoding="utf-8"))


def n(x):
    return f"{x:,}".replace(",", ".")


def p(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def s(x, d=1):
    return ("+" if x > 0 else "−" if x < 0 else "") + p(abs(x), d)


def lista(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


U = C["ufs"]
neg = sorted((u for u in U if U[u]["med"] < 0), key=lambda u: U[u]["med"])
pos = [u for u in U if U[u]["med"] > 0]
norte3 = sum(U[u]["queda20"] for u in ("AP", "AC", "RR"))
muns = [m[0] for m in C["mun_quedas"][:5]]


def ab(uf, e):
    return [i for i in json.load(open(caminhos.TSE / "ab" / f"{uf.lower()}-e00{e}-ab.json", encoding="utf-8"))["abr"]
            if i.get("tpabr") == "mun"]


def oficial(uf, cd):
    """Comparecimento oficial do município, 1º e 2º turno (eleitores que votaram e % do eleitorado), dos arquivos do TSE."""
    out = []
    for e in ("6257", "6258"):
        i = next(i for i in ab(uf, e) if i["cdabr"] == cd)
        out += [int(i["e"]["c"]), 100 * int(i["e"]["c"]) / int(i["e"]["te"])]
    return out  # [votaram 1º, % 1º, votaram 2º, % 2º]


UFS27 = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()
dif_pais = sum(int(i["e"]["c"]) for u in UFS27 for i in ab(u, "6258")) - sum(int(i["e"]["c"]) for u in UFS27 for i in ab(u, "6257"))
# eleitores aptos (te) no país, 2º menos 1º turno (voto em trânsito); nesta apuração, −149
dif_aptos = sum(int(i["e"]["te"]) for u in UFS27 for i in ab(u, "6258")) - sum(int(i["e"]["te"]) for u in UFS27 for i in ab(u, "6257"))


def quedas():
    """Eleitores que votaram, no 1º e no 2º turno, nas seções com queda de mais de 20 pontos (todas e só AP, AC e RR), e quantas
    dessas seções há em cada município."""
    import csv
    bio = caminhos.saida("biometria")
    s1 = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]): r for r in csv.DictReader(open(bio / "bio_1t_secoes.csv", encoding="utf-8"))
          if r["uf"] != "ZZ"}
    tot, norte, mun = [0, 0, 0], [0, 0, 0], {}
    for r in csv.DictReader(open(bio / "bio_2t_secoes_v2.csv", encoding="utf-8")):
        k = (r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"])
        if k in s1 and int(s1[k]["aptos"]):
            c1, c2 = int(s1[k]["comparecimento"]), int(r["votos"])
            if 100 * (c2 - c1) / int(s1[k]["aptos"]) < -20:
                for acc in (tot, norte) if k[0] in ("AP", "AC", "RR") else (tot,):
                    acc[0] += 1; acc[1] += c1; acc[2] += c2
                mun[k[:2]] = mun.get(k[:2], 0) + 1
    return tot, norte, mun


QT, QN, QM = quedas()
assert QT[0] == C["queda20"] and QN[0] == norte3, (QT, QN)
# Os dois municípios do topo de mun_quedas (mesma ordem de comparecimento.py: nº de seções com queda, depois UF e código), com o
# comparecimento oficial de cada um nos arquivos de resultado do TSE. Nesta apuração: Itaubal (AP-06041) e Porto Walter (AC-01066).
TOP2 = sorted(((q, mk) for mk, q in QM.items()), reverse=True)[:2]
assert [(q, f"({u})") for q, (u, _) in TOP2] == [(m[1], m[0][-4:]) for m in C["mun_quedas"][:2]], (TOP2, C["mun_quedas"][:2])
OF = [(muns[i].split(" (")[0], *oficial(u, cd)) for i, (_, (u, cd)) in enumerate(TOP2)]
METODO_C = ("Como contamos: o comparecimento do 1º turno está nos boletins de urna (dados abertos do TSE); o do 2º, nos logs das urnas, "
            "publicados seção por seção no site do TSE (incluímos o log da urna original onde a urna foi substituída). A variação é "
            f"calculada sobre os eleitores aptos do 1º turno, porque o log não traz esse número; no país, os aptos mudaram em {n(abs(dif_aptos))} "
            "eleitores entre os turnos. Tudo é público e qualquer pessoa pode conferir.")
t_comp = (
    "Comparecimento seção por seção, do 1º para o 2º turno.\n"
    f"Comparamos as {n(C['n'])} seções eleitorais do país (sem o exterior): quantos eleitores votaram em cada uma no 1º e no 2º turno.\n"
    f"Resultado: em {p(100 * C['subiu'] / C['n'], 0)}% das seções, mais eleitores votaram no 2º turno. Na seção típica (mediana), o "
    f"comparecimento subiu {p(C['med'])} ponto percentual, e metade das seções ficou entre {s(C['q1'])} e {s(C['q3'])} pontos. "
    f"{p(100 * C['faixa_m5_10'] / C['n'], 0)}% das seções ficaram entre −5 e +10 pontos.\n"
    f"Variações grandes foram raras: {n(C['abs20'])} seções ({p(100 * C['abs20'] / C['n'], 2)}%) mudaram mais de 20 pontos. "
    f"Dessas, {n(QT[0])} foram quedas: votaram nelas {n(QT[1])} eleitores no 1º turno e {n(QT[2])} no 2º, {n(QT[1] - QT[2])} a menos. "
    f"{n(QN[0])} dessas seções ({p(100 * QN[0] / QT[0], 0)}%) ficam no AP, no AC e em RR, os estados onde a abstenção mais subiu, com "
    f"{n(QN[1] - QN[2])} votos a menos. Para comparar: no país, o 2º turno teve {n(dif_pais)} votos a mais que o 1º (sem o exterior). "
    f"Os municípios com mais seções assim foram {lista(muns)}. O resultado oficial do TSE por município mostra a mesma queda: em "
    f"{OF[0][0]}, votaram {n(OF[0][1])} eleitores no 1º turno e {n(OF[0][3])} no 2º (de {p(OF[0][2])}% para {p(OF[0][4])}% do "
    f"eleitorado); em {OF[1][0]}, {n(OF[1][1])} e {n(OF[1][3])} (de {p(OF[1][2])}% para {p(OF[1][4])}%).\n"
    f"Por UF, a seção típica teve alta em {len(pos)} UFs e queda em {len(neg)} ({lista(neg)}).\n"
    f"{METODO_C}")

N = B["nat"]
T = B["tentativas"]
H = B["hora"]
UFB = B["uf"]
tot = lambda u: (UFB[u]["semcad"] + UFB[u]["falhou"]) / UFB[u]["votos"]
uf_max, uf_min = max(UFB, key=tot), min(UFB, key=tot)
nao_uf = {u: d["nao"] / (d["t1"] + d["t24"] + d["nao"]) for u, d in T["uf"].items()}
nao_max = max(nao_uf.values())
nao_top = sorted(u for u, v in nao_uf.items() if round(100 * v, 1) == round(100 * nao_max, 1))
nao_min_u = min(nao_uf, key=nao_uf.get)
i8, ilast = 0, H["horas"].index("16h")
t_bio = (
    "Biometria no 2º turno: quem votou sem a digital, a que horas e em que estado.\n"
    "Lemos os logs de todas as urnas do 2º turno (sem o exterior). Eles registram cada passo da votação: a urna pede a digital até 4 "
    "vezes; se ela não é reconhecida, o mesário confere um dado do eleitor e a urna pede a digital do mesário para liberar o voto. Quem "
    "não tem biometria cadastrada é liberado pelo mesário depois de conferir o ano de nascimento.\n"
    f"Resultado: {n(N['semcad'] + N['falhou'])} votos ({p(100 * (N['semcad'] + N['falhou']) / N['votos'], 2)}%) foram liberados sem a "
    f"digital: {n(N['semcad'])} de eleitores sem biometria cadastrada ({p(100 * N['semcad'] / N['votos'], 2)}%) e {n(N['falhou'])} de "
    f"eleitores com biometria que não foi reconhecida ({p(100 * N['falhou'] / N['votos'], 2)}%).\n"
    f"Tentativas: dos {p(T['pediu'] / 1e6)} milhões de eleitores com biometria que votaram, {p(100 * T['t1'] / T['pediu'])}% foram reconhecidos na 1ª "
    f"tentativa, {p(100 * T['t24'] / T['pediu'])}% da 2ª à 4ª e {p(100 * T['nao'] / T['pediu'])}% não foram reconhecidos.\n"
    f"Ao longo do dia: a parte de digitais não reconhecidas foi maior de manhã ({p(H['p_falhou'][i8])}% dos votos às 8h), ficou perto de "
    f"6% entre 11h e 15h e terminou em {p(H['p_falhou'][ilast])}% às 16h. A de eleitores sem biometria cadastrada subiu a cada hora: de "
    f"{p(H['p_semcad'][i8])}% às 8h para {p(H['p_semcad'][ilast])}% às 16h. Os logs não mostram o motivo dessas diferenças.\n"
    f"Por UF: {uf_max} tem a maior parte de votos sem a digital ({p(100 * tot(uf_max))}%), puxada por eleitores sem biometria "
    f"cadastrada ({p(100 * UFB[uf_max]['semcad'] / UFB[uf_max]['votos'])}% dos votos); pelos dados do TSE, o ES é o estado com menos "
    f"eleitores com biometria cadastrada. {uf_min} tem a menor parte ({p(100 * tot(uf_min))}%). Entre os eleitores com biometria, a parte "
    f"não reconhecida vai de {p(100 * nao_uf[nao_min_u])}% em {nao_min_u} a {p(100 * nao_max)}% " + " e ".join(f"no {u}" for u in nao_top) + ".\n"
    "Os logs são públicos, seção por seção, no site do TSE, e qualquer pessoa pode conferir.")

out = {"comparecimento": {"images": ["c1-histograma.png", "c2-estados.png"], "text": t_comp},
       "biometria": {"images": ["b1-ao-longo-do-dia.png", "b2-tentativas.png", "b3-estados.png"], "text": t_bio}}
json.dump(out, open(OUT / "textos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sys.stdout.reconfigure(encoding="utf-8")
for k, v in out.items():
    print(f"## {k}\n{v['text']}\n")
