from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from src.auth import PerfilConflitanteError, validar_email_para_profile
from src.database import db
from src.models import InstalacaoSolar, Lead, Usuario
from src.utils import _format_datetime_br, log_info, log_dados, log_ok


STATUS_KANBAN = ['Novo', 'Em Contato', 'Concluído']


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


def _obter_leads_por_status(empresa_id: int) -> dict[str, list[Lead]]:
    leads_por_status = {status: [] for status in STATUS_KANBAN}
    leads = (
        Lead.select()
        .where(
            (Lead.status.in_(STATUS_KANBAN))
            & ((Lead.empresa_responsavel.is_null(True)) | (Lead.empresa_responsavel == empresa_id))
        )
        .order_by(Lead.criado_em.desc())
    )
    for lead in leads:
        leads_por_status.setdefault(lead.status, []).append(lead)
    total = sum(len(v) for v in leads_por_status.values())
    log_dados(f'Kanban B2B: leads carregados para empresa {empresa_id}', total)
    return leads_por_status


def _mudar_status(lead: Lead, novo_status: str) -> None:
    if novo_status not in STATUS_KANBAN:
        raise ValueError('Status invalido para o Kanban.')
    lead.status = novo_status
    lead.save()
    log_ok(f'Kanban: lead #{lead.id} movido para {novo_status}')


def _obter_ou_criar_cliente_b2c(email: str, nome: str, telefone: str | None) -> tuple[Usuario, bool]:
    email = validar_email_para_profile(email, 'customer')
    usuario = Usuario.get_or_none(Usuario.email == email)
    if usuario:
        atualizado = False
        if nome and usuario.nome != nome:
            usuario.nome = nome
            atualizado = True
        if telefone and not usuario.telefone:
            usuario.telefone = telefone
            atualizado = True
        if atualizado:
            usuario.save()
        return usuario, False

    usuario = Usuario.create(
        firebase_uid=None,
        nome=nome or email.split('@', 1)[0],
        email=email,
        telefone=telefone,
        tipo_perfil='B2C',
    )
    return usuario, True


def _criar_lead_manual(
    empresa_id: int,
    email: str,
    nome: str,
    telefone: str | None,
    descricao: str | None,
) -> tuple[Lead, bool]:
    empresa = Usuario.get_by_id(empresa_id)
    with db.atomic():
        cliente, criado = _obter_ou_criar_cliente_b2c(email, nome, telefone)
        lead = Lead.create(
            cliente=cliente,
            empresa_responsavel=empresa,
            nome_contato=nome or cliente.nome,
            telefone_contato=telefone or cliente.telefone,
            origem='Kanban B2B - Lead manual',
            descricao_servico=descricao or 'Lead cadastrado manualmente pelo integrador.',
            status='Novo',
        )
    log_ok(f'Kanban: lead manual #{lead.id} criado (cliente: {email}, empresa: {empresa_id})')
    return lead, criado


def _render_formulario_lead(empresa_id: int, on_created: Callable[[], None]) -> None:
    with ui.card().classes('w-full rounded-2xl border border-slate-200 bg-white p-5 gap-4'):
        ui.label('Adicionar lead').classes('text-lg font-bold text-slate-900')
        ui.label(
            'Informe o e-mail do cliente. Se ele ainda nao existir, criaremos uma conta B2C para manter o vinculo.'
        ).classes('text-sm text-slate-600')
        with ui.row().classes('w-full gap-3 items-start max-[900px]:flex-col'):
            lead_email = ui.input('E-mail do cliente *').props('outlined').classes('flex-1 min-w-64')
            lead_nome = ui.input('Nome do contato').props('outlined').classes('flex-1 min-w-64')
            lead_telefone = ui.input('Telefone').props('outlined').classes('w-56 max-[900px]:w-full')
        lead_descricao = ui.textarea('Descricao / necessidade').props('outlined autogrow').classes('w-full')

        def adicionar_lead() -> None:
            email = str(lead_email.value or '').strip()
            nome = str(lead_nome.value or '').strip()
            telefone = str(lead_telefone.value or '').strip() or None
            descricao = str(lead_descricao.value or '').strip() or None
            if not email:
                ui.notify('Informe o e-mail do cliente.', color='warning')
                return
            try:
                lead, cliente_criado = _criar_lead_manual(empresa_id, email, nome, telefone, descricao)
            except PerfilConflitanteError as exc:
                ui.notify(str(exc), color='negative')
                return
            except Exception as exc:
                ui.notify(f'Nao foi possivel criar o lead: {exc}', color='negative')
                return
            acao_cliente = 'Cliente B2C criado e lead' if cliente_criado else 'Lead'
            ui.notify(f'{acao_cliente} #{lead.id} adicionado ao Kanban.', color='positive')
            on_created()

        ui.button('Adicionar lead', on_click=adicionar_lead).props('color=primary').classes('rounded-xl self-start')


def _render_resumo_kanban(leads_por_status: dict[str, list[Lead]]) -> int:
    total_leads = sum(len(leads) for leads in leads_por_status.values())
    with ui.row().classes('w-full gap-4 max-[900px]:flex-col'):
        with ui.card().classes('flex-1 p-5 rounded-2xl'):
            ui.label('Leads ativos').classes('text-sm text-slate-500')
            ui.label(str(total_leads)).classes('text-3xl font-bold text-slate-900')
        for status in STATUS_KANBAN:
            with ui.card().classes('flex-1 p-5 rounded-2xl'):
                ui.label(status).classes('text-sm text-slate-500')
                ui.label(str(len(leads_por_status[status]))).classes('text-3xl font-bold text-slate-900')
    return total_leads


def _render_empty_state() -> None:
    with ui.card().classes('w-full p-6 rounded-2xl border border-slate-200 bg-slate-50'):
        ui.label('Nenhum lead ativo no momento.').classes('text-lg font-semibold text-slate-900')
        ui.label(
            'Quando um cliente solicitar contato pelo Dashboard B2C, a oportunidade aparecera aqui.'
        ).classes('text-sm text-slate-600')


def _lead_localizacao(lead: Lead) -> str:
    instalacao = _obter_instalacao_cliente(lead)
    if not instalacao:
        return '-'
    cidade_uf = ' / '.join(part for part in [instalacao.cidade, instalacao.estado] if part)
    return cidade_uf or instalacao.cep or '-'


def _render_lead_card(lead: Lead, status: str, mover_lead: Callable[[Lead, str], None]) -> None:
    telefone_whatsapp = _normalizar_telefone_whatsapp(lead.telefone_contato)
    with ui.card().classes('w-full p-4 rounded-xl gap-3 bg-white border border-slate-200'):
        with ui.row().classes('w-full items-start justify-between gap-2'):
            with ui.column().classes('gap-0 min-w-0'):
                ui.label(lead.nome_contato).classes('text-base font-semibold text-slate-900')
                ui.label(f'Solicitado em {_format_datetime_br(lead.criado_em)}').classes('text-xs text-slate-500')
            ui.label(f'#{lead.id}').classes('text-xs font-semibold text-slate-400')

        ui.label(f'Local: {_lead_localizacao(lead)}').classes('text-sm text-slate-700')
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


def _render_colunas_kanban(
    leads_por_status: dict[str, list[Lead]],
    mover_lead: Callable[[Lead, str], None],
) -> None:
    with ui.row().classes('w-full gap-4 items-start max-[1100px]:flex-col'):
        for status in STATUS_KANBAN:
            with ui.column().classes('flex-1 min-w-0 gap-3 rounded-2xl bg-slate-100 p-4'):
                ui.label(status).classes('text-lg font-bold text-slate-900')
                ui.label(f'{len(leads_por_status[status])} oportunidade(s)').classes('text-xs text-slate-500')
                for lead in leads_por_status[status]:
                    _render_lead_card(lead, status, mover_lead)


def render_kanban(auth: dict) -> None:
    container = ui.column().classes('w-full gap-6 p-6')
    empresa_id = int(auth['usuario_id'])

    def renderizar() -> None:
        container.clear()
        leads_por_status = _obter_leads_por_status(empresa_id)

        with container:
            ui.label('Kanban de leads').classes('text-2xl font-bold text-slate-900')
            _render_formulario_lead(empresa_id, renderizar)
            total_leads = _render_resumo_kanban(leads_por_status)

            if total_leads == 0:
                _render_empty_state()
                return

            _render_colunas_kanban(leads_por_status, mover_lead)

    def mover_lead(lead: Lead, destino: str) -> None:
        try:
            _mudar_status(lead, destino)
        except ValueError as exc:
            ui.notify(str(exc), color='negative')
            return
        ui.notify(f'Lead #{lead.id} movido para {destino}.', color='positive')
        renderizar()

    renderizar()
