from __future__ import annotations

from nicegui import ui

from src.ui.pages.public import inject_public_styles


def _section(title: str, subtitle: str = '') -> None:
    with ui.card().classes('w-full max-w-5xl mx-auto p-8 rounded-2xl shadow-lg border border-slate-200'):
        if title:
            ui.label(title).classes('text-2xl font-bold text-slate-900')
        if subtitle:
            ui.label(subtitle).classes('text-base text-slate-600 mt-1')


def _bullet(text: str, level: int = 0) -> None:
    prefix = '  ' * level + '• ' if level == 0 else '  ' * level + '— '
    ui.label(f'{prefix}{text}').classes('text-base text-slate-700 leading-relaxed')


def _code(lines: str) -> None:
    with ui.card().classes('w-full bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-sm leading-relaxed overflow-x-auto'):
        ui.label(lines.strip())


def _slide(title: str, subtitle: str = '', number: str = '') -> None:
    with ui.column().classes('w-full min-h-screen items-center justify-center p-8'):
        with ui.card().classes('w-full max-w-5xl p-10 rounded-3xl shadow-2xl border border-slate-200'):
            if number:
                ui.label(number).classes('text-sm font-bold text-secondary mb-2')
            ui.label(title).classes('text-3xl font-bold text-slate-900')
            if subtitle:
                ui.label(subtitle).classes('text-lg text-slate-500 mt-2')
            ui.separator().classes('my-6')


def _nav_bar() -> None:
    with ui.row().classes('w-full items-center justify-between px-6 py-3 bg-white border-b border-slate-200'):
        with ui.row().classes('items-center gap-3'):
            ui.image('/assets/images/logo_radarsolar.png').classes('w-8 h-8')
            ui.label('Radar Solar').classes('text-lg font-bold text-slate-900')
        with ui.row().classes('items-center gap-4'):
            ui.link('Inicio', '#inicio').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Problema', '#problema').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Solucao', '#solucao').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Funcionalidades', '#funcionalidades').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Ementa', '#ementa').classes('text-sm text-slate-600 hover:text-secondary no-underline')
            ui.link('Mapa', '/demo/mapa').classes('text-sm text-secondary font-semibold no-underline')
            ui.link('Entrar', '/login').classes('text-sm bg-secondary text-white px-4 py-1.5 rounded-full font-semibold no-underline hover:opacity-90')


def render_apresentacao() -> None:
    inject_public_styles()
    _nav_bar()

    with ui.column().classes('w-full bg-slate-50'):
        # ── Slide 1: Capa ──
        with ui.column().classes('w-full min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800'):
            with ui.column().classes('items-center gap-4 p-10'):
                ui.label('Radar Solar').classes('text-5xl font-bold text-white text-center')
                ui.label('Plataforma de inteligencia comercial para energia solar').classes('text-xl text-secondary text-center')
                ui.label('Projetos 1 — CESAR School 2026.1').classes('text-base text-slate-400 mt-4')
                ui.link('Iniciar apresentacao', '#problema').classes('mt-8 bg-secondary text-white px-6 py-2.5 rounded-full font-semibold no-underline hover:opacity-90')

        # ── Slide 2: Problema ──
        with _slide('O Problema', number='01'), ui.column().classes('w-full gap-3 mt-4'):
            _bullet('Clientes com energia solar nao tem visibilidade do proprio consumo e geracao')
            _bullet('Nao identificam quedas de performance no sistema fotovoltaico')
            _bullet('Integradores solares nao tem dados para direcionar prospeccao comercial')
            _bullet('Mercado solar pulverizado: ~15 mil instalacoes so na RMR sem geointeligencia')

        # ── Slide 3: Solucao ──
        with _slide('A Solucao', number='02'), ui.column().classes('w-full gap-3 mt-4'):
            _bullet('App web com dois perfis: Cliente (B2C) e Integrador (B2B)')
            _bullet('B2C: Dashboard com faturas, alertas de anomalia e solicitacao de manutencao')
            _bullet('B2B: Mapa de calor interativo com dados reais da ANEEL + pins de PJ')
            _bullet('Kanban de leads com arrastar e soltar: Novo → Em Contato → Concluido')
            _bullet('Tecnologias: NiceGUI + SQLite + Leaflet.js + Chart.js + Firebase')

        # ── Slide 4: Arquitetura ──
        with _slide('Arquitetura do Sistema', number='03'), ui.column().classes('w-full gap-2 mt-4'):
            _code("""main.py -> src.main
  src/
    database.py    SQLite + PRAGMA foreign_keys
    models.py      6 modelos (Usuario, InstalacaoSolar,
                   Fatura, Lead, EmpresaPerfil, CnpjCache)
    auth.py        Firebase Magic Link + perfil conflitante
    utils.py       Utilitarios compartilhados
    normalize.py   Normalizacao de ~370 fabricantes solares
    ui/pages/
      public/      Homepage, login, auth_confirm
      cliente/     Dashboard, faturas, perfil
      empresa/     Kanban, perfil, mapa (com leads)
      demo/        Mapa publico interativo

  scripts/
    update_all.py             Pipeline ANEEL -> CNPJ
    update_aneel_data.py      Download ANEEL + parquet
    update_cnpj_enderecos.py  Enriquecimento CNPJ
    init_db.py                Criacao das tabelas""")

        # ── Slide 5: Funcionalidades ──
        with _slide('Funcionalidades Implementadas', number='04'), ui.column().classes('w-full gap-3 mt-4'):
            with ui.grid(columns=2).classes('w-full gap-4'):
                feats = [
                    ('RF01', 'Login Firebase Magic Link'),
                    ('RF02', 'Mapa de calor ANEEL + graficos'),
                    ('RF03', 'Dashboard B2C com alertas'),
                    ('RF04', 'CRUD manual de faturas'),
                    ('RF05', 'Solicitacao de manutencao'),
                    ('RF06', 'Kanban B2B + WhatsApp'),
                    ('RF09', 'Pins CNPJ com geocoding real'),
                    ('—', 'Pipeline automatizado ANEEL'),
                ]
                for rid, rname in feats:
                    with ui.card().classes('p-4 rounded-xl border border-slate-200'):
                        ui.label(rid).classes('text-xs font-bold text-secondary')
                        ui.label(rname).classes('text-sm text-slate-700')

        # ── Slide 6: Ementa ──
        with _slide('Ementa: Estruturas Basicas', number='05'), ui.column().classes('w-full gap-3 mt-4'):
            _bullet('Variaveis e tipos: models.py, dashboard.py (queda_percentual)')
            _bullet('if/elif/else: bloqueio de perfil conflitante (auth.py:56)')
            _bullet('while (indireto): retry rate limit via recursao (cnpj_enderecos.py:72)')
            _bullet('for: iteracao em instalacoes (mapa.py:713), linhas CSV (cnpj_enderecos.py:51)')
            _bullet('Listas: pins.append({...}), list comprehensions (normalize.py:27)')
            _bullet('Dicionarios: RMR_MUNICIPIOS, dict comprehension CnpjCache (mapa.py:709)')
            _bullet('Tuplas: coordenadas tuple[float, float] (mapa.py:763)')
            _bullet('Funcoes: modularizacao em normalize.py, auth.py, utils.py')

        # ── Slide 7: Ementa 2 ──
        with _slide('Ementa: Funcoes, Modulos, Boas Praticas', number='06'), ui.column().classes('w-full gap-3 mt-4'):
            _bullet('Decomposicao: carregar_pjs_mapa() quebra em 5 subproblemas (mapa.py:702)')
            _bullet('Reuso: src.normalize importado por mapa.py; src.utils compartilhado')
            _bullet('Refatoracao: mapa.py reduziu de 2.184 para 1.028 linhas')
            _bullet('Legibilidade: nomes descritivos, type hints em todas as funcoes')
            _bullet('Constantes nomeadas: LIMIAR_QUEDA_GERACAO_PERCENT (20%), STATUS_KANBAN')
            _bullet('Tratamento de erros: try/except em APIs (CNPJa, Nominatim, ViaCEP)')
            _bullet('Arquivos: leitura/escrita de CSV, parquet, shapefile, JSON')

        # ── Slide 8: Algoritmos ──
        with _slide('Ementa: Algoritmos Aplicados', number='07'), ui.column().classes('w-full gap-3 mt-4'):
            ui.label('Geocoding com fallback (mapa.py:763)').classes('text-base font-semibold text-slate-900 mt-2')
            _bullet('1. CEP exato → bairro no shapefile', level=1)
            _bullet('2. Prefixo CEP (5 digitos) → bairro', level=1)
            _bullet('3. Centroide do bairro fallback', level=1)
            _bullet('4. Centroide do municipio', level=1)
            _bullet('5. (None, None) se nada funcionar', level=1)
            ui.label('Normalizacao de fabricantes (normalize.py:32-686)').classes('text-base font-semibold text-slate-900 mt-4')
            _bullet('~370 sinonimos de modulos e inversores', level=1)
            _bullet('Normalizacao: upper case, remocao de acentos', level=1)
            _bullet('Busca prefixada + similaridade fuzzy (difflib)', level=1)

        # ── Slide 9: Demo ──
        with ui.column().classes('w-full min-h-screen items-center justify-center bg-slate-900'):
            with ui.column().classes('items-center gap-6 p-10'):
                ui.label('Demonstracao ao Vivo').classes('text-3xl font-bold text-white')
                with ui.column().classes('items-start gap-3'):
                    for passo in [
                        '1. Landing page e login com Facebook Magic Link',
                        '2. Dashboard B2C: faturas, alertas, solicitacao',
                        '3. Kanban B2B: leads, arrastar e soltar, WhatsApp',
                        '4. Mapa de calor: zoom RMR, filtros, graficos',
                        '5. Pins CNPJ com dados reais da Receita',
                    ]:
                        ui.label(passo).classes('text-lg text-slate-300')
                ui.separator().classes('w-32 my-4')
                ui.label('Acesse o mapa agora:').classes('text-sm text-slate-400')
                ui.link('/demo/mapa', '/demo/mapa').classes('bg-secondary text-white px-8 py-3 rounded-full text-lg font-semibold no-underline hover:opacity-90')

        # ── Slide 10: Obrigado ──
        with ui.column().classes('w-full min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800'):
            with ui.column().classes('items-center gap-4'):
                ui.label('Obrigado!').classes('text-5xl font-bold text-white')
                ui.html('<div class="w-24 h-1 bg-secondary rounded-full"></div>')
                ui.label('Jader Santos').classes('text-xl text-slate-300 mt-4')
                ui.label('github.com/msantosjader/radar-solar').classes('text-base text-secondary')

        # ── Footer spacer ──
        ui.label('').classes('h-16')
