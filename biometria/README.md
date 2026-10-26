# Biometria no 1º e no 2º turno de 2026, por estado

Esta análise conta, em cada estado, os votos de eleitores que **têm biometria cadastrada, mas não foram habilitados pela
digital**: a urna pediu a digital, ela não foi reconhecida e o mesário liberou o voto depois de conferir os dados do
eleitor. É o campo `QT_ELEI_BIOM_SEM_HABILITACAO` do boletim de urna do TSE ("quantidade de eleitoras e eleitores com
biometria, mas que não foram habilitados por meio dela"). O exterior (UF `ZZ`) fica de fora em todos os números.

- **1º turno (04/10/2026):** o campo vem pronto nos boletins de urna dos dados abertos do TSE, uma linha por seção.
- **2º turno (25/10/2026):** a planilha de boletins ainda não estava publicada; a mesma quantidade é contada no log de
  cada urna (`logd.dat`), publicado seção por seção no site de resultados do TSE.

O resultado é o percentual desses votos sobre os votos de cada estado nos dois turnos, a diferença entre os turnos em
pontos percentuais, e um resumo em texto gerado a partir dos números.

## Método

**Contagem no log** (`bio_parse.py`, função `count_lines`). Só entram as linhas do dia da votação. Cada sessão de eleitor
começa em `Aguardando digitação do identificador` e termina em `O voto do eleitor foi computado` (um voto). Na sessão:

- `Solicita digital. Tentativa N de M` indica que o eleitor tem biometria cadastrada (a urna só pede a digital a quem tem);
- `Tipo de habilitação do eleitor [biométrica]` indica que ele foi habilitado pela digital.

Por seção: `votos`, `com_biometria` (votos em que a digital foi pedida), `habilitados_bio`,
`biom_sem_hab = com_biometria − min(com_biometria, habilitados_bio)` (a medida do boletim) e
`sem_bio_total = votos − habilitados_bio` (todos os votos liberados sem a digital, inclusive de quem não tem biometria).

**Urnas substituídas.** A coleta dos logs (`logs_urna/coletar_logs.py`) guarda só o `logd.dat` principal de cada seção.
Quando a urna foi trocada durante a votação, esse é o log da urna de contingência, e o log da urna original fica
aninhado dentro do `.jez`. `lista_contingencia.py` encontra essas seções (linha `Log interno da urna de contingência`
no log do dia, mais as seções com 0 votos), `refetch.py` baixa de novo o `.jez` completo delas e `bio_nested.py`
reconta cada seção com todos os logs: as linhas são agrupadas pela urna que as gravou (3ª coluna), linhas repetidas
entre arquivos contam uma vez, o log de urna que se identifica como de outra seção é descartado e as urnas da seção são
somadas. Em 2026 foram 1.971 seções; a recontagem acrescentou 156.853 votos e 16.851 votos sem habilitação pela digital.

**Cobertura** (`reconcile.py`). Os votos contados nos logs são comparados, município a município, com o comparecimento
oficial do 2º turno (`e.c` nos arquivos de abrangência do TSE): faltam 508 dos 127.854.631 votos, 454 deles em duas
seções sem log publicado (Niterói-RJ, zona 0144, seção 0007; Guarulhos-SP, zona 0395, seção 0298).

**Por estado** (`build_uf.py`, `bio_charts.py`). 1º turno: soma de `QT_COMPARECIMENTO` e `QT_ELEI_BIOM_SEM_HABILITACAO`
dos boletins. 2º turno: soma de `votos` e `biom_sem_hab` de `bio_2t_secoes_v2.csv`. Percentual = 100 × votos sem
habilitação pela digital ÷ votos. Nos mapas de nível, a escala de cor é divergente e centrada em 6,7% (o percentual do
país nos dois turnos, arredondado); no mapa da diferença, centrada em 0. Variação de até 0,05 ponto conta como
"praticamente igual".

**Conferência do método no 1º turno** (`bio_sample_1t.py`, opcional). Sorteia 300 seções do Brasil (semente 20261004)
da tabela `sections` de `sections.sqlite`, baixa o log do 1º turno de cada uma e aplica a mesma contagem. Em 299 das 300
o log deu exatamente o comparecimento e o `QT_ELEI_BIOM_SEM_HABILITACAO` do boletim. A outra (DF, município 97012,
zona 0014, seção 0068) é de urna substituída: o script lê só o log principal (167 votos, 7); contando também o log
aninhado da urna original, dá 297 votos e 21, iguais ao boletim. A comparação seção a seção é uma junção simples de
`bio_sample_1t.csv` com `bio_1t_secoes.csv` pelas colunas `uf, cd_municipio, nr_zona, nr_secao`. O sorteio depende da ordem das
linhas em `sections.sqlite`, que pode mudar de uma coleta para outra; as 300 seções sorteadas e o resultado da contagem
estão em `dados_congelados/amostra_1t.csv`.

## Números (2026)

| | 1º turno | 2º turno |
|---|---|---|
| Votos (Brasil, sem o exterior) | 124.934.069 | 127.854.123 |
| Votos com biometria e sem habilitação pela digital | 8.342.249 (6,68%) | 8.632.415 (6,75%) |

Variação no país: +0,07 ponto. Maior percentual no 2º turno: PI (9,0%); menor: RR (4,1%). O percentual subiu em 15
estados e caiu em 7 estados e no DF; nenhuma UF variou mais que 0,6 ponto (a maior variação foi em MS, −0,57). No 2º
turno, outros 7.251.808 votos foram de eleitores sem biometria cadastrada; somando os dois grupos, 15.884.223 votos
(12,4%) foram liberados sem a digital.

## Fontes

| Dado | Endereço | Script |
|---|---|---|
| Boletins de urna do 1º turno (dados abertos, "Resultados - 2026 - Boletim de Urna") | `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_{UF}_051020261403.zip` (27 UFs + ZZ) | `bio_1t.py` |
| Logs das urnas do 2º turno | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/{uf}/{mun}/{zona}/{secao}/...` (`aux.json` e o `.jez` do log) | `logs_urna/coletar_logs.py` |
| `.jez` completo das seções com urna substituída | os mesmos endereços | `refetch.py` |
| Comparecimento oficial do 2º turno por município | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/{uf}/{uf}-e006258-ab.json` | `abstencao/baixar.py` |
| Logs do 1º turno (amostra de conferência) | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/{uf}/{mun}/{zona}/{secao}/...` | `bio_sample_1t.py` |
| Contornos simplificados dos estados | `comum/ufs.json` (no repositório) | — |

O sufixo `051020261403` dos zips de boletins é a data de geração do arquivo pelo TSE; se o TSE republicar o pacote, o
nome muda e a constante `URL` de `bio_1t.py` precisa ser ajustada (veja o nome atual na página do conjunto de dados em
`dadosabertos.tse.jus.br`).

## Pastas de dados

Todos os scripts usam `comum/caminhos.py`. Os dados ficam em `dados/` na raiz do repositório ou na pasta indicada pela
variável de ambiente `ELEICOES_DADOS`:

```powershell
$env:ELEICOES_DADOS = "D:\eleicoes-dados"      # PowerShell
```
```bash
export ELEICOES_DADOS=/mnt/dados/eleicoes      # bash
```

- entradas: `DADOS/urna_logs/` (`sections.sqlite` e `day/`, só leitura), `DADOS/tse/ab/`, `DADOS/jez_contingencia/`;
- zips temporários do 1º turno: `DADOS/tse/` (cada um é apagado depois de lido);
- saídas: `DADOS/derivados/biometria/`.

## Como rodar

Python 3.12 ou mais novo. Tudo usa só a biblioteca padrão, exceto `bio_charts.py` (matplotlib). `bio_1t.py` usa o
`curl` da linha de comando (já vem no Windows 10/11, no macOS e na maioria das distribuições Linux). Comandos a partir
da raiz do repositório:

```bash
# 1. Logs do 2º turno (coleta longa; veja logs_urna/README.md)
python logs_urna/coletar_logs.py --once   # repita até o status não mostrar seções em "fila" nem "erro"

# 2. Comparecimento oficial por município (arquivos de abrangência)
python abstencao/baixar.py --so ab

# 3. 1º turno: boletins de urna -> bio_1t_secoes.csv (retomável: pula os estados que já estão no CSV)
python biometria/bio_1t.py

# 4. 2º turno: contagem nos logs -> bio_2t_secoes.csv
python biometria/bio_2t.py

# 5. Seções com urna substituída -> refetch_list.json (depois do passo 4, para incluir as seções com 0 votos)
python biometria/lista_contingencia.py

# 6. .jez completo dessas seções -> DADOS/jez_contingencia/ (retomável)
python biometria/refetch.py

# 7. Recontagem com o log da urna original -> bio_2t_secoes_v2.csv e nested_report.json
python biometria/bio_nested.py

# 8. Cobertura (logs × comparecimento oficial) -> cobertura.json (e refetch_list2.json, diagnóstico)
python biometria/reconcile.py bio_2t_secoes_v2.csv

# 9. Totais por estado -> bio_uf.json
python biometria/build_uf.py bio_2t_secoes_v2.csv

# 10. Gráficos -> 1-mapas-1t-2t.png, 2-mapa-diferenca.png, 3-barras-estados.png e numeros.json
uv run --no-project --with matplotlib python biometria/bio_charts.py      # ou: pip install matplotlib; python ...

# 11. Resumo em texto -> textos.json
python biometria/textos.py bio_2t_secoes_v2.csv

# 12. Conferência com o boletim de urna do 2º turno -> conferencia_bu_2t.json
#     (os 4.000 BUs da conferência publicada estão listados em dados_congelados/bus_conferidos.csv; ~4.000 requisições,
#     cerca de 40 min no intervalo padrão de 0,6 s)
python comparacao_bu/baixar_bu.py biometria/dados_congelados/bus_conferidos.csv
python biometria/conferir_bu_2t.py

# Opcional: conferência do método no 1º turno -> bio_sample_1t.csv (~600 requisições)
python biometria/bio_sample_1t.py
```

`refetch.py` e `bio_nested.py` aceitam caminhos como argumentos (`refetch.py [lista.json] [pasta_saida]`,
`bio_nested.py [pasta_dos_jez]`); sem eles, usam os padrões acima. `build_uf.py bio_2t_secoes_v2.csv --check` compara
com o `bio_uf.json` existente em vez de gravar.

**Teste rápido em poucos estados.** `bio_2t.py` e `lista_contingencia.py` aceitam `--ufs` (e `--saida`). Com `--ufs` e
sem `--saida`, gravam `bio_2t_secoes_<UFs>.csv` e `refetch_list_<UFs>.json`, sem tocar nos arquivos completos:

```bash
python biometria/bio_2t.py --ufs RR AP AC
python biometria/lista_contingencia.py --ufs RR AP AC
```

Em 2026, esses três estados têm 5.703 seções com log e 12 seções com urna substituída.

**Conferir os resultados.** `sha256_resultados.txt` tem o SHA-256 das tabelas e JSONs principais gerados a partir dos dados de
2026 (as imagens dependem da fonte e da versão do matplotlib e não entram):

```bash
cd "${ELEICOES_DADOS:-dados}/derivados/biometria" && sha256sum -c /caminho/do/repositorio/biometria/sha256_resultados.txt
```

### Ritmo das requisições

Todas as requisições usam o User-Agent de `comum/caminhos.py`.

- `bio_1t.py`: 28 arquivos do `cdn.tse.jus.br`, um de cada vez; o `curl` repete até 3 vezes, com espera crescente, em
  falha temporária (inclusive HTTP 429).
- `refetch.py`: até 3 requisições/s no total (4 em paralelo), com até 6 tentativas e espera crescente em erro.
- `bio_sample_1t.py`: no máximo 3 requisições/s, uma de cada vez, com nova tentativa e espera crescente em erro.
- coleta dos logs: veja `logs_urna/README.md` (padrão conservador, com redução automática a cada HTTP 429).

Aumentar esses ritmos (constante `RATE` de `refetch.py`, pausas de `bio_sample_1t.py`, opções do coletor) fica por conta
e risco de quem roda: o servidor do TSE responde HTTP 429 e pode bloquear acessos em excesso.

## Saídas (DADOS/derivados/biometria/)

| Arquivo | Script | Conteúdo |
|---|---|---|
| `bio_1t_secoes.csv` | `bio_1t.py` | uma linha por seção do 1º turno: `uf, cd_municipio, nr_zona, nr_secao, aptos, comparecimento, biom_sem_hab, tipo_urna, agregadas` (499.206 seções, 1.309 no exterior; 22,8 MB) |
| `bio_2t_secoes.csv` | `bio_2t.py` | uma linha por seção com log no 2º turno: `uf, cd_municipio, nr_zona, nr_secao, votos, com_biometria, biom_sem_hab, habilitados_bio, sem_bio_total` (499.176 seções; 18,8 MB) |
| `refetch_list.json` | `lista_contingencia.py` | `[[uf, mun, zona, secao], ...]` das seções com urna substituída (1.971; 65 KB) |
| `bio_2t_secoes_v2.csv` | `bio_nested.py` | `bio_2t_secoes.csv` com essas seções recontadas (é a tabela usada daqui em diante) |
| `nested_report.json` | `bio_nested.py` | antes/depois de cada seção recontada (votos, biom_sem_hab, número de logs e de urnas) |
| `cobertura.json` | `reconcile.py` | `oficial`, `logs`, `falta`, `pct` e o texto usado no rodapé dos gráficos |
| `refetch_list2.json` | `reconcile.py` | diagnóstico: seções com log possivelmente incompleto (log com menos de 85% do comparecimento do 1º turno, em município com falta); em 2026, 1 seção, não usada nos resultados |
| `bio_uf.json` | `build_uf.py` | `{UF: [votos 1T, biom_sem_hab 1T, votos 2T, biom_sem_hab 2T]}` |
| `1-mapas-1t-2t.png` | `bio_charts.py` | mapas do percentual por estado no 1º e no 2º turno, mesma escala |
| `2-mapa-diferenca.png` | `bio_charts.py` | mapa da diferença 2º − 1º turno, em pontos percentuais |
| `3-barras-estados.png` | `bio_charts.py` | barras por estado com os dois turnos e o número de votos |
| `numeros.json` | `bio_charts.py` | totais do país (`nat`) e por estado (`uf`: votos, votos sem habilitação pela digital, percentuais e diferença) |
| `textos.json` | `textos.py` | `{chave: {"image", "text"}}`: `resumo_1_mapas` a `resumo_4_metodo` (o resumo em partes, na ordem) e `texto_mapas`, `texto_variacao`, `texto_estados` (um texto completo para cada imagem) |
| `conferencia_bu_2t.json` | `conferir_bu_2t.py` | contagem dos logs × boletim de urna do 2º turno: BUs lidos, comparados, iguais e a lista das diferenças (em 2026, 4.000 de 4.000 iguais) |
| `bio_sample_1t.csv` | `bio_sample_1t.py` | opcional: contagem no log do 1º turno das 300 seções sorteadas |

Outras análises leem daqui: `comparecimento_dia/` usa `bio_1t_secoes.csv`, `bio_2t_secoes_v2.csv` e `cobertura.json`;
`comparecimento_dia/extract.py` importa `bio_nested.py`, e `modelo_historico/graficos.py` importa `bio_charts.py`
(mapa do Brasil e barra de cor).

## Tamanhos e tempos

| Etapa | Dados | Tempo aproximado |
|---|---|---|
| Coleta dos logs do 2º turno | ~90 GB baixados; 32,7 GB de logs do dia guardados (499.176 arquivos `.log.gz`) e `sections.sqlite` de 255 MB | mais de 30 h no ritmo padrão (veja `logs_urna/README.md`) |
| `bio_1t.py` | 28 zips, alguns GB no total, baixados e apagados um de cada vez | ~10 min numa conexão rápida |
| `bio_2t.py`, `lista_contingencia.py` | leem os 499.176 logs (32,7 GB comprimidos) com 8 processos | ~10 min cada, em SSD |
| `refetch.py` | 1.971 seções, ~3.900 requisições, 397 MB | ~25 min a 3 req/s |
| `bio_nested.py` | 397 MB de `.jez` | ~30 s |
| `reconcile.py`, `build_uf.py`, `bio_charts.py`, `textos.py` | tabelas acima | segundos |
| `bio_sample_1t.py` | ~600 requisições | ~5 min |

## Ressalvas

- **2º turno pelos logs, não pelo boletim.** A contagem no log reproduz o campo do boletim no 1º turno (300 seções
  sorteadas, acima). No 2º turno, `conferir_bu_2t.py` compara a contagem dos logs com o boletim
  de urna em 4.000 seções (comparecimento e os três contadores de habilitação): todas iguais.
- **Momento da coleta.** O resultado do 2º turno depende do que o TSE tinha publicado quando os logs foram baixados.
  Duas seções do Brasil não tinham log publicado; elas explicam a maior parte dos 508 votos que faltam.
- **Urnas substituídas.** Sem os passos 5 a 7, as 1.971 seções com urna substituída ficam só com o log da urna de
  contingência, e a contagem do 2º turno fica com 156.853 votos a menos (127.697.270 em vez de 127.854.123).
  `bio_sample_1t.py` também lê só o log principal (daí a 1 seção diferente em 300).
- **Denominadores.** 1º turno: comparecimento do boletim. 2º turno: votos contados nos logs (99,9996% do comparecimento
  oficial).
- **Só um dos grupos que votam sem a digital.** A medida não inclui os eleitores sem biometria cadastrada, que também
  votam sem a digital (7.251.808 votos no 2º turno). A planilha de boletins do 1º turno não traz esse grupo; por isso a
  comparação entre os turnos usa só os eleitores com biometria.
- **Fonte das imagens.** Os gráficos usam a Segoe UI (Windows), com a DejaVu Sans do matplotlib como alternativa
  (definido em `abstencao/charts_v2.py`). Fora do Windows, as imagens saem com a outra fonte e quebras de linha um
  pouco diferentes; os números não mudam.
- **Abrir `sections.sqlite` em modo só leitura** ainda cria os arquivos auxiliares `-shm`/`-wal` do SQLite ao lado dele,
  se não existirem; os dados não são alterados.
