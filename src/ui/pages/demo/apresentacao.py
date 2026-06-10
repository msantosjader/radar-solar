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
                    'O dashboard compara a geração atual com a geração do mês anterior. Esse trecho usa variáveis '
                    'numéricas, operadores aritméticos e uma constante que representa a regra de negócio do alerta.',
                    """queda_percentual = ((anterior - atual) / anterior) * 100
if queda_percentual >= LIMIAR_QUEDA_GERACAO_PERCENT:
    alertas.append(
        f'Queda de geracao acima do limite: {_format_percent(queda_percentual)}'
    )""",
                )
                _evidence(
                    'Estrutura de decisão: if/else',
                    'src/auth.py:56-63',
                    'A autenticação bloqueia um e-mail que tente entrar com um perfil diferente do cadastrado. É um '
                    'exemplo direto de decisão condicional protegendo uma regra importante do sistema.',
                    """if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    perfil_existente = TIPO_TO_LABEL.get(usuario_existente.tipo_perfil, usuario_existente.tipo_perfil)
    perfil_solicitado = TIPO_TO_LABEL.get(tipo_perfil, tipo_perfil)
    raise PerfilConflitanteError(
        f'Este e-mail ja esta cadastrado como {perfil_existente}. '
        f'Para acessar como {perfil_solicitado}, use outro e-mail.'
    )""",
                )
                _evidence(
                    'Estrutura de repetição: for',
                    'src/ui/pages/demo/mapa.py:713-716',
                    'O mapa percorre instalações de empresas, limpa o CNPJ e só cria pin quando o valor tem 14 dígitos. '
                    'O registro não é apagado; ele apenas não entra nessa camada visual do mapa.',
                    """for inst in pjs:
    cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
    if len(cnpj) != 14:
        continue""",
                )
                _evidence(
                    'Repetição com retry',
                    'scripts/update_cnpj_enderecos.py:72-75',
                    'Quando a API CNPJá responde com rate limit, o script aguarda e tenta novamente. É uma repetição '
                    'controlada por recursão, usada para respeitar o limite da API.',
                    """if exc.code == 429:
    print(f'  Rate limited. Aguardando 60s...')
    time.sleep(60)
    return consultar_cnpja(cnpj)""",
                )
                _evidence(
                    'Listas e dicionários',
                    'src/ui/pages/demo/mapa.py:708-711, 739-758',
                    'Os pins exibidos no mapa são acumulados em uma lista. O cache de CNPJs é transformado em dicionário '
                    'para permitir consulta rápida pela chave do CNPJ.',
                    """pins: list[dict] = []
cnpj_cache: dict[str, CnpjCache] = {
    c.cnpj: c for c in CnpjCache.select()
}

pins.append({
    'codigo': inst['codigo'],
    'titular': inst['titular'],
    'cnpj': cnpj,
    'lat': float(lat),
    'lng': float(lng),
})""",
                )
                _evidence(
                    'Tuplas para coordenadas',
                    'src/ui/pages/demo/mapa.py:763-766',
                    'A função retorna latitude e longitude juntas. A anotação de tipo deixa claro que cada valor pode ser '
                    'numérico ou None, caso o algoritmo não encontre uma coordenada confiável.',
                    """def _estimar_coordenada_por_cep(
    municipio_codigo: str, cep_digits: str, prefixo: str,
    bairros_por_cep_exato: dict, bairros_por_prefixo: dict, data: dict,
) -> tuple[float | None, float | None]:""",
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

        ui.label('').classes('h-16')
