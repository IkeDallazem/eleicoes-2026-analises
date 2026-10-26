# Comparecimento e biometria seção por seção (2º turno de 2026)

Duas medidas tiradas dos logs das urnas do 2º turno (25/10/2026), seção por seção, sem o exterior:

1. **Comparecimento do 1º para o 2º turno.** Para cada seção eleitoral, a variação
   `(votos no 2º turno − comparecimento no 1º turno) / eleitores aptos no 1º turno`, em pontos percentuais.
   O 1º turno vem dos boletins de urna (dados abertos do TSE: `QT_APTOS`, `QT_COMPARECIMENTO`); o 2º turno, dos votos
   contados nos logs das urnas (uma linha `O voto do eleitor foi computado` por voto). Resultado: distribuição nacional,
   distribuição por UF e municípios com mais seções com variação acima de 20 pontos.
2. **Biometria ao longo do dia.** Cada voto do 2º turno é classificado pelo modo como o eleitor foi habilitado:
   - `bio`: habilitado pela digital;
   - `falhou`: tem biometria cadastrada, a urna pediu a digital (`Solicita digital. Tentativa N de M`), ela não foi
     reconhecida e o voto foi liberado pelo mesário;
   - `semcad`: sem biometria cadastrada (a urna não pede a digital).

   Os votos são agrupados pela hora de Brasília em que o eleitor foi identificado, por UF e pelo número de tentativas
   de digital até o reconhecimento.

## Fontes (TSE)

| Dado | Endereço | Baixado por |
|---|---|---|
| Logs das urnas do 2º turno (`.jez`, por seção) | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/{uf}/{uf}-p003221-cs.json` e `.../arquivo-urna/3221/dados/{uf}/{mun}/{zona}/{secao}/...` | `logs_urna/coletar_logs.py` |
| Log completo das seções com urna substituída | mesmo endereço, `.jez` completo (com o log da urna original aninhado) | `biometria/refetch.py` |
| Boletins de urna do 1º turno (dados abertos) | `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_{UF}_051020261403.zip` | `biometria/bio_1t.py` |
| Resultado por município, 1º e 2º turno (`ab`) | `https://resultados.tse.jus.br/oficial/ele2026/{6257,6258}/dados/{uf}/{uf}-e00{6257,6258}-ab.json` | `abstencao/baixar.py` |
| Votação por município e zona 2026 (nomes dos municípios) | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip` | `abstencao/baixar.py` |

## Pastas de dados

Os scripts não gravam nada ao lado do código. Tudo fica em `DADOS`, que por padrão é `dados/` na raiz do repositório;
para usar outra pasta, defina a variável de ambiente `ELEICOES_DADOS` (veja `comum/caminhos.py`):

```
set ELEICOES_DADOS=D:\eleicoes          (Windows, cmd)
export ELEICOES_DADOS=/dados/eleicoes   (Linux/macOS)
```

Entradas lidas por esta análise:

- `DADOS/urna_logs/sections.sqlite` e `DADOS/urna_logs/day/<UF>/*.log.gz` (de `logs_urna/`);
- `DADOS/jez_contingencia/<UF>/<mun>-<zona>-<secao>/` (de `biometria/refetch.py`);
- `DADOS/derivados/biometria/bio_1t_secoes.csv`, `bio_2t_secoes_v2.csv` e `cobertura.json` (de `biometria/`);
- `DADOS/tse/ab/<uf>-e006257-ab.json`, `<uf>-e006258-ab.json` e `DADOS/tse/detalhe_votacao_munzona_2026.zip`
  (de `abstencao/baixar.py`).

Saídas: `DADOS/derivados/comparecimento_dia/`.

## Ordem de execução

Comandos a partir da raiz do repositório. Requisitos: Python 3.12 ou mais novo e `matplotlib` (os resultados de referência
foram gerados com matplotlib 3.11.2); o resto é biblioteca padrão.

**1. Arquivos do TSE** (resultado por município e zip de votação por município e zona):

```
python abstencao/baixar.py --so ab zips
```

**2. Logs das urnas do 2º turno** (coleta longa; ritmo padrão conservador, veja `logs_urna/README.md`):

```
python logs_urna/coletar_logs.py --once   # repita até o status não mostrar seções em "fila" nem "erro"
```

**3. Etapas de `biometria/`** de que esta análise depende (argumentos e detalhes em `biometria/README.md`):

- `bio_1t.py` → `bio_1t_secoes.csv` (boletins de urna do 1º turno, por seção);
- `bio_2t.py` → `bio_2t_secoes.csv` (votos e biometria do 2º turno, pelos logs);
- `lista_contingencia.py` → `refetch_list.json` (seções com urna substituída);
- `refetch.py` → `DADOS/jez_contingencia/` (`.jez` completos dessas seções);
- `bio_nested.py` → `bio_2t_secoes_v2.csv` (as mesmas seções recontadas com o log da urna original);
- `reconcile.py` → `cobertura.json` (votos oficiais do 2º turno × votos contados nos logs; usado no rodapé dos gráficos).

**4. Esta análise:**

```
python comparecimento_dia/nomes.py            # nomes.json: nomes dos municípios
python comparecimento_dia/extract.py          # secoes.jsonl: uma linha por seção (lê todos os logs)
python comparecimento_dia/comparecimento.py   # c1-histograma.png, c2-estados.png, comparecimento.json
python comparecimento_dia/biometria_dia.py    # b1-ao-longo-do-dia.png, b2-tentativas.png, b3-estados.png, biometria.json
python comparecimento_dia/textos.py           # textos.json: resumos em texto dos dois conjuntos de números
```

`extract.py` aceita `--ufs` (UFs separadas por vírgula) para um teste parcial e `--workers` (processos em paralelo,
padrão 8). Com `--ufs` a saída é `secoes_<UFs>.jsonl` (por exemplo `secoes_AC-AP-RR.jsonl`) e o `secoes.jsonl` completo
não é tocado; as linhas saem na mesma ordem e com o mesmo conteúdo das linhas dessas UFs no arquivo completo.

```
python comparecimento_dia/extract.py --ufs RR,AP,AC --workers 4
```

`comparecimento.py` só depende das etapas 1, 3 e de `nomes.py`; `biometria_dia.py` só depende de `extract.py`;
`textos.py` precisa das saídas dos dois e das etapas 1 e 3.

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `nomes.json` | `{"UF-CDMUN": NM_MUNICIPIO}` (5.757 municípios, 186 deles no exterior), na ordem de UF e nome |
| `secoes.jsonl` | uma linha por seção: votos, número de urnas com votos, votos por tipo (`bio`/`falhou`/`semcad`), votos por hora de Brasília e tipo, tentativas de digital até o reconhecimento (`tent_ok`) e nos não reconhecidos (`tent_falhou`), máximo de tentativas anunciado (`max_de`) e timeouts |
| `comparecimento.json` | totais, quartis, contagens (`queda20`, `alta20`, `abs20`...), estatísticas por UF e os municípios com mais seções com queda (`mun_quedas`) e alta (`mun_altas`) |
| `c1-histograma.png` | histograma da variação por seção (barras de 1 ponto, de −20 a +20; as pontas acumulam o resto) |
| `c2-estados.png` | caixa (quartis), mediana e faixa de 5% a 95% por UF |
| `biometria.json` | totais nacionais por tipo, série por hora, tentativas e totais por UF |
| `b1-ao-longo-do-dia.png` | eleitores identificados por hora e % de votos sem a digital por hora |
| `b2-tentativas.png` | por UF: reconhecidos na 1ª tentativa, da 2ª à 4ª e não reconhecidos |
| `b3-estados.png` | por UF: % dos votos sem a digital (sem biometria cadastrada + não reconhecidos) |
| `textos.json` | resumos em texto (`comparecimento`, `biometria`), cada um com a lista das imagens correspondentes |

## Resultados de referência

Com as entradas usadas nos resultados publicados:

- 497.895 seções pareadas (1º turno no boletim de urna e 2º turno no log, com aptos > 0);
- mediana da variação: +1,91 ponto; metade das seções entre +0,30 e +3,46; 76% das seções com mais votos no 2º turno;
- 313 seções com variação acima de 20 pontos em módulo: 304 quedas e 9 altas;
- 127.854.123 votos contados nos logs do 2º turno, contra 127.854.631 no resultado oficial (`cobertura.json`: faltam 508);
- 15.884.223 votos (12,42%) liberados sem a digital: 7.251.808 sem biometria cadastrada e 8.632.415 com biometria não
  reconhecida.

## Tamanho e tempo

| Item | Tamanho | Tempo aproximado |
|---|---|---|
| `DADOS/urna_logs/day/` | 499.176 arquivos, 32,7 GB (só as linhas do dia da votação, em gzip) | mais de 30 h de coleta no ritmo padrão (ver `logs_urna/`) |
| `DADOS/urna_logs/sections.sqlite` | 255 MB | |
| `DADOS/jez_contingencia/` | 1.971 seções, ~397 MB de `.jez` (~407 MB com os `aux.json`) | |
| `bio_1t_secoes.csv` / `bio_2t_secoes_v2.csv` | 22,8 MB / 18,8 MB | |
| `DADOS/tse/ab/` | 54 arquivos usados, ~9,5 MB | |
| `secoes.jsonl` | 286 MB, 499.176 linhas | `extract.py`: ~10 min com 8 processos |
| demais saídas | ~1,5 MB | `nomes.py`, `comparecimento.py`, `biometria_dia.py`, `textos.py`: segundos cada |

## Ressalvas

- **Aptos do 1º turno.** O log não traz o número de eleitores aptos da seção; a variação usa os aptos do 1º turno. Os
  aptos mudam pouco entre os turnos (voto em trânsito): no país, a soma de `te` nos arquivos `ab` das 27 UFs cai 149
  eleitores do 1º para o 2º turno (calculado em `textos.py`).
- **Cobertura dos logs.** Os votos contados nos logs ficam 508 abaixo do comparecimento oficial do 2º turno (99,9996%);
  o número vem de `biometria/reconcile.py` (`cobertura.json`) e é citado no rodapé dos gráficos de comparecimento.
- **Seções com urna substituída.** O log publicado da urna de contingência traz aninhado o log da urna original. Nessas
  seções, `extract.py` lê o `logd.dat` e os `.jez` aninhados, agrupa as linhas pela urna que as gravou (3ª coluna),
  conta cada linha repetida uma vez só e descarta logs que se identificam como de outra seção (mesma regra de
  `biometria/bio_nested.py`). Uma seção só é lida assim se a pasta dela em `DADOS/jez_contingencia/` tiver o marcador
  `ok`; sem essa pasta, `extract.py` usa só o log do dia em `DADOS/urna_logs/day/` e os votos dessas seções ficam menores.
- **Hora.** O relógio da urna está na hora local. A hora de Brasília usa uma tabela fixa de fusos (AC +2 h; AM, RO, RR, MT
  e MS +1 h; Fernando de Noronha, PE-30015, −1 h) e, fora Noronha, também a hora da primeira habilitação: se ela ocorre antes de
  6,9 h (ou 7,9 h) no relógio da urna, o deslocamento é de pelo menos 2 h (ou 1 h). A hora considerada é a da digitação do
  identificador do eleitor. No gráfico, horas anteriores às 8h entram em 8h, e 17h ou depois entram em "17h+".
- **Sem o exterior.** Seções da UF `ZZ` ficam de fora de todas as contas.
- **Retrato no tempo.** Os arquivos de resultado (`ab`) e os logs são os publicados na época da coleta; o TSE pode
  republicar arquivos, e aí os números podem mudar um pouco. Seções cujo log não estava publicado na coleta não entram.
- **Frases fixas nos resumos.** Três trechos de `textos.py` não são calculados a partir das entradas: "ficou perto de 6%
  entre 11h e 15h" (leitura da série `p_falhou` de `biometria.json`), "os estados onde a abstenção mais subiu" (AP, AC e
  RR, conforme a análise em `abstencao/`) e "o ES é o estado com menos eleitores com biometria cadastrada" (estatística
  do eleitorado do TSE, fora das entradas desta pasta).
- **Os logs não explicam causas.** As diferenças por hora e por UF são descritivas.
- **Fonte das imagens.** O estilo dos gráficos vem de `abstencao/charts_v2.py`, que usa a fonte Segoe UI com
  DejaVu Sans como alternativa. Fora do Windows (sem Segoe UI) as imagens saem com a fonte alternativa: os números são
  os mesmos, mas os PNG não ficam idênticos byte a byte aos de referência.
