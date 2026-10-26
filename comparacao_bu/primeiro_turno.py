"""1º turno (presidente) por seção para as seções da amostra, lido direto dos zips de dados abertos do TSE. Gera t1.csv.

Entradas em caminhos.TSE (baixadas de cdn.tse.jus.br, ver README):
  votacao_secao_2026_BR.zip (votacao_secao_2026_BR.csv) e detalhe_votacao_secao_2026.zip (detalhe_votacao_secao_2026_BRASIL.csv).
Amostra: dados_congelados/download.csv (padrão; a da comparação publicada) ou, com --amostra-nova, o download.csv de amostra.py.
Saída: caminhos.saida("comparacao_bu")/t1.csv. Uso: python primeiro_turno.py [--amostra-nova]
"""
import csv
import io
import sys
import zipfile
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
VOT = (caminhos.TSE / "votacao_secao_2026_BR.zip", "votacao_secao_2026_BR.csv")
DET = (caminhos.TSE / "detalhe_votacao_secao_2026.zip", "detalhe_votacao_secao_2026_BRASIL.csv")
AMOSTRA = (caminhos.saida("comparacao_bu") if "--amostra-nova" in sys.argv else HERE / "dados_congelados") / "download.csv"
T1 = caminhos.saida("comparacao_bu") / "t1.csv"
CHAVE = ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO")


def carregar(con, tabela, zip_csv, colunas, secoes):
    """Copia para a tabela (tudo texto) as linhas do 1º turno para presidente das seções da amostra, lendo o CSV
    (latin-1, ';') direto de dentro do zip, sem extrair. As consultas abaixo repetem o mesmo filtro e fazem as contas."""
    nomes = ["NR_TURNO", "CD_CARGO", *CHAVE, *colunas]
    con.execute(f"create table {tabela} ({', '.join(f'{c} varchar' for c in nomes)})")
    caminho, membro = zip_csv
    linhas = []
    with zipfile.ZipFile(caminho) as zf, zf.open(membro) as bruto:
        leitor = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1", newline=""), delimiter=";", quotechar='"')
        cab = next(leitor)
        cab[0] = cab[0].removeprefix("\xef\xbb\xbf")  # BOM UTF-8 lido como latin-1, se houver
        idx = [cab.index(c) for c in nomes]
        t, c, uf, mun, zona, secao = idx[:6]
        for r in leitor:
            if r[t] == "1" and r[c] == "1" and (r[uf], int(r[mun]), int(r[zona]), int(r[secao])) in secoes:
                linhas.append([r[j] for j in idx])
    con.executemany(f"insert into {tabela} values ({', '.join('?' * len(nomes))})", linhas)


con = duckdb.connect()
con.execute(f"""
create table k as select uf, cast(mun as int) mun, cast(zona as int) zona, cast(secao as int) secao
from read_csv('{AMOSTRA.as_posix()}', delim=';', header=true, all_varchar=true)""")
secoes = set(con.execute("select uf, mun, zona, secao from k").fetchall())
carregar(con, "vot_csv", VOT, ["NR_VOTAVEL", "QT_VOTOS"], secoes)
carregar(con, "det_csv", DET, ["QT_APTOS", "QT_COMPARECIMENTO", "QT_VOTOS_NOMINAIS", "QT_VOTOS_LEGENDA", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS"], secoes)
con.execute("""
create table v as
select SG_UF uf, cast(CD_MUNICIPIO as int) mun, cast(NR_ZONA as int) zona, cast(NR_SECAO as int) secao,
       cast(NR_VOTAVEL as int) nr, sum(cast(QT_VOTOS as int)) qt
from vot_csv
where NR_TURNO = '1' and CD_CARGO = '1'
  and (SG_UF, cast(CD_MUNICIPIO as int), cast(NR_ZONA as int), cast(NR_SECAO as int)) in (select (uf, mun, zona, secao) from k)
group by all""")
con.execute("""
create table d as
select SG_UF uf, cast(CD_MUNICIPIO as int) mun, cast(NR_ZONA as int) zona, cast(NR_SECAO as int) secao,
       sum(cast(QT_APTOS as int)) aptos, sum(cast(QT_COMPARECIMENTO as int)) comp, sum(cast(QT_VOTOS_NOMINAIS as int)) nominais,
       sum(cast(QT_VOTOS_LEGENDA as int)) legenda, sum(cast(QT_VOTOS_BRANCOS as int)) brancos, sum(cast(QT_VOTOS_NULOS as int)) nulos,
       count(*) n_linhas
from det_csv
where NR_TURNO = '1' and CD_CARGO = '1'
  and (SG_UF, cast(CD_MUNICIPIO as int), cast(NR_ZONA as int), cast(NR_SECAO as int)) in (select (uf, mun, zona, secao) from k)
group by all""")
print("votáveis distintos:", con.execute("select list(distinct nr order by nr) from v").fetchone()[0])
con.execute(f"""
copy (
select k.uf, k.mun, k.zona, k.secao,
       sum(case when v.nr = 13 then v.qt else 0 end) lula1,
       sum(case when v.nr = 22 then v.qt else 0 end) flavio1,
       sum(case when v.nr between 10 and 90 then v.qt else 0 end) validos1_vot,
       sum(case when v.nr = 95 then v.qt else 0 end) brancos1_vot,
       sum(case when v.nr >= 96 then v.qt else 0 end) nulos1_vot,
       count(v.nr) n_votaveis,
       any_value(d.aptos) aptos1, any_value(d.comp) comp1, any_value(d.nominais) + any_value(d.legenda) validos1_det,
       any_value(d.brancos) brancos1, any_value(d.nulos) nulos1, any_value(d.n_linhas) det_linhas
from k left join v using (uf, mun, zona, secao) left join d using (uf, mun, zona, secao)
group by all order by all
) to '{T1.as_posix()}' (delimiter ';', header true)""")
print(con.execute(f"""select count(*) secoes, count(*) filter (where n_votaveis = 0) sem_1t,
  count(*) filter (where det_linhas is null) sem_detalhe,
  count(*) filter (where validos1_vot <> validos1_det) validos_divergentes
  from read_csv('{T1.as_posix()}', delim=';')""").fetchall())
print("t1:", T1)
