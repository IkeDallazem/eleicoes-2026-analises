# Eleições 2026: análises com dados públicos do TSE

Scripts que reproduzem seis análises da eleição presidencial de 2026, feitas só com dados públicos do TSE: arquivos de
resultado, dados abertos, boletins de urna e logs das urnas. Cada pasta de análise tem um README com o método, as fontes, os
comandos na ordem certa, as saídas e as ressalvas.

| Pasta | O que mede |
|---|---|
| [`logs_urna/`](logs_urna/) | Coleta dos logs das urnas do 2º turno. Votos registrados depois das 17h e eleitores habilitados sem biometria, seção por seção |
| [`comparacao_bu/`](comparacao_bu/) | Resultado do 2º turno nas seções sinalizadas × seções da mesma zona, a partir dos boletins de urna |
| [`abstencao/`](abstencao/) | Abstenção do 1º para o 2º turno, por estado e por município, com 2022 como referência |
| [`biometria/`](biometria/) | Votos de eleitores com biometria cadastrada que não foram habilitados pela digital, 1º × 2º turno, por estado |
| [`comparecimento_dia/`](comparecimento_dia/) | Variação do comparecimento seção por seção e uso da biometria ao longo do dia |
| [`modelo_historico/`](modelo_historico/) | 2º turno de 2026 comparado aos de 2002 a 2022: estimativa do 2º turno a partir do 1º, município por município |
| [`comum/`](comum/) | Pastas de dados (`caminhos.py`) e contornos dos estados para os mapas (`ufs.json`, `gerar_ufs.py`) |

## Requisitos

- Python 3.12 ou mais novo e os pacotes de `requirements.txt` (`pip install -r requirements.txt`, ou
  `uv run --with <pacote> python ...`, como nos READMEs).
- `curl` (em `biometria/bio_1t.py` e num download descrito em `comparacao_bu/`).
- Playwright com Microsoft Edge ou o Chromium do Playwright, só para as imagens de `logs_urna/` e `comparacao_bu/`
  (`python -m playwright install chromium`).
- As imagens saem idênticas às publicadas com matplotlib 3.11.2 e a fonte Segoe UI (Windows). Em outros sistemas a
  fonte DejaVu Sans entra no lugar: os números são os mesmos, mas o texto muda um pouco de largura. Para usar
  exatamente essas versões com uv: `uv run --no-project --with-requirements requirements.txt python <script>`.

## Dados

Nada do que é baixado ou gerado fica junto do código. Tudo vai para `dados/` na raiz do repositório, ou para a pasta
indicada na variável de ambiente `ELEICOES_DADOS`:

```
dados/
  urna_logs/        logs do 2º turno (logs_urna/coletar_logs.py): sections.sqlite e day/
  tse/              arquivos de resultado e zips de dados abertos do TSE
  jez_contingencia/ logs completos das seções com urna substituída (biometria/refetch.py)
  bu_2t/            boletins de urna do 2º turno da amostra (comparacao_bu/baixar_bu.py)
  derivados/X/      tabelas, imagens e textos gerados pela análise X
```

## Dependências entre as análises

- `abstencao/baixar.py` baixa os arquivos de resultado por UF e o nacional, além dos zips de votação por município. Eles
  são usados por quase todas as análises.
- `logs_urna/coletar_logs.py` baixa os logs das urnas: cerca de 499 mil seções, uns 90 GB transferidos e cerca de 35 GB
  em disco; no ritmo padrão (até 8 requisições por segundo), a coleta leva mais de 30 h. Esses logs são a base de `logs_urna/`, `biometria/` e `comparecimento_dia/`.
- `comparacao_bu/` usa o `secoes_analisadas.csv` gerado por `logs_urna/`.
- `comparecimento_dia/` usa as tabelas por seção geradas por `biometria/`.
- `biometria/conferir_bu_2t.py` usa `comparacao_bu/baixar_bu.py` (para baixar os BUs) e `comparacao_bu/bu_parser.py`;
  `comparacao_bu/` baixa o zip de votação por seção com `modelo_historico/baixar.py secao2026`.
- `abstencao/` e `modelo_historico/` não dependem dos logs.

## Requisições ao TSE

Todos os scripts identificam as requisições com o User-Agent de `comum/caminhos.py`, repetem em caso de erro com
espera crescente e começam com um ritmo conservador: no máximo 3 por segundo no site de resultados e até 8 por segundo
na coleta dos logs, com redução automática a cada HTTP 429. Ritmos maiores ficam por conta e risco de quem roda: o TSE
pode bloquear temporariamente quem faz requisições demais.

## Reprodutibilidade

- `abstencao/sha256_entradas.txt` e `modelo_historico/sha256_entradas.txt` trazem o SHA-256 dos arquivos do TSE usados.
  `biometria/sha256_resultados.txt` traz o SHA-256 das tabelas geradas. O TSE pode republicar arquivos: se os hashes
  não baterem, os números podem mudar um pouco.
- A comparação de `comparacao_bu/` foi feita com as seções sinalizadas até aquele momento da coleta. A amostra usada
  está congelada em `comparacao_bu/dados_congelados/`.
- Os logs e os boletins de urna são públicos, seção por seção, em
  `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/`. Os dados abertos estão em
  `https://dadosabertos.tse.jus.br/` e `https://cdn.tse.jus.br/estatistica/sead/odsele/`.

## Dados de terceiros

`comum/ufs.json` é uma versão simplificada de `brazil-states.geojson`, do projeto
[codeforamerica/click_that_hood](https://github.com/codeforamerica/click_that_hood) (licença MIT; hoje o projeto fica em
codeforgermany/click_that_hood). `python comum/gerar_ufs.py` (precisa de duckdb) refaz `comum/ufs.json` a partir da
fonte; é o único script que grava dentro da pasta do código.

## Licença

O código está sob a licença MIT (arquivo `LICENSE`). Os dados do TSE são públicos. `comum/ufs.json` segue a licença
MIT do projeto de origem (veja "Dados de terceiros").
