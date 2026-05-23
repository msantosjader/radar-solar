from nicegui import ui


def render_kanban() -> None:
    with ui.column().classes('w-full gap-6 p-6'):
        ui.label('Kanban de leads').classes('text-2xl font-bold text-slate-900')
        with ui.card().classes('w-full p-6 rounded-2xl'):
            ui.label('Modulo em preparacao').classes('text-lg font-semibold text-slate-900')
            ui.label(
                'A gestao detalhada do funil de atendimento do integrador entra na proxima etapa do produto.'
            ).classes('text-base text-slate-600 leading-7')
