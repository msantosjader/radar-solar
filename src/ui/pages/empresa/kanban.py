from __future__ import annotations

from datetime import datetime

from nicegui import ui

from src.models import InstalacaoSolar, Lead


STATUS_KANBAN = ['Novo', 'Em Contato', 'Concluído']


def _format_datetime_br(value: datetime | None) -> str:
    if value is None:
        return '-'
    return value.strftime('%d/%m/%Y as %H:%M')


def _normalizar_telefone_whatsapp(value: str | None) -> str | None:
    digits = ''.join(filter(str.isdigit, value or ''))
    if not digits:
        return None
    if len(digits) in (10, 11):
        digits = f'55{digits}'
    return digits


def _obter_instalacao_cliente(lead: Lead) -> InstalacaoSolar | None:
    if not lead.cliente_id:
        return None
    return InstalacaoSolar.select().where(InstalacaoSolar.usuario == lead.cliente_id).first()


def _obter_leads_por_status() -> dict[str, list[Lead]]:
    leads_por_status = {status: [] for status in STATUS_KANBAN}
    leads = (
        Lead.select()
        .where(Lead.status.in_(STATUS_KANBAN))
        .order_by(Lead.criado_em.desc())
    )
    for lead in leads:
        leads_por_status.setdefault(lead.status, []).append(lead)
    return leads_por_status


def _mudar_status(lead: Lead, novo_status: str) -> None:
    if novo_status not in STATUS_KANBAN:
        raise ValueError('Status invalido para o Kanban.')
    lead.status = novo_status
    lead.save()


def render_kanban() -> None:
    container = ui.column().classes('w-full gap-6 p-6')

    def renderizar() -> None:
        container.clear()
        leads_por_status = _obter_leads_por_status()
        total_leads = sum(len(leads) for leads in leads_por_status.values())

        with container:
            ui.label('Kanban de leads').classes('text-2xl font-bold text-slate-900')
            with ui.row().classes('w-full gap-4 max-[900px]:flex-col'):
                with ui.card().classes('flex-1 p-5 rounded-2xl'):
                    ui.label('Leads ativos').classes('text-sm text-slate-500')
                    ui.label(str(total_leads)).classes('text-3xl font-bold text-slate-900')
                for status in STATUS_KANBAN:
                    with ui.card().classes('flex-1 p-5 rounded-2xl'):
                        ui.label(status).classes('text-sm text-slate-500')
                        ui.label(str(len(leads_por_status[status]))).classes('text-3xl font-bold text-slate-900')

            if total_leads == 0:
                with ui.card().classes('w-full p-6 rounded-2xl border border-slate-200 bg-slate-50'):
                    ui.label('Nenhum lead ativo no momento.').classes('text-lg font-semibold text-slate-900')
                    ui.label(
                        'Quando um cliente solicitar contato pelo Dashboard B2C, a oportunidade aparecera aqui.'
                    ).classes('text-sm text-slate-600')
                return

            with ui.row().classes('w-full gap-4 items-start max-[1100px]:flex-col'):
                for status in STATUS_KANBAN:
                    with ui.column().classes('flex-1 min-w-0 gap-3 rounded-2xl bg-slate-100 p-4'):
                        ui.label(status).classes('text-lg font-bold text-slate-900')
                        ui.label(f'{len(leads_por_status[status])} oportunidade(s)').classes('text-xs text-slate-500')

                        for lead in leads_por_status[status]:
                            instalacao = _obter_instalacao_cliente(lead)
                            telefone_whatsapp = _normalizar_telefone_whatsapp(lead.telefone_contato)
                            localizacao = '-'
                            if instalacao:
                                cidade_uf = ' / '.join(
                                    part for part in [instalacao.cidade, instalacao.estado] if part
                                )
                                localizacao = cidade_uf or instalacao.cep or '-'

                            with ui.card().classes('w-full p-4 rounded-xl gap-3 bg-white border border-slate-200'):
                                with ui.row().classes('w-full items-start justify-between gap-2'):
                                    with ui.column().classes('gap-0 min-w-0'):
                                        ui.label(lead.nome_contato).classes('text-base font-semibold text-slate-900')
                                        ui.label(f'Solicitado em {_format_datetime_br(lead.criado_em)}').classes(
                                            'text-xs text-slate-500'
                                        )
                                    ui.label(f'#{lead.id}').classes('text-xs font-semibold text-slate-400')

                                ui.label(f'Local: {localizacao}').classes('text-sm text-slate-700')
                                if lead.telefone_contato:
                                    ui.label(f'Contato: {lead.telefone_contato}').classes('text-sm text-slate-700')
                                if lead.descricao_servico:
                                    ui.label(lead.descricao_servico).classes('text-sm text-slate-600 leading-6')

                                with ui.row().classes('w-full gap-2 flex-wrap'):
                                    if telefone_whatsapp:
                                        ui.button(
                                            'WhatsApp',
                                            on_click=lambda telefone=telefone_whatsapp: ui.navigate.to(
                                                f'https://wa.me/{telefone}', new_tab=True
                                            ),
                                        ).props('outline color=positive').classes('rounded-lg text-xs')

                                    for destino in STATUS_KANBAN:
                                        if destino == status:
                                            continue
                                        ui.button(
                                            destino,
                                            on_click=lambda lead=lead, destino=destino: mover_lead(lead, destino),
                                        ).props('flat color=primary').classes('rounded-lg text-xs')

    def mover_lead(lead: Lead, destino: str) -> None:
        try:
            _mudar_status(lead, destino)
        except ValueError as exc:
            ui.notify(str(exc), color='negative')
            return
        ui.notify(f'Lead #{lead.id} movido para {destino}.', color='positive')
        renderizar()

    renderizar()
