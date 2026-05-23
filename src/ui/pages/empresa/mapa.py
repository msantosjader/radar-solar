from nicegui import ui


def render_mapa() -> None:
    with ui.column().classes('w-full gap-6 p-6'):
        ui.label('Mapa de oportunidades').classes('text-2xl font-bold text-slate-900')
        with ui.row().classes('w-full gap-4'):
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Leads ativos').classes('text-sm text-slate-500')
                ui.label('12').classes('text-3xl font-bold text-slate-900')
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Instalacoes monitoradas').classes('text-sm text-slate-500')
                ui.label('248').classes('text-3xl font-bold text-slate-900')
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Prioridade atual').classes('text-sm text-slate-500')
                ui.label('Recife Norte').classes('text-3xl font-bold text-slate-900')

        with ui.card().classes('w-full p-6 rounded-2xl'):
            ui.label('Radar comercial').classes('text-lg font-semibold text-slate-900')
            ui.label(
                'Esta area sera a base do integrador para acompanhar concentracao de instalacoes, sinais de manutencao '
                'e conexoes com clientes da regiao.'
            ).classes('text-base text-slate-600 leading-7')
