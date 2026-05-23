from nicegui import ui


def render_faturas() -> None:
    with ui.column().classes('w-full gap-6 p-6'):
        ui.label('Faturas').classes('text-2xl font-bold text-slate-900')
        with ui.card().classes('w-full p-6 rounded-2xl'):
            ui.label('Modulo em preparacao').classes('text-lg font-semibold text-slate-900')
            ui.label(
                'A insercao manual e a manutencao das faturas do cliente entram na proxima feature de CRUD.'
            ).classes('text-base text-slate-600 leading-7')
