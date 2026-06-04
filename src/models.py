from peewee import Model, CharField, FloatField, ForeignKeyField, DateTimeField, IntegerField, DateField
from datetime import datetime
from src.database import db


class BaseModel(Model):
    """Classe base com a conexão SQLite e campos automáticos de auditoria (DRY)"""
    criado_em = DateTimeField(default=datetime.now)
    atualizado_em = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        # Atualiza o carimbo de tempo automaticamente sempre que o registo for modificado
        self.atualizado_em = datetime.now()
        return super().save(*args, **kwargs)

    class Meta:
        database = db


class Usuario(BaseModel):
    firebase_uid = CharField(unique=True, null=True)
    nome = CharField()
    email = CharField(unique=True)
    cpf_cnpj = CharField(unique=True, null=True)
    telefone = CharField(null=True)
    tipo_perfil = CharField()  # 'B2C' (Cliente) ou 'B2B' (Empresa)


class EmpresaPerfil(BaseModel):
    usuario = ForeignKeyField(Usuario, backref='perfil_empresa', unique=True)
    nome_fantasia = CharField(null=True)
    email_comercial = CharField(null=True)
    cep = CharField(null=True)
    logradouro = CharField(null=True)
    numero = CharField(null=True)
    complemento = CharField(null=True)
    cidade = CharField(null=True)
    estado = CharField(max_length=2, null=True)


class InstalacaoSolar(BaseModel):
    usuario = ForeignKeyField(Usuario, backref='instalacoes')

    # Chaves de Identificação e Integração
    codigo_aneel = CharField(unique=True, null=True)  # CodEmpreendimento / CodGeracaoDistribuida
    conta_contrato_celpe = CharField(null=True)

    # Dados Comerciais e Tarifários (Mapeados do empreendimentos.csv)
    concessionaria = CharField(null=True)  # NomAgente
    classe_consumo = CharField(null=True)  # DscClasseConsumo
    subgrupo_tarifario = CharField(null=True)  # DscSubGrupoTarifario
    modalidade_geracao = CharField(null=True)  # DscModalidadeHabilitado
    qtd_ucs_recebem_credito = IntegerField(null=True)  # QtdUCRecebeCredito

    # Dados Técnicos de Geração (Mapeados do info-tecnica.csv)
    potencia_instalada_kwp = FloatField(null=True)  # MdaPotenciaInstalada
    potencia_modulos_kw = FloatField(null=True)  # MdaPotenciaModulos
    potencia_inversores_kw = FloatField(null=True)  # MdaPotenciaInversores
    qtd_modulos = IntegerField(null=True)  # QtdModulos
    area_arranjo_m2 = FloatField(null=True)  # MdaAreaArranjo

    fabricante_modulo = CharField(null=True)  # NomFabricanteModulo
    modelo_modulo = CharField(null=True)  # NomModeloModulo
    fabricante_inversor = CharField(null=True)  # NomFabricanteInversor
    modelo_inversor = CharField(null=True)  # NomModeloInversor

    data_conexao = DateField(null=True)  # DatConexao

    # Endereço e Geolocalização
    cep = CharField()
    logradouro = CharField()
    numero = CharField()
    complemento = CharField(null=True)
    cidade = CharField()
    estado = CharField(max_length=2)
    latitude = FloatField(null=True)  # NumCoordNEmpreendimento
    longitude = FloatField(null=True)  # NumCoordEEmpreendimento


class Fatura(BaseModel):
    instalacao = ForeignKeyField(InstalacaoSolar, backref='faturas')
    mes_referencia = CharField()
    consumo_kwh = FloatField()
    injecao_kwh = FloatField(null=True)
    creditos_utilizados = FloatField(null=True)
    saldo_creditos = FloatField(null=True)
    valor_fatura_rs = FloatField()
    geracao_app_kwh = FloatField(null=True)


class Lead(BaseModel):
    cliente = ForeignKeyField(Usuario, backref='leads_gerados', null=True)
    empresa_responsavel = ForeignKeyField(Usuario, backref='leads_capturados', null=True)
    nome_contato = CharField()
    telefone_contato = CharField(null=True)
    origem = CharField()
    descricao_servico = CharField(null=True)
    valor_estimado_rs = FloatField(null=True)
    status = CharField(default='Novo')


def criar_tabelas():
    """Executa a criação física das tabelas dentro do ficheiro SQLite"""
    with db:
        db.create_tables([Usuario, EmpresaPerfil, InstalacaoSolar, Fatura, Lead])
        migrar_lead_empresa_responsavel_nullable()


def migrar_lead_empresa_responsavel_nullable():
    """Permite que leads nasçam abertos, sem integrador responsável."""
    colunas = list(db.execute_sql("PRAGMA table_info('lead')"))
    empresa_coluna = next((coluna for coluna in colunas if coluna[1] == 'empresa_responsavel_id'), None)
    if not empresa_coluna or empresa_coluna[3] == 0:
        return

    with db.atomic():
        db.execute_sql('ALTER TABLE lead RENAME TO lead_old_empresa_not_null')
        db.create_tables([Lead])
        db.execute_sql('''
            INSERT INTO lead (
                id, criado_em, atualizado_em, cliente_id, empresa_responsavel_id,
                nome_contato, telefone_contato, origem, descricao_servico,
                valor_estimado_rs, status
            )
            SELECT
                id, criado_em, atualizado_em, cliente_id, empresa_responsavel_id,
                nome_contato, telefone_contato, origem, descricao_servico,
                valor_estimado_rs, status
            FROM lead_old_empresa_not_null
        ''')
        db.execute_sql('DROP TABLE lead_old_empresa_not_null')
