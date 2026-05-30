from __future__ import annotations

from datetime import datetime

from nicegui import ui
from src.models import Fatura, InstalacaoSolar, Usuario


LIMIAR_QUEDA_GERACAO_PERCENT = 20.0
LIMIAR_DIFERENCA_GERACAO_INJECAO_PERCENT = 35.0


def _format_kwh(value: float | None) -> str:
    if value is None:
        return '-'
    return f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + ' kWh'


def _format_percent(value: float) -> str:
    return f'{value:.1f}%'.replace('.', ',')


def _obter_faturas_usuario(usuario_id: int) -> list[Fatura]:
    instalacoes_ids = (
        InstalacaoSolar.select(InstalacaoSolar.id)
        .where(InstalacaoSolar.usuario == usuario_id)
    )
    return list(
        Fatura.select()
        .where(Fatura.instalacao.in_(instalacoes_ids))
        .order_by(Fatura.criado_em.desc())
    )


def _avaliar_alertas(faturas: list[Fatura]) -> tuple[list[str], list[str]]:
    alertas: list[str] = []
    status: list[str] = []

    if len(faturas) < 2:
        status.append('Sem historico suficiente para validar tendencia de geracao (minimo de 2 faturas).')
    else:
        atual = faturas[0].geracao_app_kwh
        anterior = faturas[1].geracao_app_kwh
        if atual is None or anterior is None or anterior <= 0:
            status.append('Sem dados de geracao completos para comparar com o mes anterior.')
        else:
            queda_percentual = ((anterior - atual) / anterior) * 100
            if queda_percentual >= LIMIAR_QUEDA_GERACAO_PERCENT:
                alertas.append(
                    f'Queda de geracao acima do limite: {_format_percent(queda_percentual)} em relacao ao mes anterior.'
                )
            else:
                status.append(
                    f'Geracao dentro da faixa esperada: variacao de {_format_percent(queda_percentual)} frente ao mes anterior.'
                )

    fatura_atual = faturas[0] if faturas else None
    if fatura_atual and fatura_atual.geracao_app_kwh and fatura_atual.geracao_app_kwh > 0 and fatura_atual.injecao_kwh is not None:
        diferenca = abs(fatura_atual.geracao_app_kwh - fatura_atual.injecao_kwh)
        percentual_diferenca = (diferenca / fatura_atual.geracao_app_kwh) * 100
        if percentual_diferenca >= LIMIAR_DIFERENCA_GERACAO_INJECAO_PERCENT:
            alertas.append(
                f'Diferenca elevada entre geracao e injecao: {_format_percent(percentual_diferenca)} no mes atual.'
            )
        else:
            status.append(
                f'Proporcao geracao x injecao sem desvio critico ({_format_percent(percentual_diferenca)} de diferenca).'
            )
    else:
        status.append('Sem dados suficientes para avaliar a diferenca entre geracao e injecao.')

    return alertas, status


def _gerar_dados_grafico(faturas: list[Fatura], limite: int = 6) -> tuple[list[str], list[float], list[float], list[float]]:
    def chave_mes_referencia(fatura: Fatura) -> datetime:
        try:
            return datetime.strptime(fatura.mes_referencia, '%m/%Y')
        except (TypeError, ValueError):
            return fatura.criado_em

    ordenadas = sorted(faturas, key=chave_mes_referencia)
    recorte = ordenadas[-limite:]
    labels = [f.mes_referencia for f in recorte]
    consumo = [round(f.consumo_kwh or 0, 2) for f in recorte]
    injecao = [round(f.injecao_kwh or 0, 2) for f in recorte]
    geracao = [round(f.geracao_app_kwh or 0, 2) for f in recorte]
    return labels, consumo, injecao, geracao


def render_dashboard(auth: dict) -> None:
    usuario = Usuario.get_or_none(Usuario.id == auth.get('usuario_id'))

    with ui.column().classes('w-full gap-6 p-6'):
        ui.label('Dashboard B2C').classes('text-2xl font-bold text-slate-900')

        if not usuario:
            with ui.card().classes('w-full p-6 rounded-2xl'):
                ui.label('Nao foi possivel carregar o usuario autenticado.').classes('text-base text-red-600')
            return

        faturas = _obter_faturas_usuario(usuario.id)
        fatura_atual = faturas[0] if faturas else None

        if not fatura_atual:
            with ui.card().classes('w-full p-6 rounded-2xl'):
                ui.label('Voce ainda nao possui faturas cadastradas.').classes('text-lg font-semibold text-slate-900')
                ui.label('Acesse o modulo de faturas para inserir seus dados e habilitar este dashboard.').classes(
                    'text-sm text-slate-600'
                )
            return

        with ui.row().classes('w-full gap-4 max-[1100px]:flex-col'):
            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Consumo').classes('text-sm text-slate-500')
                ui.label(_format_kwh(fatura_atual.consumo_kwh)).classes('text-3xl font-bold text-slate-900')
                ui.label(f'Mes {fatura_atual.mes_referencia}').classes('text-xs text-slate-500')

            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Injecao na rede').classes('text-sm text-slate-500')
                ui.label(_format_kwh(fatura_atual.injecao_kwh)).classes('text-3xl font-bold text-slate-900')
                ui.label('Energia devolvida para compensacao').classes('text-xs text-slate-500')

            with ui.card().classes('flex-1 p-6 rounded-2xl'):
                ui.label('Saldo de creditos').classes('text-sm text-slate-500')
                ui.label(_format_kwh(fatura_atual.saldo_creditos)).classes('text-3xl font-bold text-slate-900')
                ui.label('Saldo acumulado na fatura').classes('text-xs text-slate-500')

        labels, consumo_hist, injecao_hist, geracao_hist = _gerar_dados_grafico(faturas)
        with ui.card().classes('w-full p-6 rounded-2xl'):
            ui.label('Historico recente da fatura').classes('text-lg font-semibold text-slate-900')
            ui.label('Comparativo dos ultimos meses entre consumo, injecao e geracao.').classes(
                'text-sm text-slate-600'
            )
            ui.echart({
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': ['Consumo', 'Injecao', 'Geracao']},
                'xAxis': {'type': 'category', 'data': labels},
                'yAxis': {'type': 'value', 'name': 'kWh'},
                'series': [
                    {'name': 'Consumo', 'type': 'bar', 'data': consumo_hist, 'itemStyle': {'color': '#1D4ED8'}},
                    {'name': 'Injecao', 'type': 'bar', 'data': injecao_hist, 'itemStyle': {'color': '#0D9488'}},
                    {'name': 'Geracao', 'type': 'line', 'data': geracao_hist, 'smooth': True, 'itemStyle': {'color': '#EA580C'}},
                ],
            }).classes('w-full h-96')

        alertas, status_operacao = _avaliar_alertas(faturas)
        houve_alerta = len(alertas) > 0
        classes_alerta = 'w-full p-6 rounded-2xl border-2 '
        if houve_alerta:
            classes_alerta += 'bg-red-50 border-red-300'
            cor_texto = 'text-red-700'
            titulo_alerta = 'Alerta visual de anomalia'
        else:
            classes_alerta += 'bg-emerald-50 border-emerald-300'
            cor_texto = 'text-emerald-700'
            titulo_alerta = 'Status da geracao'

        with ui.card().classes(classes_alerta):
            ui.label(titulo_alerta).classes(f'text-lg font-semibold {cor_texto}')
            for alerta in alertas:
                ui.label(f'- {alerta}').classes(f'text-sm {cor_texto}')
            for status in status_operacao:
                ui.label(f'- {status}').classes(f'text-sm {cor_texto}')

        with ui.card().classes('w-full p-6 rounded-2xl border border-slate-200 bg-slate-50'):
            ui.label('Regras de alerta em uso (temporario)').classes('text-base font-semibold text-slate-900')
            ui.label(
                f'- Regra 1: queda de geracao >= {_format_percent(LIMIAR_QUEDA_GERACAO_PERCENT)} versus mes anterior gera alerta.'
            ).classes('text-sm text-slate-700')
            ui.label(
                f'- Regra 2: diferenca entre geracao e injecao >= {_format_percent(LIMIAR_DIFERENCA_GERACAO_INJECAO_PERCENT)} no mes atual gera alerta.'
            ).classes('text-sm text-slate-700')
            ui.label('- Sem historico/dados suficientes: sistema informa status sem disparar falso positivo.').classes('text-sm text-slate-700')
