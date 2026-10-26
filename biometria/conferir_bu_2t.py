"""Confere a contagem do 2º turno feita nos logs com o boletim de urna (BU) da mesma seção.

Além dos votos, o BU binário traz o comparecimento da seção e três contadores de habilitação: eleitores sem biometria
cadastrada, habilitados pela biometria e com biometria cadastrada mas não habilitados pela digital. Para cada BU
disponível, compara com bio_2t_secoes_v2.csv:
  comparecimento do BU                 = votos
  habilitados pela biometria (BU)      = habilitados_bio
  biometria sem habilitação (BU)       = biom_sem_hab
  sem biometria cadastrada (BU)        = votos − com_biometria

Os BUs vêm de logs_urna/coletar_logs.py --bu (DADOS/urna_logs/bu/<UF>/) e de comparacao_bu/baixar_bu.py (DADOS/bu_2t/<UF>/).
Saída: DADOS/derivados/biometria/conferencia_bu_2t.json.  Uso: python conferir_bu_2t.py
"""
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "comum"))
sys.path.insert(0, str(RAIZ / "comparacao_bu"))
import caminhos  # noqa: E402
import bu_parser  # noqa: E402

PASTA = caminhos.saida("biometria")
PASTAS_BU = [caminhos.LOGS / "bu", caminhos.DADOS / "bu_2t"]


def contadores(data):
    """(municipio, zona, secao, comparecimento, [sem biometria, habilitados pela biometria, biometria sem habilitação])."""
    bu = bu_parser.unwrap(bu_parser.decode(data))
    parsed = bu_parser.parse_bu(data)
    comparecimento = next(c.int() for c in bu.children if c.is_int)
    hab = next(c for c in bu.children if c.cls == 2 and c.tag == 1 and c.constructed)
    return parsed.municipio, parsed.zona, parsed.secao, comparecimento, [c.int() for c in hab.children if c.is_int]


def main():
    log = {(r["uf"], int(r["cd_municipio"]), int(r["nr_zona"]), int(r["nr_secao"])): r
           for r in csv.DictReader(open(PASTA / "bio_2t_secoes_v2.csv", encoding="utf-8"))}
    bus, erros = {}, []
    for pasta in PASTAS_BU:
        for f in sorted(pasta.glob("*/*.dat")):
            if f.parent.name == "ZZ":  # exterior: fora da análise (o BU de lá não traz os contadores de biometria)
                continue
            try:
                mun, zona, secao, comp, hab = contadores(f.read_bytes())
            except (ValueError, StopIteration) as e:
                erros.append(f"{f.parent.name}/{f.name}: {e}")
                continue
            bus[(f.parent.name, mun, zona, secao)] = (comp, hab)
    n = iguais = 0
    sem_log, diferentes = [], []
    for k, (comp, hab) in sorted(bus.items()):
        r = log.get(k)
        if r is None:
            sem_log.append(k)
            continue
        n += 1
        votos, com_bio = int(r["votos"]), int(r["com_biometria"])
        esperado = [votos - com_bio, int(r["habilitados_bio"]), int(r["biom_sem_hab"])]
        if comp == votos and hab == esperado:
            iguais += 1
        else:
            diferentes.append({"secao": "-".join(map(str, k)), "bu": [comp, hab], "log": [votos, esperado]})
    out = {"bus_lidos": len(bus), "comparados": n, "iguais": iguais, "diferentes": diferentes,
           "sem_linha_no_log": ["-".join(map(str, k)) for k in sem_log], "erros_de_leitura": erros}
    json.dump(out, open(PASTA / "conferencia_bu_2t.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"BUs lidos: {len(bus)}; comparados com o log: {n}; iguais: {iguais}; diferentes: {len(diferentes)}; "
          f"sem linha no log: {len(sem_log)}; erros de leitura: {len(erros)}")


if __name__ == "__main__":
    main()
