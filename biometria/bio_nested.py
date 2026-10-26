"""Reconta, com o log da urna original (aninhado no .jez), as seções do 2º turno com urna substituída, e grava
bio_2t_secoes_v2.csv (bio_2t_secoes.csv com essas seções trocadas pela recontagem).

Regra: as linhas de todos os logs (logd.dat principal + .jez aninhados) são agrupadas pela urna que as gravou (3ª coluna);
linhas idênticas repetidas entre arquivos contam uma vez; o log de urna que se identifica como de outra seção é descartado;
cada urna é contada com bio_parse.count_lines e os votos das urnas da seção são somados.
Lê DADOS/derivados/biometria/bio_2t_secoes.csv e os .jez baixados por refetch.py; grava bio_2t_secoes_v2.csv e
nested_report.json (antes/depois por seção, para conferência) na mesma pasta.
Uso: bio_nested.py [pasta_dos_jez]   (padrão: DADOS/jez_contingencia)"""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "comum"))
from bio_parse import count_lines  # noqa: E402
import caminhos  # noqa: E402

DAY = "25/10/2026"


def logs_in(data):
    """[(rótulo, linhas do dia)] do .jez: o logd.dat e cada .jez aninhado (recursivo)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            low = name.lower()
            if low.endswith(".dat") and "logd" in low:
                text = archive.read(name).decode("latin-1")
                out.append((name, [l for l in text.splitlines() if l.startswith(DAY)]))
            elif low.endswith(".jez"):
                try:
                    out.extend((f"{name}:{n}", ls) for n, ls in logs_in(archive.read(name)))
                except zipfile.BadZipFile:
                    pass
    return out


def other_section(lines, secao):
    """True se o log da urna se identifica como de outra seção (há pacote de seção que traz o log da urna de outra seção)."""
    named = {l.split("	")[4].split(":", 1)[1].strip() for l in lines
             if len(l.split("	")) > 4 and l.split("	")[4].startswith("Seção Eleitoral:")}
    named.discard("0000")  # urna de contingência antes de ser atribuída
    return bool(named) and secao not in named


def count_section(folder):
    secao = folder.name.split("-")[2]
    logs = []
    for jez in sorted(folder.glob("*.jez")):
        logs.extend(logs_in(jez.read_bytes()))
    urnas = {}
    for label, lines in logs:
        per = {}
        for line in lines:
            r = line.split("\t", 3)
            per.setdefault(r[2].strip() if len(r) > 3 else "", []).append(line)
        for uid, ls in per.items():
            urnas.setdefault(uid, []).append(ls)
    seen = set()
    total = None
    for uid, chunks in urnas.items():
        merged = []
        for ls in sorted(chunks, key=lambda c: c[0][:19] if c else ""):
            for line in ls:
                if line not in seen:
                    seen.add(line)
                    merged.append(line)
        if other_section(merged, secao):
            continue
        c = count_lines(merged, DAY)
        total = c if total is None else {k: total[k] + c[k] for k in c}
    return total, len(logs), len(urnas)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else caminhos.DADOS / "jez_contingencia"
    pasta = caminhos.saida("biometria")
    fields = ["uf", "cd_municipio", "nr_zona", "nr_secao", "votos", "com_biometria", "biom_sem_hab", "habilitados_bio", "sem_bio_total"]
    rows = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]): r for r in csv.DictReader(open(pasta / "bio_2t_secoes.csv", encoding="utf-8"))}
    report = []
    for folder in sorted(p for p in root.glob("*/*") if (p / "ok").exists()):
        uf = folder.parent.name
        mun, zona, secao = folder.name.split("-")
        key = (uf, mun, zona, secao)
        new, n_logs, n_urnas = count_section(folder)
        old = rows[key]
        if new is None and n_logs:
            new = {k: 0 for k in fields[4:]}  # só logs de outra seção
        if new is None:
            report.append({"key": key, "n_logs": n_logs, "n_urnas": n_urnas, "erro": "sem linhas"})
            continue
        report.append({"key": key, "n_logs": n_logs, "n_urnas": n_urnas, "votos_antes": int(old["votos"]), "votos_depois": new["votos"],
                       "bsh_antes": int(old["biom_sem_hab"]), "bsh_depois": new["biom_sem_hab"]})
        rows[key] = {"uf": uf, "cd_municipio": mun, "nr_zona": zona, "nr_secao": secao, **new}
    with open(pasta / "bio_2t_secoes_v2.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows.values())
    json.dump(report, open(pasta / "nested_report.json", "w", encoding="utf-8"), ensure_ascii=False)
    ok = [r for r in report if "erro" not in r]
    print("seções relidas", len(report), "sem linhas", len(report) - len(ok))
    print("votos +", sum(r["votos_depois"] - r["votos_antes"] for r in ok), "biom_sem_hab +", sum(r["bsh_depois"] - r["bsh_antes"] for r in ok))
    print("menos votos que antes (não deveria):", sum(1 for r in ok if r["votos_depois"] < r["votos_antes"]))
    print("seções com 2+ urnas:", sum(1 for r in ok if r["n_urnas"] >= 2))


if __name__ == "__main__":
    main()
