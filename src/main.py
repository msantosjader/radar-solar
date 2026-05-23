from pathlib import Path
from nicegui import app, ui

from src.ui.pages.public.homepage import render_homepage
from src.ui.pages.public.login import render_login

# --- CONFIGURAÇÃO DE DIRETÓRIOS ESTÁTICOS ---
CURRENT_DIR = Path(__file__).parent
ASSETS_DIR = CURRENT_DIR / 'ui' / 'assets'

# Adiciona a rota estática usando o caminho absoluto convertido em string
app.add_static_files('/assets', str(ASSETS_DIR))

def apply_theme():
    ui.colors(primary='#1D293B', secondary='#F97316', accent='#FFD700', dark='#0F172A')


# --- ROTAS ---
@ui.page('/')
def home():
    apply_theme() # Aplica o tema na homepage
    render_homepage()

@ui.page('/login')
def login(profile: str = 'customer'):
    apply_theme() # Aplica o tema na página de login
    render_login(profile)

ui.run(title="Radar Solar - Inteligência Energética", port=8080)
