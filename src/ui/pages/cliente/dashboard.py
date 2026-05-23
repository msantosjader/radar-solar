from nicegui import ui


def render_dashboard() -> None:
    with ui.column().classes('w-full gap-6 p-6'):
        ui.label('Visao geral da usina').classes('text-2xl font-bold text-slate-900')
        with ui.row().classes('w-full gap-4'):
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Geracao do mes').classes('text-sm text-slate-500')
                ui.label('1.248 kWh').classes('text-3xl font-bold text-slate-900')
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Saldo de creditos').classes('text-sm text-slate-500')
                ui.label('182 kWh').classes('text-3xl font-bold text-slate-900')
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Status da usina').classes('text-sm text-slate-500')
                ui.label('Operando com alerta').classes('text-3xl font-bold text-orange-500')

        with ui.card().classes('w-full p-6 rounded-2xl'):
            ui.label('Resumo').classes('text-lg font-semibold text-slate-900')
            ui.label(
                'Este espaco sera a entrada do microgerador para acompanhar a geracao, a compensacao e sinais '
                'de inconsistencias na conta de luz.'
            ).classes('text-base text-slate-600 leading-7')
