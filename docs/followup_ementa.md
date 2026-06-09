# Radar Solar — Mapeamento dos Tópicos da Ementa vs Código

## Disciplina: Fundamentos de Programação (BD004)
## Docente: Flávio da Silva Neves

Mapeamento de cada tópico do conteúdo programático da ementa para
trechos de código do projeto Radar Solar, com exemplos práticos.

---

## 1. Apresentação da Disciplina e Conceitos Fundamentais de Algoritmos

**Conteúdo:** Conceitos fundamentais de algoritmos, exemplos do cotidiano.

**No projeto:** Todo o sistema é uma materialização do conceito de algoritmo:
sequência de passos para transformar dados brutos da ANEEL em inteligência
comercial. O pipeline de dados ilustra isso claramente.

**Exemplo:** `scripts/update_aneel_data.py`
- Algoritmo de download, extração e transformação de dados da ANEEL
- Cada etapa é um passo bem definido: baixar ZIP → extrair CSV →
  filtrar RMR → cruzar equipamentos → gerar parquet

---

## 2. Lógica de Programação e Resolução de Problemas

**Conteúdo:** Raciocínio lógico, decomposição de problemas.

**No projeto:** Decomposição do problema "mapa comercial de energia solar"
em módulos: login, dashboard B2C, dashboard B2B, mapa, kanban, cache CNPJ.

**Exemplo:** `src/ui/pages/demo/mapa.py:702-775` — `carregar_pjs_mapa()`
```

def carregar_pjs_mapa(data: dict) -> list[dict]:
    # 1. Filtrar instalações PJ com CNPJ
    # 2. Consultar cache CNPJá
    # 3. Montar endereço completo
    # 4. Pegar coordenada geocodificada
    # 5. Montar pin com todos os dados
    return pins
```

Cada etapa resolve um subproblema específico.

---

## 3. Representação de Algoritmos: Pseudocódigo e Fluxogramas

**Conteúdo:** Estrutura sequencial, representação de soluções.

**No projeto:** A estrutura do código-fonte funciona como pseudocódigo
executável. As funções são nomeadas de forma descritiva, servindo como
documentação do algoritmo.

**Exemplo:** `src/ui/pages/cliente/faturas.py:105-200`
O fluxo de criação de fatura segue uma sequência lógica clara:
1. Validar dados de entrada
2. Verificar duplicidade de competência
3. Salvar no banco
4. Atualizar dashboard
5. Exibir feedback ao usuário

---

## 4. Introdução ao Python e Ambiente de Desenvolvimento

**Conteúdo:** Primeiros programas, entrada/saída de dados.

**No projeto:** Uso intensivo de funções built-in do Python.

**Exemplos:**
- `src/normalize.py:12-18`
```python
def _text(value: object) -> str:
    return str(value).strip() if pd.notna(value) else ''
```

- `scripts/update_cnpj_enderecos.py:25-26`
```python
def only_digits(value: object) -> str:
    return ''.join(ch for ch in str(value) if ch.isdigit())
```

- `src/ui/pages/demo/mapa.py:760-761`
```python
def _number(value: object) -> float:
    try:
        return float(str(value).replace(',', '.').strip())
    except (ValueError, TypeError):
        return 0.0
```

---

## 5. Variáveis, Tipos de Dados e Operadores

**Conteúdo:** Tipos primitivos (int, float, str, bool), operadores aritméticos,
relacionais e lógicos.

**No projeto:**

**Operadores aritméticos:**
- `src/models.py:53`
```python
economia = (cls.consumo * 0.85) - cls.injecao
```

- `src/ui/pages/cliente/dashboard.py:180`
```python
geracao_estimada = consumo * 0.85
```

**Operadores relacionais e lógicos (if/else):**
- `src/models.py:74-81` — alerta de anomalia
```python
if geracao_estimada < consumo * 0.8:
    return 'Alerta Vermelho'
elif geracao_estimada < consumo * 0.9:
    return 'Alerta Amarelo'
else:
    return 'Normal'
```

**Concatenação de strings:**
- `src/ui/pages/demo/mapa.py:1867-1868`
```python
cidadeUf = f'{pj.municipio.upper()}/{pj.uf}' if pj.uf else pj.municipio.upper()
```

---

## 6. Estruturas de Decisão: if, elif, else

**Conteúdo:** Tomada de decisão com condicionais.

**No projeto:** Uso abundante em validações, autorizações, formatação condicional.

**Exemplos:**

- `src/ui/pages/empresa/kanban.py:148-155` — filtro de leads por perfil
```python
if usuario.tipo == 'Integrador':
    leads_abertos = Lead.select().where(Lead.empresa_responsavel.is_null())
    leads_meus = Lead.select().where(Lead.empresa_responsavel == empresa)
    leads = list(chain(leads_abertos, leads_meus))
elif usuario.tipo == 'Empresa':
    leads = Lead.select().where(Lead.empresa_responsavel == empresa)
```

- `src/ui/pages/public/__init__.py:255-270` — bloqueio de perfil conflitante
```python
if usuario and usuario.tipo != tipo_escolhido:
    raise PerfilConflitanteError(
        f'Este e-mail já está cadastrado como {usuario.tipo}. '
        f'Use o perfil correto para acessar.'
    )
```

- `src/ui/pages/demo/mapa.py:732-734` — fallback de endereço
```python
if bairro_rel and bairro_rel != 'Nao identificado':
    endereco_rel = f'{inst["municipio"]}, {bairro_rel}'
```

---

## 7. Estruturas de Repetição: while

**Conteúdo:** Laço while, controle de repetição.

**No projeto:**

- `scripts/update_cnpj_enderecos.py:62-67` — retry em rate limit
```python
if exc.code == 429:
    print('  Rate limited. Aguardando 60s...')
    time.sleep(60)
    return consultar_cnpja(cnpj)  # recursão simulando while
```

**Nota:** O `while` é usado indiretamente via recursão no retry da API.
No mapa, o loop principal é o `forEach`/`map` do JavaScript (que equivale
a um `while`/`for`), mas no backend Python optamos por `for` com iteráveis
por ser mais idiomático.

---

## 8. Estruturas de Repetição: for

**Conteúdo:** Laço for, iteração sobre intervalos e coleções.

**No projeto:** O `for` é a estrutura de repetição mais usada no sistema.

**Exemplos:**

- `scripts/update_cnpj_enderecos.py:138-139` — iterar CNPJs pendentes
```python
for i, cnpj in enumerate(cnpjs_pendentes, start=1):
    print(f'[{i}/{len(cnpjs_pendentes)}] Consultando {cnpj}...')
```

- `src/ui/pages/demo/mapa.py:706-707` — agregar instalações por município
```python
for lista in data['instalacoesPorMunicipio'].values():
    instalacoes.extend(lista)
```

- `src/ui/pages/demo/mapa.py:715-717` — iterar PJs e montar pins
```python
for inst in pjs:
    cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
    if len(cnpj) != 14:
        continue
```

- `scripts/update_cnpj_enderecos.py:42-48` — ler CSV linha a linha
```python
for linha in linhas[1:]:
    partes = linha.split(';')
    if idx >= len(partes):
        continue
    cnpj_raw = only_digits(partes[idx])
    if len(cnpj_raw) == 14:
        cnpjs_unicos.add(cnpj_raw)
```

---

## 9. Estruturas Básicas de Dados: Listas

**Conteúdo:** Criação, manipulação, percurso, operações básicas.

**No projeto:**

- `src/ui/pages/demo/mapa.py:710` — lista de pins
```python
pins: list[dict] = []
```

- `src/ui/pages/demo/mapa.py:752-774` — append e manipulação de listas
```python
pins.append({
    'codigo': inst['codigo'],
    'titular': inst['titular'],
    'cnpj': cnpj,
    ...
})
```

- `scripts/update_cnpj_enderecos.py:45-47` — compreensão de listas
```python
cnpjs_pendentes = [c for c in carregar_cnpjs_do_csv() if c not in ja_cacheados]
```

- `src/normalize.py:39-42` — list comprehension com filtro
```python
def normalizar_modulo(nome: str) -> str:
    nome_upper = nome.upper().strip()
    for padrao, normalizado in MAPA_MODULOS:
        if any(p in nome_upper for p in padrao):
            return normalizado
    return nome_upper.title()
```

---

## 10. Estruturas de Dados Complementares: Tuplas e Dicionários

**Conteúdo:** Tuplas, dicionários, aplicações práticas.

**No projeto:**

**Dicionários** — estrutura mais usada depois de listas:
- `src/ui/pages/demo/mapa.py:50-144` — dicionário de municípios da RMR
```python
RMR_MUNICIPIOS = {
    '2600054': 'Abreu e Lima',
    '2600609': 'Araçoiaba',
    '2602902': 'Cabo de Santo Agostinho',
    ...
}
```

- `src/ui/pages/demo/mapa.py:711-712` — dict comprehension
```python
cnpj_cache: dict[str, CnpjCache] = {
    c.cnpj: c for c in CnpjCache.select()
}
```

- `src/models.py:102-114` — dicionário de campos do modelo via Peewee

**Tuplas** — usadas para coordenadas, retorno de funções, pares chave-valor:
- `src/ui/pages/demo/mapa.py:736-737`
```python
lat, lng = _estimar_coordenada_por_cep(...)
```

- `src/ui/pages/demo/mapa.py:776-779`
```python
def _estimar_coordenada_por_cep(...) -> tuple[float | None, float | None]:
```

- `src/normalize.py:15-32` — tuplas de mapeamento
```python
MAPA_MODULOS: list[tuple[list[str], str]] = [
    (['JINKO', 'JINKOSOLAR'], 'Jinko'),
    (['CANADIAN', 'CSI'], 'Canadian Solar'),
    (['LONGI'], 'Longi'),
]
```

---

## 11. Funções e Modularização

**Conteúdo:** Definição e uso de funções, parâmetros, retorno e escopo.

**No projeto:** Todo o sistema é estruturado em funções e módulos.

**Exemplos:**

- `src/normalize.py` — módulo dedicado a normalização
```python
def normalizar_modulo(nome: str) -> str: ...
def normalizar_inversor(nome: str) -> str: ...
```

- `src/ui/pages/demo/mapa.py` — funções auxiliares no mapa
```python
def _text(value: object) -> str: ...
def _number(value: object) -> float: ...
def _date_br(value) -> str: ...
def _bairro_key(nome: str) -> str: ...
def _shape_centroid(geometry: dict) -> tuple[float, float] | None: ...
```

- `scripts/update_cnpj_enderecos.py` — pipeline modularizado
```python
def carregar_cnpjs_do_csv() -> list[str]: ...
def consultar_cnpja(cnpj: str) -> dict | None: ...
def extrair_dados_cnpj(dados: dict) -> dict: ...
def geocodificar(endereco: str) -> tuple[float | None, float | None]: ...
def atualizar_parquet() -> None: ...
def main() -> int: ...
```

---

## 12. Algoritmos Estruturados e Boas Práticas

**Conteúdo:** Organização, legibilidade, reuso de código, refatoração.

**No projeto:**

**Organização:** Separação clara em módulos `src/models.py` (dados),
`src/ui/` (interface), `scripts/` (utilitários), `src/normalize.py` (lógica).

**Reuso:**
- `src/normalize.py` é importado por `src/ui/pages/demo/mapa.py`
```python
from src.normalize import normalizar_inversor, normalizar_modulo
```

**Refatoração:**
- `src/ui/pages/demo/mapa.py:300-323` — função que monta instalações é
  reusada tanto pelo mapa quanto pela tabela e gráficos
- `scripts/update_cnpj_enderecos.py:137-183` — `atualizar_parquet()` é
  reusada no final do script e também chamada quando não há pendentes

**Legibilidade:**
- Nomes descritivos: `carregar_pjs_mapa`, `geocodificar`, `formatCnpj`
- Type hints em todas as funções
- Comentários em blocos de lógica complexa

---

## 13. Integração de Conceitos

**Conteúdo:** Uso combinado de estruturas de controle e dados.

**No projeto:** O mapa `/demo/mapa` é o melhor exemplo de integração:

1. **Dicionários** para configurar municípios (`RMR_MUNICIPIOS`)
2. **Listas** para coleções de instalações e pins
3. **For** para iterar e montar dados
4. **If/else** para filtros e formatação condicional
5. **Funções** para modularizar o código
6. **Tuplas** para retorno de coordenadas
7. **Arquivos** (parquet/CSV) para persistência
8. **API externa** para geocoding
9. **JSON** para serialização e envio ao frontend

**Exemplo no pipeline de dados (`scripts/update_aneel_data.py`):**
1. Download de ZIP com `urllib`
2. Extração com `zipfile`
3. Leitura com `pandas`
4. Filtro com expressões booleanas
5. Agrupamento com `groupby`
6. Normalização com dicionários
7. Escrita em parquet

---

## 14. Desenvolvimento de Algoritmos Aplicados

**Conteúdo:** Implementação de um problema completo em Python.

**No projeto:** O projeto completo é a aplicação prática. Dois algoritmos
de destaque:

**Algoritmo de geocoding com fallback** (`src/ui/pages/demo/mapa.py:759-803`):
```
1. Tentar CEP exato → buscar bairro no shapefile
2. Se não achar, tentar prefixo do CEP → buscar bairro
3. Se não achar, usar centróide do bairro fallback
4. Se não achar, usar centróide do município
5. Retornar (lat, lng) ou (None, None)
```

**Algoritmo de recomendação de energia solar** (`src/normalize.py`):
```
1. Identificar fabricante do equipamento
2. Normalizar variações ortográficas
3. Cruzar com dados de desempenho histórico
4. Estimar geração esperada
```

---

## 15. Testes e Validação de Algoritmos

**Conteúdo:** Testes e validação das soluções, correção lógica.

**No projeto:** A validação é feita de forma prática:

- **Teste de validação de dados** em `src/ui/pages/cliente/faturas.py`:
```python
if not consumo or not valor:
    ui.notify('Preencha consumo e valor da fatura', type='warning')
    return
```

- **Validação de CPF/CNPJ** em `src/ui/pages/demo/mapa.py:717-718`:
```python
cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
if len(cnpj) != 14:
    continue
```

- **Validação de coordenadas** em `src/ui/pages/demo/mapa.py:749-750`:
```python
if not lat or not lng:
    continue
```

- **Tratamento de erros de API** em `scripts/update_cnpj_enderecos.py:53-71`:
```python
try:
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))
except HTTPError as exc:
    if exc.code == 404: ...
    if exc.code == 429: ...
except (URLError, TimeoutError, json.JSONDecodeError) as exc: ...
```

**Observação:** Testes unitários formais com `pytest` ainda não foram
implementados (RNF07 pendente).

---

## Resumo por Aula

| Aula | Data | Conteúdo | Onde usamos no projeto |
|------|------|----------|----------------------|
| 1 | 11/2 | Apresentação, algoritmos | Todo o sistema |
| 2 | 25/2 | Lógica, decomposição | `carregar_pjs_mapa()` — quebra em 5 passos |
| 3 | 4/3 | Pseudocódigo, fluxogramas | Nomes descritivos de funções (`_estimar_coordenada_por_cep`) |
| 4 | 11/3 | Python, I/O | `only_digits()`, `_text()`, `_number()` |
| 5 | 18/3 | Variáveis, tipos, operadores | `models.py:53` (economia = consumo*0.85 - injecao) |
| 6 | 25/3 | if/elif/else | Filtro de perfil, validações, bloqueio de conflito |
| 7 | 1/4 | while | Retry de rate limit (recursão simulando while) |
| 8 | 8/4 | for | `for inst in pjs`, `for linha in linhas` |
| 9 | 15/4 | **AV1** | — |
| 10 | 22/4 | Listas | `pins.append({...})`, list comprehensions |
| 11 | 29/4 | Tuplas, dicionários | `tuple[float, float]`, `RMR_MUNICIPIOS`, dict comprehensions |
| 12 | 6/5 | Funções, modularização | `normalizar_modulo()`, `geocodificar()`, `extrair_dados_cnpj()` |
| 13 | 13/5 | Boas práticas, refatoração | Separação em módulos, type hints, reuso via `src/normalize.py` |
| 14 | 20/5 | Integração de conceitos | Mapa completo (listas + dicts + for + if + funções + API + JSON) |
| 15 | 27/5 | Algoritmos aplicados | Pipeline ANEEL + geocoding com fallback |
| 16 | 3/6 | Revisão prática | — |
| **17** | **10/6** | **Apresentação do projeto** | **Radar Solar — este repositório** |
| 18 | 17/6 | **AV2** | — |
| — | 13/6 | **SR2** | **Entrega do projeto + pitch** |
| — | 20/6 | **Mostra TechDesign** | **Exposição do projeto** |
