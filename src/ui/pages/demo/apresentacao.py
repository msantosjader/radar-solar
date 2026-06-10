from __future__ import annotations

from nicegui import ui

from src.ui.pages.public import inject_public_styles


def _nav_bar() -> None:
    with ui.row().classes('w-full items-center justify-between px-6 py-3 bg-white border-b border-slate-200 sticky top-0 z-50'):
        with ui.row().classes('items-center gap-3'):
            ui.image('/assets/images/logo_radarsolar.png').classes('w-8 h-8')
            ui.label('Radar Solar').classes('text-lg font-bold text-slate-900')
        with ui.row().classes('items-center gap-4 max-[700px]:hidden'):
            ui.link('Estruturas básicas', '#estruturas').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Modularização', '#modularizacao').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('CRUD', '#crud').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Algoritmos', '#algoritmos').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Stack', '#stack').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Mapa', '/demo/mapa').classes('text-sm text-secondary font-semibold no-underline')


def _section_header(title: str, description: str) -> None:
    with ui.column().classes('w-full max-w-5xl gap-4 rs-animate-up'):
        ui.label(title).classes('text-4xl font-bold text-slate-900 leading-tight max-[700px]:text-3xl')
        ui.label(description).classes('text-xl text-slate-600 leading-8 max-w-5xl')


def _code_quote(code: str) -> None:
    with ui.card().classes(
        'w-full bg-slate-950 text-slate-100 p-4 rounded-xl font-mono text-xs '
        'leading-relaxed overflow-x-auto border border-slate-800 shadow-inner'
    ):
        ui.label(code.strip()).classes('whitespace-pre')


def _evidence(title: str, file_ref: str, explanation: str, code: str) -> None:
    with ui.card().classes(
        'w-full p-6 rounded-2xl border border-slate-200 bg-white shadow-sm '
        'rs-animate-up hover:shadow-lg transition-shadow'
    ):
        with ui.row().classes('w-full items-start justify-between gap-6 max-[900px]:flex-col'):
            with ui.column().classes('gap-2 flex-1'):
                ui.label(title).classes('text-xl font-bold text-slate-900')
                ui.label(file_ref).classes('text-sm font-mono text-secondary')
                ui.label(explanation).classes('text-base text-slate-600 leading-relaxed')
            with ui.column().classes('w-full max-w-xl'):
                _code_quote(code)


def _stack_card(name: str, description: str, image_url: str) -> None:
    with ui.card().classes(
        'p-5 rounded-2xl border border-slate-200 bg-white shadow-sm '
        'rs-animate-up hover:shadow-lg transition-shadow min-h-48'
    ):
        with ui.row().classes('items-center gap-4'):
            ui.image(image_url).classes('w-12 h-12 object-contain')
            with ui.column().classes('gap-1'):
                ui.label(name).classes('text-lg font-bold text-slate-900')
                ui.label(description).classes('text-sm text-slate-600 leading-relaxed')


def _anchor(anchor_id: str) -> None:
    ui.html(f'<span id="{anchor_id}" class="rs-anchor"></span>')


def render_apresentacao() -> None:
    inject_public_styles()
    ui.add_head_html('''
    <style>
      html { scroll-behavior: smooth; }
      .rs-anchor { display: block; position: relative; top: -92px; visibility: hidden; }
    </style>
    ''')
    _nav_bar()

    with ui.column().classes('w-full bg-slate-50'):
        with ui.column().classes('w-full items-center gap-10 py-24 px-6 bg-white'):
            _anchor('estruturas')
            _section_header(
                'Estruturas básicas no Radar Solar',
                'Os fundamentos aparecem no fluxo principal da aplicação: validar entradas, calcular alertas, percorrer '
                'instalações, montar coleções para o mapa e controlar decisões importantes do sistema.',
            )

            with ui.column().classes('w-full max-w-5xl gap-6'):
                _evidence(
                    'Variáveis, tipos e operadores',
                    'src/ui/pages/cliente/dashboard.py:111-114',
                    'O dashboard compara a geração atual com a geração do mês anterior. Esse trecho usa variáveis numéricas, '
                    'operadores aritméticos e uma constante que representa a regra de negócio do alerta.',
                    """# Exemplo 1: cálculo de alerta no dashboard
queda_percentual = ((anterior - atual) / anterior) * 100
if queda_percentual >= LIMIAR_QUEDA_GERACAO_PERCENT:
    alertas.append(
        f'Queda de geracao acima do limite: {_format_percent(queda_percentual)}'
    )""",
                )
                _evidence(
                    'Estrutura de decisão: if/else',
                    'auth.py:56-63 / faturas.py:20-33',
                    'As decisões aparecem em regras de autenticação e validação de formulários. O sistema bloqueia perfis '
                    'conflitantes e também impede que valores inválidos sejam salvos como fatura.',
                    """# Exemplo 1: bloqueio de perfil conflitante
if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    perfil_existente = TIPO_TO_LABEL.get(usuario_existente.tipo_perfil, usuario_existente.tipo_perfil)
    perfil_solicitado = TIPO_TO_LABEL.get(tipo_perfil, tipo_perfil)
    raise PerfilConflitanteError(
        f'Este e-mail ja esta cadastrado como {perfil_existente}. '
        f'Para acessar como {perfil_solicitado}, use outro e-mail.'
    )

# Exemplo 2: campo obrigatório na fatura
if not text:
    if optional:
        return None
    raise ValueError(f'O campo "{field_name}" e obrigatorio.')""",
                )
                _evidence(
                    'Operadores lógicos',
                    'auth.py:56 / empresa/kanban.py:35-38',
                    'O projeto usa operadores lógicos para combinar condições. Em Python puro usamos and; nas consultas '
                    'Peewee, usamos & e | para representar AND e OR no SQL gerado pelo ORM.',
                    """# Exemplo 1: operador lógico and em Python
if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    raise PerfilConflitanteError(...)

# Exemplo 2: AND (&) e OR (|) em consulta Peewee
Lead.select().where(
    (Lead.status.in_(STATUS_KANBAN))
    & ((Lead.empresa_responsavel.is_null(True)) | (Lead.empresa_responsavel == empresa_id))
)""",
                )
                _evidence(
                    'Estrutura de repetição: for',
                    'mapa.py:713-716 / update_cnpj_enderecos.py:51-57',
                    'O for aparece tanto na montagem visual do mapa quanto no processamento de arquivos. Em ambos os casos, '
                    'o loop percorre registros e decide quais entram no resultado final.',
                    """# Exemplo 1: percorrer PJs do mapa
for inst in pjs:
    cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
    if len(cnpj) != 14:
        continue

# Exemplo 2: percorrer linhas do CSV
for linha in linhas[1:]:
    partes = linha.split(';')
    if idx >= len(partes):
        continue
    cnpj_raw = only_digits(partes[idx])""",
                )
                _evidence(
                    'Repetição controlada: retry sem while',
                    'update_cnpj_enderecos.py:72-75 / update_all.py:93-109',
                    'O código Python não usa while diretamente. Para a API CNPJá, quando o servidor responde com HTTP 429 '
                    '(rate limit), o script espera 60 segundos e chama a mesma função de novo. É uma repetição por recursão, '
                    'controlada por uma condição de erro. No pipeline, cada etapa também só avança se a anterior terminar sem erro.',
                    """# Exemplo 1: retry da API CNPJá após rate limit
if exc.code == 429:
    print(f'  Rate limited. Aguardando 60s...')
    time.sleep(60)
    return consultar_cnpja(cnpj)

# Exemplo 2: sequência do pipeline
code = _run('update_aneel_data.py', '1/3: Atualizacao ANEEL')
if code != 0:
    return code""",
                )
                _evidence(
                    'Listas e dicionários',
                    'mapa.py:708-711 / empresa/kanban.py:31-43',
                    'Listas guardam coleções ordenadas de itens; dicionários agrupam informações por chave. O mapa usa isso '
                    'para pins e cache, enquanto o kanban usa para separar leads por status.',
                    """# Exemplo 1: lista de pins e cache por CNPJ
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
    leads_por_status.setdefault(lead.status, []).append(lead)""",
                )
                _evidence(
                    'Tuplas para coordenadas',
                    'mapa.py:763-766 / update_cnpj_enderecos.py:125-136',
                    'Coordenadas são retornadas em pares. O tipo da função deixa claro que o resultado tem dois valores e '
                    'que cada um pode ser nulo quando a geocodificação falha.',
                    """# Exemplo 1: fallback por CEP no mapa
def _estimar_coordenada_por_cep(
    municipio_codigo: str, cep_digits: str, prefixo: str,
    bairros_por_cep_exato: dict, bairros_por_prefixo: dict, data: dict,
) -> tuple[float | None, float | None]:

# Exemplo 2: geocodificação por endereço
def geocodificar(endereco: str) -> tuple[float | None, float | None]:
    if resultados:
        return (float(resultados[0]['lat']), float(resultados[0]['lon']))
    return (None, None)""",
                )
                _evidence(
                    'Leitura de dados e arquivos',
                    'mapa.py:281, 398 / update_cnpj_enderecos.py:39',
                    'Além de entrada por formulário, o projeto lê arquivos reais: Parquet para instalações, shapefiles do '
                    'IBGE para geometria e CSV/texto para dados usados no pipeline.',
                    """# Exemplo 1: leitura analítica em Parquet
df = pd.read_parquet(INSTALACOES_PARQUET, columns=colunas)

# Exemplo 2: leitura de shapefile do IBGE
municipio_reader = shapefile.Reader(str(MUNICIPIOS_SHP), encoding='cp1252')

# Exemplo 3: leitura de CSV como texto no pipeline CNPJ
linhas = EMPREENDIMENTOS_CSV.read_text(encoding='latin1').splitlines()""",
                )

        with ui.column().classes('w-full items-center gap-10 py-24 px-6 bg-slate-50'):
            _anchor('modularizacao')
            _section_header(
                'Funções, módulos e boas práticas',
                'O projeto separa responsabilidades em módulos pequenos. Autenticação, normalização, utilitários, mapa, '
                'dashboard e pipeline ficam em lugares diferentes, o que torna o código mais fácil de explicar e manter.',
            )

            with ui.column().classes('w-full max-w-5xl gap-6'):
                _evidence(
                    'Função com responsabilidade clara',
                    'src/ui/pages/demo/mapa.py:702-760',
                    'A função carrega pins de empresas no mapa. Ela agrega instalações, filtra CNPJs, consulta cache, '
                    'monta endereço e devolve uma lista pronta para o frontend.',
                    """def carregar_pjs_mapa(data: dict) -> list[dict]:
    instalacoes = []
    for lista in data['instalacoesPorMunicipio'].values():
        instalacoes.extend(lista)

    pjs = [inst for inst in instalacoes if inst.get('tipo') == 'PJ' and inst.get('cpf_cnpj')]
    pins: list[dict] = []""",
                )
                _evidence(
                    'Reuso entre módulos',
                    'src/ui/pages/demo/mapa.py:20-21',
                    'O mapa não precisa conhecer os detalhes da normalização. Ele importa funções prontas de outro módulo, '
                    'o que reduz duplicação e facilita manutenção.',
                    """from src.models import CnpjCache, InstalacaoSolar, Lead
from src.normalize import normalizar_inversor, normalizar_modulo""",
                )
                _evidence(
                    'Constantes nomeadas',
                    'src/ui/pages/cliente/dashboard.py:12-13',
                    'Valores mágicos foram transformados em constantes. Assim, a regra de alerta fica clara, centralizada '
                    'e fácil de ajustar.',
                    """LIMIAR_QUEDA_GERACAO_PERCENT = 20.0
LIMIAR_DIFERENCA_GERACAO_INJECAO_PERCENT = 35.0""",
                )
                _evidence(
                    'Tratamento de erro em API externa',
                    'scripts/update_cnpj_enderecos.py:68-80',
                    'O pipeline consulta serviços externos que podem falhar ou limitar requisições. O código trata CNPJ '
                    'não encontrado, rate limit e erros de rede sem derrubar o processamento.',
                    """except HTTPError as exc:
    if exc.code == 404:
        return {'taxId': cnpj, 'company': {}}
    if exc.code == 429:
        time.sleep(60)
        return consultar_cnpja(cnpj)
except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    return None""",
                )

        with ui.column().classes('w-full items-center gap-10 py-24 px-6 bg-white'):
            _anchor('crud')
            _section_header(
                'CRUD de faturas',
                'A tela de faturas mostra o ciclo completo de dados do usuário: cadastrar, consultar, editar e excluir. '
                'Cada ação valida entradas, persiste no SQLite e atualiza a interface com feedback visual.',
            )

            with ui.column().classes('w-full max-w-5xl gap-6'):
                _evidence(
                    'Create: cadastrar uma fatura',
                    'src/ui/pages/cliente/faturas.py:258-274',
                    'Antes de salvar, o sistema valida se já existe uma fatura para a mesma competência. Se não existir, '
                    'cria o registro vinculado à instalação do usuário.',
                    """if _usuario_ja_tem_fatura_na_competencia(usuario.id, mes, state['edit_id']):
    ui.notify('Ja existe uma fatura cadastrada para essa competencia.', color='warning')
    return

instalacao = _obter_ou_criar_instalacao_manual(usuario.id)
Fatura.create(instalacao=instalacao, **payload)
ui.notify('Fatura salva com sucesso.', color='positive')""",
                )
                _evidence(
                    'Read: listar e selecionar faturas',
                    'src/ui/pages/cliente/faturas.py:115-121',
                    'A tela consulta as faturas do usuário logado e exibe os registros em ordem decrescente de criação, '
                    'mantendo cada cliente isolado dos dados de outros usuários.',
                    """def _listar_faturas_usuario(usuario_id: int) -> list[Fatura]:
    instalacoes_ids = InstalacaoSolar.select(InstalacaoSolar.id).where(InstalacaoSolar.usuario == usuario_id)
    return list(
        Fatura.select()
        .where(Fatura.instalacao.in_(instalacoes_ids))
        .order_by(Fatura.criado_em.desc())
    )""",
                )
                _evidence(
                    'Update: editar uma fatura existente',
                    'src/ui/pages/cliente/faturas.py:262-270',
                    'Quando existe um ID em edição, o sistema busca a fatura, atualiza os campos recebidos no formulário '
                    'e persiste a alteração com save().',
                    """if state['edit_id']:
    fatura = _obter_fatura_do_usuario(usuario.id, state['edit_id'])
    if not fatura:
        ui.notify('Fatura nao encontrada para edicao.', color='negative')
        return
    for field, value in payload.items():
        setattr(fatura, field, value)
    fatura.save()""",
                )
                _evidence(
                    'Delete: excluir uma fatura',
                    'src/ui/pages/cliente/faturas.py:294-302',
                    'A exclusão também valida se a fatura pertence ao usuário. Depois remove o registro, limpa o formulário, '
                    'recarrega a lista e mostra feedback visual.',
                    """fatura = _obter_fatura_do_usuario(usuario.id, fatura_id)
if not fatura:
    ui.notify('Fatura nao encontrada para exclusao.', color='negative')
    return

fatura.delete_instance()
limpar_formulario()
carregar_faturas()
ui.notify('Fatura excluida com sucesso.', color='positive')""",
                )

        with ui.column().classes('w-full items-center gap-10 py-24 px-6 bg-slate-50'):
            _anchor('algoritmos')
            _section_header(
                'Algoritmos aplicados',
                'A camada de dados resolve problemas práticos do domínio: localizar empresas no mapa, padronizar nomes '
                'inconsistentes da ANEEL e atualizar a base sem depender de trabalho manual.',
            )

            with ui.column().classes('w-full max-w-5xl gap-6'):
                _evidence(
                    'Geocoding com fallback',
                    'src/ui/pages/demo/mapa.py:767-799',
                    'Quando não há coordenada exata, o algoritmo tenta caminhos progressivamente menos precisos: CEP exato, '
                    'prefixo do CEP, bairro fallback, município e, por fim, None.',
                    """candidatos = bairros_por_cep_exato.get(municipio_codigo, {}).get(cep_digits, set())
if not candidatos and municipio_codigo and len(prefixo) >= 5:
    candidatos = bairros_por_prefixo.get(municipio_codigo, {}).get(prefixo[:5], set())

for feature in bairros:
    if feature['properties'].get('tipo') == 'bairro_fallback':
        c = _shape_centroid(feature['geometry'])
        if c:
            return c

return None, None""",
                )
                _evidence(
                    'Normalização de fabricantes',
                    'src/normalize.py:9-24, 687-690',
                    'A ANEEL traz nomes de fabricantes com muitas variações. O código limpa acentos, espaços e caixa alta '
                    'antes de aplicar sinônimos para exibir gráficos consistentes.',
                    """def _normalizar_str(value: str) -> str:
    value = _limpar(value)
    value = value.upper()
    value = _strip_accents(value)
    return value

def normalizar_modulo(value: str | None) -> str:
    return _normalizar_fabricante(value, _SINONIMOS_MODULO, _FABRICANTES_MODULO)""",
                )
                _evidence(
                    'Pipeline completo de dados',
                    'scripts/update_all.py',
                    'O projeto não depende de atualização manual. Um script orquestra a atualização da ANEEL, a geração '
                    'dos CSVs da RMR e o enriquecimento com CNPJ e geocodificação.',
                    """# Fluxo do update_all.py
1. update_aneel_data.py        # baixa e processa dados ANEEL
2. extract_aneel_rmr_csv.py    # gera CSVs filtrados da RMR
3. update_cnpj_enderecos.py    # consulta CNPJa, geocodifica e atualiza cache""",
                )
                _evidence(
                    'Execução sequencial com parada em erro',
                    'scripts/update_all.py:93-109',
                    'O orquestrador executa uma etapa por vez. Se uma etapa falha, ele para imediatamente para evitar '
                    'gerar arquivos inconsistentes ou seguir com dados incompletos.',
                    """code = _run('update_aneel_data.py', '1/3: Atualizacao ANEEL')
if code != 0:
    return code

code = _run('extract_aneel_rmr_csv.py', '2/3: Extracao CSVs RMR')
if code != 0:
    return code

if not args.skip_cnpj:
    code = _run('update_cnpj_enderecos.py', '3/3: Enriquecimento CNPJ')
    if code != 0:
        return code""",
                )

        with ui.column().classes('w-full items-center gap-10 py-24 px-6 bg-white'):
            _anchor('stack')
            _section_header(
                'Stack utilizada',
                'A implementação combina uma aplicação web em Python, banco SQLite, processamento analítico com Pandas, '
                'mapas interativos no navegador e autenticação externa com Firebase.',
            )

            with ui.grid(columns=3).classes('w-full max-w-5xl gap-5 max-[900px]:grid-cols-2 max-[650px]:grid-cols-1'):
                _stack_card(
                    'Python + NiceGUI',
                    'Base da aplicação web, rotas, interface e orquestração das telas.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg',
                )
                _stack_card(
                    'SQLite + Peewee',
                    'Banco local do MVP e ORM usado nos modelos de usuário, faturas, leads e cache CNPJ.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/sqlite/sqlite-original.svg',
                )
                _stack_card(
                    'Pandas + Parquet',
                    'Processamento dos dados da ANEEL e geração dos arquivos analíticos usados no mapa.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/pandas/pandas-original.svg',
                )
                _stack_card(
                    'Leaflet.js',
                    'Mapa interativo, camadas geográficas, heatmap por município e bairro, pins e popups.',
                    'https://leafletjs.com/docs/images/logo.png',
                )
                _stack_card(
                    'Chart.js',
                    'Gráficos do mapa: evolução temporal, fabricantes, classes, modalidades e PF/PJ.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/chartjs/chartjs-original.svg',
                )
                _stack_card(
                    'Firebase',
                    'Autenticação com Magic Link por e-mail e separação entre perfis B2C e B2B.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/firebase/firebase-plain.svg',
                )
                _stack_card(
                    'HTML, CSS e JavaScript',
                    'Assets públicos, mapa client-side, filtros, paginação e carregamento dos gráficos.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/javascript/javascript-original.svg',
                )
                _stack_card(
                    'Git + GitHub',
                    'Controle de versão, branches por melhoria e revisão via pull requests.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/git/git-original.svg',
                )
                _stack_card(
                    'Dados abertos e APIs',
                    'ANEEL, IBGE e Correios alimentam os dados. CNPJá e Nominatim enriquecem o mapa; ViaCEP e BrasilAPI apoiam cadastros.',
                    'https://cdn.jsdelivr.net/gh/devicons/devicon/icons/openapi/openapi-original.svg',
                )

        ui.label('').classes('h-16')
