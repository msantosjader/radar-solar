# Radar Solar — Apresentação da Ementa

Aplicação web para conectar consumidores de energia solar (B2C) a integradores (B2B).
Desenvolvida como artefato avaliativo da disciplina **Projetos 1 (2026.1)** — CESAR School.

---

## 1 — Estruturas básicas no Radar Solar

Os fundamentos aparecem no fluxo principal: validar entradas, calcular alertas,
percorrer instalações, montar coleções para o mapa e controlar decisões do sistema.

### Variáveis, tipos e operadores aritméticos/relacionais

**Arquivo:** `src/ui/pages/cliente/dashboard.py:111-114`

O dashboard compara a geração atual com a do mês anterior. Usa variáveis
numéricas, operadores aritméticos e comparação relacional para a regra de alerta.

```python
queda_percentual = ((anterior - atual) / anterior) * 100
if queda_percentual >= LIMIAR_QUEDA_GERACAO_PERCENT:
    alertas.append(
        f'Queda de geracao acima do limite: {_format_percent(queda_percentual)}'
    )
```

### Estruturas de decisão e operadores lógicos

**Arquivos:** `auth.py:56-63`, `faturas.py:20-33`, `empresa/kanban.py:35-38`

Decisões em autenticação, validação de formulários e consultas SQL. Usamos
`if/else`, `and` em Python puro e `&`/`|` em consultas Peewee para AND/OR no SQL.

```python
# Exemplo 1: if + and em regra de autenticação
if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    raise PerfilConflitanteError(...)

# Exemplo 2: if aninhado em validação de formulário
if not text:
    if optional:
        return None
    raise ValueError(f'O campo "{field_name}" e obrigatorio.')

# Exemplo 3: AND (&) e OR (|) em consulta Peewee
Lead.select().where(
    (Lead.status.in_(STATUS_KANBAN))
    & ((Lead.empresa_responsavel.is_null(True)) | (Lead.empresa_responsavel == empresa_id))
)
```

### Estrutura de repetição: for

**Arquivos:** `mapa.py:713-716`, `update_cnpj_enderecos.py:51-57`

O `for` percorre registros tanto na montagem do mapa quanto no pipeline de dados.

```python
# Exemplo 1: percorrer PJs do mapa
for inst in pjs:
    cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
    if len(cnpj) != 14:
        continue

# Exemplo 2: percorrer linhas do CSV
for linha in linhas[1:]:
    partes = linha.split(';')
    if idx >= len(partes):
        continue
    cnpj_raw = only_digits(partes[idx])
```

### Repetição controlada: retry sem while

**Arquivos:** `update_cnpj_enderecos.py:72-75`, `update_all.py:93-109`

O código não usa `while` diretamente. Para a API CNPJá, quando o servidor
responde HTTP 429 (rate limit), o script espera 60s e chama a mesma função
de novo — repetição por recursão controlada por condição de erro.

```python
# Exemplo 1: retry da API CNPJá após rate limit
if exc.code == 429:
    print(f'  Rate limited. Aguardando 60s...')
    time.sleep(60)
    return consultar_cnpja(cnpj)

# Exemplo 2: sequência do pipeline
code = _run('update_aneel_data.py', '1/3: Atualizacao ANEEL')
if code != 0:
    return code
```

### Listas e dicionários

**Arquivos:** `mapa.py:708-711`, `empresa/kanban.py:31-43`

Listas guardam coleções ordenadas; dicionários agrupam por chave. O mapa usa
para pins e cache; o kanban separa leads por status.

```python
# Exemplo 1: lista de pins e cache por CNPJ
pins: list[dict] = []
cnpj_cache: dict[str, CnpjCache] = {
    c.cnpj: c for c in CnpjCache.select()
}
pins.append({
    'codigo': inst['codigo'],
    'titular': inst['titular'],
    'cnpj': cnpj,
    'lat': float(lat),
    'lng': float(lng),
})

# Exemplo 2: leads agrupados por status
leads_por_status = {status: [] for status in STATUS_KANBAN}
for lead in leads:
    leads_por_status.setdefault(lead.status, []).append(lead)
```

### Tuplas para coordenadas

**Arquivos:** `mapa.py:763-766`, `update_cnpj_enderecos.py:125-136`

Coordenadas são retornadas em pares. O tipo da função indica que cada valor
pode ser nulo quando a geocodificação falha.

```python
def _estimar_coordenada_por_cep(
    municipio_codigo: str, cep_digits: str, prefixo: str,
    bairros_por_cep_exato: dict, bairros_por_prefixo: dict, data: dict,
) -> tuple[float | None, float | None]:

def geocodificar(endereco: str) -> tuple[float | None, float | None]:
    if resultados:
        return (float(resultados[0]['lat']), float(resultados[0]['lon']))
    return (None, None)
```

### Leitura de dados e arquivos

**Arquivos:** `mapa.py:281,398`, `update_cnpj_enderecos.py:39`

O projeto lê Parquet (instalações), shapefiles do IBGE (geometria) e CSV
(texto) para alimentar o pipeline.

```python
# Exemplo 1: leitura analítica em Parquet
df = pd.read_parquet(INSTALACOES_PARQUET, columns=colunas)

# Exemplo 2: leitura de shapefile do IBGE
municipio_reader = shapefile.Reader(str(MUNICIPIOS_SHP), encoding='cp1252')

# Exemplo 3: leitura de CSV como texto no pipeline CNPJ
linhas = EMPREENDIMENTOS_CSV.read_text(encoding='latin1').splitlines()
```

---

## 2 — Funções, módulos e boas práticas

Responsabilidades separadas em módulos pequenos: autenticação, normalização,
utilitários, mapa, dashboard e pipeline ficam em arquivos distintos.

### Função com responsabilidade clara

**Arquivo:** `src/ui/pages/demo/mapa.py:702-760`

A função agrega instalações, filtra CNPJs, consulta cache, monta endereço
e devolve uma lista pronta para o frontend.

```python
def carregar_pjs_mapa(data: dict) -> list[dict]:
    instalacoes = []
    for lista in data['instalacoesPorMunicipio'].values():
        instalacoes.extend(lista)
    pjs = [inst for inst in instalacoes if inst.get('tipo') == 'PJ' and inst.get('cpf_cnpj')]
    pins: list[dict] = []
```

### Reuso entre módulos

**Arquivo:** `src/ui/pages/demo/mapa.py:20-21`

O mapa importa funções prontas de outros módulos, reduzindo duplicação.

```python
from src.models import CnpjCache, InstalacaoSolar, Lead
from src.normalize import normalizar_inversor, normalizar_modulo
```

### Constantes nomeadas

**Arquivo:** `src/ui/pages/cliente/dashboard.py:12-13`

Valores mágicos transformados em constantes para clareza e fácil ajuste.

```python
LIMIAR_QUEDA_GERACAO_PERCENT = 20.0
LIMIAR_DIFERENCA_GERACAO_INJECAO_PERCENT = 35.0
```

### Tratamento de erro em API externa

**Arquivo:** `scripts/update_cnpj_enderecos.py:68-80`

O pipeline trata CNPJ não encontrado (404), rate limit (429) e erros de rede
sem derrubar o processamento.

```python
except HTTPError as exc:
    if exc.code == 404:
        return {'taxId': cnpj, 'company': {}}
    if exc.code == 429:
        time.sleep(60)
        return consultar_cnpja(cnpj)
except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    return None
```

---

## 3 — CRUD de faturas

Ciclo completo de dados: cadastrar, consultar, editar e excluir faturas no SQLite.

### Create: cadastrar fatura

**Arquivo:** `src/ui/pages/cliente/faturas.py:258-274`

Valida se já existe fatura para a mesma competência antes de criar.

```python
if _usuario_ja_tem_fatura_na_competencia(usuario.id, mes, state['edit_id']):
    ui.notify('Ja existe uma fatura cadastrada para essa competencia.', color='warning')
    return
instalacao = _obter_ou_criar_instalacao_manual(usuario.id)
Fatura.create(instalacao=instalacao, **payload)
ui.notify('Fatura salva com sucesso.', color='positive')
```

### Read: listar faturas

**Arquivo:** `src/ui/pages/cliente/faturas.py:115-121`

Consulta faturas do usuário logado, mantendo cada cliente isolado dos demais.

```python
def _listar_faturas_usuario(usuario_id: int) -> list[Fatura]:
    instalacoes_ids = InstalacaoSolar.select(InstalacaoSolar.id).where(InstalacaoSolar.usuario == usuario_id)
    return list(
        Fatura.select()
        .where(Fatura.instalacao.in_(instalacoes_ids))
        .order_by(Fatura.criado_em.desc())
    )
```

### Update: editar fatura

**Arquivo:** `src/ui/pages/cliente/faturas.py:262-270`

Busca a fatura por ID, atualiza campos e persiste com `save()`.

```python
if state['edit_id']:
    fatura = _obter_fatura_do_usuario(usuario.id, state['edit_id'])
    if not fatura:
        ui.notify('Fatura nao encontrada para edicao.', color='negative')
        return
    for field, value in payload.items():
        setattr(fatura, field, value)
    fatura.save()
```

### Delete: excluir fatura

**Arquivo:** `src/ui/pages/cliente/faturas.py:294-302`

Remove o registro, limpa formulário, recarrega lista e mostra feedback.

```python
fatura = _obter_fatura_do_usuario(usuario.id, fatura_id)
if not fatura:
    ui.notify('Fatura nao encontrada para exclusao.', color='negative')
    return
fatura.delete_instance()
limpar_formulario()
carregar_faturas()
ui.notify('Fatura excluida com sucesso.', color='positive')
```

---

## 4 — Algoritmos aplicados

A camada de dados resolve problemas práticos: localizar empresas no mapa,
padronizar nomes inconsistentes da ANEEL e atualizar a base sem trabalho manual.

### Geocoding com fallback

**Arquivo:** `src/ui/pages/demo/mapa.py:767-799`

Quando não há coordenada exata, tenta caminhos progressivos: CEP, prefixo,
bairro fallback, município e, por fim, `None`.

```python
candidatos = bairros_por_cep_exato.get(municipio_codigo, {}).get(cep_digits, set())
if not candidatos and municipio_codigo and len(prefixo) >= 5:
    candidatos = bairros_por_prefixo.get(municipio_codigo, {}).get(prefixo[:5], set())
for feature in bairros:
    if feature['properties'].get('tipo') == 'bairro_fallback':
        c = _shape_centroid(feature['geometry'])
        if c:
            return c
return None, None
```

### Normalização de fabricantes

**Arquivo:** `src/normalize.py:9-24, 687-690`

A ANEEL traz nomes de fabricantes com muitas variações. O código limpa
acentos, espaços e caixa alta antes de aplicar ~370 sinônimos para
exibir gráficos consistentes.

```python
def _normalizar_str(value: str) -> str:
    value = _limpar(value)
    value = value.upper()
    value = _strip_accents(value)
    return value

def normalizar_modulo(value: str | None) -> str:
    return _normalizar_fabricante(value, _SINONIMOS_MODULO, _FABRICANTES_MODULO)
```

### Pipeline completo de dados

**Arquivo:** `scripts/update_all.py`

O orquestrador executa três etapas sequenciais:

```
1. update_aneel_data.py        # baixa e processa dados ANEEL
2. extract_aneel_rmr_csv.py    # gera CSVs filtrados da RMR
3. update_cnpj_enderecos.py    # consulta CNPJá, geocodifica e atualiza cache
```

### Execução sequencial com parada em erro

**Arquivo:** `scripts/update_all.py:93-109`

Cada etapa só avança se a anterior terminar sem erro.

```python
code = _run('update_aneel_data.py', '1/3: Atualizacao ANEEL')
if code != 0:
    return code
code = _run('extract_aneel_rmr_csv.py', '2/3: Extracao CSVs RMR')
if code != 0:
    return code
if not args.skip_cnpj:
    code = _run('update_cnpj_enderecos.py', '3/3: Enriquecimento CNPJ')
    if code != 0:
        return code
```

---

## 5 — Stack utilizada

| Tecnologia | Papel |
|------------|-------|
| **Python + NiceGUI** | Base da aplicação web, rotas, interface e orquestração |
| **SQLite + Peewee** | Banco local do MVP e ORM (usuário, faturas, leads, cache) |
| **Pandas + Parquet** | Processamento analítico dos dados ANEEL |
| **Leaflet.js** | Mapa interativo, heatmap, bairros, pins e popups |
| **Chart.js** | Gráficos: conexões por ano, fabricantes, classes, PF/PJ |
| **Firebase** | Autenticação com Magic Link por e-mail |
| **HTML, CSS e JavaScript** | Assets públicos, mapa client-side, filtros e paginação |
| **Git + GitHub** | Controle de versão, branches e pull requests |
| **Dados abertos e APIs** | ANEEL, IBGE, Correios, CNPJá, Nominatim, ViaCEP, BrasilAPI |

---

## Execução

```bash
# Instalar dependências
uv sync
# ou: pip install -e .

# Inicializar banco
python scripts/init_db.py

# Pipeline completo (opcional)
python scripts/update_all.py

# Iniciar servidor
python main.py
# Acessar http://localhost:8080
```
