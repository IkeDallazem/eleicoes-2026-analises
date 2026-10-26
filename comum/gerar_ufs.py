"""Gera comum/ufs.json: contornos simplificados das 27 UFs usados nos mapas (biometria/bio_charts.py).

Fonte: brazil-states.geojson do projeto codeforamerica/click_that_hood (licença MIT), baixado de
https://raw.githubusercontent.com/codeforamerica/click_that_hood/main/public/data/brazil-states.geojson
Simplificação: ST_Simplify(geom, 0.0012) da extensão spatial do DuckDB, uma geometria por UF, em ordem de sigla (DF no fim).
Saída: lista de {"sigla", "type", "coordinates"}.

Uso: python gerar_ufs.py   (precisa de duckdb; a extensão spatial é instalada na primeira execução)
"""
import json
import sys
import urllib.request
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import caminhos  # noqa: E402

URL = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/main/public/data/brazil-states.geojson"
FONTE = caminhos.DADOS / "brazil-states.geojson"
SAIDA = Path(__file__).resolve().parent / "ufs.json"


def main():
    if not FONTE.exists():
        FONTE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": caminhos.USER_AGENT})
        FONTE.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    linhas = con.execute("SELECT sigla, ST_AsGeoJSON(ST_Simplify(geom, 0.0012)) FROM ST_Read(?) ORDER BY sigla",
                         [str(FONTE)]).fetchall()
    # DF por último: é desenhado por cima de GO, que o cerca.
    linhas = [r for r in linhas if r[0] != "DF"] + [r for r in linhas if r[0] == "DF"]
    ufs = [{"sigla": sigla, **json.loads(geo)} for sigla, geo in linhas]
    SAIDA.write_text(json.dumps(ufs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(ufs), "UFs ->", SAIDA)


if __name__ == "__main__":
    main()
