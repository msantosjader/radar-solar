import os
from pathlib import Path

from nicegui import app, ui

from src.models import criar_tabelas
from src.ui.layout import render_private_shell
from src.ui.pages.cliente.spa import render_cliente_spa
from src.ui.pages.demo.apresentacao import render_apresentacao
from src.ui.pages.demo.mapa import render_demo_mapa
from src.ui.pages.empresa.kanban import render_kanban
from src.ui.pages.empresa.mapa import render_mapa
from src.ui.pages.empresa.perfil import render_perfil_empresa
from src.ui.pages.public.auth_confirm import render_auth_confirm
from src.ui.pages.public.homepage import render_homepage
from src.ui.pages.public.login import render_login

# --- CONFIGURAÇÃO DE DIRETÓRIOS ESTÁTICOS ---
CURRENT_DIR = Path(__file__).parent
ASSETS_DIR = CURRENT_DIR / 'ui' / 'assets'
criar_tabelas()

# Adiciona a rota estática usando o caminho absoluto convertido em string
app.add_static_files('/assets', str(ASSETS_DIR))
app.add_static_files('/demo/static', str(CURRENT_DIR / 'ui' / 'pages' / 'demo' / 'static'))


def apply_theme() -> None:
    ui.colors(primary='#1D293B', secondary='#F97316', accent='#FFD700', dark='#0F172A')


def render_redirect(path: str, message: str = 'Redirecionando...') -> None:
    with ui.column().classes('w-full min-h-screen items-center justify-center gap-4'):
        ui.spinner(size='lg').classes('text-secondary')
        ui.label(message).classes('text-base text-slate-600')
    ui.timer(0.1, lambda: ui.navigate.to(path), once=True)


# --- ROTAS ---
@ui.page('/')
def home() -> None:
    apply_theme()  # Aplica o tema na homepage
    render_homepage()

@ui.page('/login')
def login(profile: str = 'customer') -> None:
    auth = app.storage.user.get('auth')
    if auth:
        apply_theme()
        render_redirect('/cliente/dashboard' if auth.get('profile') == 'customer' else '/empresa/mapa')
        return
    apply_theme()  # Aplica o tema na página de login
    render_login(profile)


@ui.page('/auth/confirm')
def auth_confirm() -> None:
    auth = app.storage.user.get('auth')
    if auth:
        apply_theme()
        render_redirect('/cliente/dashboard' if auth.get('profile') == 'customer' else '/empresa/mapa')
        return
    apply_theme()
    render_auth_confirm()


@ui.page('/demo/mapa')
def demo_mapa() -> None:
    apply_theme()
    render_demo_mapa()

@ui.page('/demo/apresentacao')
def demo_apresentacao() -> None:
    apply_theme()
    render_apresentacao()


@ui.page('/cliente/dashboard')
def cliente_dashboard() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'customer':
        apply_theme()
        render_redirect('/login?profile=customer')
        return
    apply_theme()
    render_cliente_spa(auth, 'dashboard')


@ui.page('/cliente/faturas')
def cliente_faturas() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'customer':
        apply_theme()
        render_redirect('/login?profile=customer')
        return
    apply_theme()
    render_cliente_spa(auth, 'faturas')


@ui.page('/cliente/perfil')
def cliente_perfil() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'customer':
        apply_theme()
        render_redirect('/login?profile=customer')
        return
    apply_theme()
    render_cliente_spa(auth, 'perfil')


@ui.page('/empresa/mapa')
def empresa_mapa() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'company':
        apply_theme()
        render_redirect('/login?profile=company')
        return
    apply_theme()
    render_private_shell(auth, '/empresa/mapa', 'Mapa do integrador', 'Concentracao de instalacoes e oportunidades.')
    render_mapa()


@ui.page('/empresa/perfil')
def empresa_perfil() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'company':
        apply_theme()
        render_redirect('/login?profile=company')
        return
    apply_theme()
    render_private_shell(auth, '/empresa/perfil', 'Perfil da empresa', 'Dados comerciais e regiao de atendimento.')
    render_perfil_empresa(auth)


@ui.page('/empresa/kanban')
def empresa_kanban() -> None:
    auth = app.storage.user.get('auth')
    if not auth or auth.get('profile') != 'company':
        apply_theme()
        render_redirect('/login?profile=company')
        return
    apply_theme()
    render_private_shell(auth, '/empresa/kanban', 'Kanban comercial', 'Acompanhamento do pipeline de atendimento.')
    render_kanban(auth)


@ui.page('/logout')
def logout() -> None:
    app.storage.user.pop('auth', None)
    apply_theme()
    render_redirect('/login', 'Saindo da conta...')


ui.run(
    title="Radar Solar - Inteligência Energética",
    port=8080,
    storage_secret=os.getenv('RADAR_SOLAR_STORAGE_SECRET', 'radar-solar-dev-storage-secret'),
)
