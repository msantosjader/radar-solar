from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pandas as pd
import shapefile
from nicegui import ui


RMR_MUNICIPIOS = {
    '2600054',  # Abreu e Lima
    '2601052',  # Aracoiaba
    '2602902',  # Cabo de Santo Agostinho
    '2603454',  # Camaragibe
    '2606804',  # Igarassu
    '2607208',  # Ipojuca
    '2607604',  # Ilha de Itamaraca
    '2607752',  # Itapissuma
    '2607901',  # Jaboatao dos Guararapes
    '2609402',  # Moreno
    '2609600',  # Olinda
    '2610707',  # Paulista
    '2611606',  # Recife
    '2613701',  # Sao Lourenco da Mata
}

ROOT_DIR = Path(__file__).resolve().parents[4]
MUNICIPIOS_SHP = ROOT_DIR / 'data/raw/ibge/PE_Municipios_2024/PE_Municipios_2024.shp'
BAIRROS_SHP = ROOT_DIR / 'data/raw/ibge/PE_bairros_CD2022/PE_bairros_CD2022.shp'
INSTALACOES_PARQUET = ROOT_DIR / 'data/processed/aneel/rmr_instalacoes.parquet'
DNE_DIR = ROOT_DIR / 'data/raw/correios/eDNE_Basico_26031/Delimitado'
CEP_PE_XLSX = ROOT_DIR / 'data/raw/CEP_PE.xlsx'
EMPREENDIMENTOS_CSV = ROOT_DIR / 'data/processed/aneel/empreendimento-geracao-distribuida-rmr.csv'


def _feature(geometry: dict, properties: dict) -> dict:
    return {
        'type': 'Feature',
        'geometry': geometry,
        'properties': properties,
    }


def _feature_collection(features: list[dict]) -> dict:
    return {
        'type': 'FeatureCollection',
        'features': features,
    }


def _number(value: object) -> float:
    if pd.isna(value):
        return 0.0
    return float(value)


def _text(value: object) -> str:
    if pd.isna(value):
        return ''
    return str(value)


def _date_br(value: object) -> str:
    if pd.isna(value):
        return ''
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return str(value)
    return parsed.strftime('%d/%m/%Y')


@lru_cache(maxsize=1)
def carregar_dados_titular() -> dict[str, dict]:
    if not EMPREENDIMENTOS_CSV.exists():
        return {}

    colunas = ['CodEmpreendimento', 'NumCPFCNPJ', 'NomTitularEmpreendimento', 'DscModalidadeHabilitado']
    df = pd.read_csv(EMPREENDIMENTOS_CSV, sep=';', encoding='latin1', usecols=colunas)
    return {
        _text(row.CodEmpreendimento): {
            'cpf_cnpj': _text(row.NumCPFCNPJ),
            'titular': _text(row.NomTitularEmpreendimento),
            'modalidade_habilitado': _text(row.DscModalidadeHabilitado),
        }
        for row in df.itertuples(index=False)
    }


def _norm(value: str) -> str:
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(value.upper().split())


def _bairro_key(value: str) -> str:
    conectores = {'DA', 'DE', 'DI', 'DO', 'DAS', 'DOS'}
    return ' '.join(part for part in _norm(value).split() if part not in conectores)


def _read_dne_rows(path: Path):
    with path.open('r', encoding='latin1', errors='replace') as file:
        for line in file:
            yield line.rstrip('\n').split('@')


@lru_cache(maxsize=1)
def carregar_bairros_por_cep() -> tuple[dict[str, dict[str, set[str]]], dict[str, dict[str, set[str]]]]:
    if CEP_PE_XLSX.exists():
        localidades = pd.read_excel(CEP_PE_XLSX, sheet_name='LOG_LOCALIDADE')
        localidades = localidades.dropna(subset=['MUN_NU'])
        municipio_por_loc_nu = {
            int(row.LOC_NU): str(int(row.MUN_NU))
            for row in localidades.itertuples(index=False)
            if str(int(row.MUN_NU)) in RMR_MUNICIPIOS
        }

        cep_bairro = pd.read_excel(CEP_PE_XLSX, sheet_name='CEP_BAIRRO')
        bairros_por_cep_exato: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        bairros_por_prefixo: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for row in cep_bairro.itertuples(index=False):
            municipio_codigo = municipio_por_loc_nu.get(int(row.LOC_NU))
            if not municipio_codigo or pd.isna(row.BAIRRO):
                continue
            for cep in range(int(row.CEP_INICIO), int(row.CEP_FIM) + 1):
                bairros_por_cep_exato[municipio_codigo][f'{cep:08d}'].add(str(row.BAIRRO))
            mascara_inicio = int(row.MASCARA_INICIO) // 1000
            mascara_fim = int(row.MASCARA_FIM) // 1000
            for prefixo in range(mascara_inicio, mascara_fim + 1):
                bairros_por_prefixo[municipio_codigo][f'{prefixo:05d}'].add(str(row.BAIRRO))

        return (
            {
                municipio: {cep: set(bairros) for cep, bairros in ceps.items()}
                for municipio, ceps in bairros_por_cep_exato.items()
            },
            {
                municipio: {prefixo: set(bairros) for prefixo, bairros in prefixos.items()}
                for municipio, prefixos in bairros_por_prefixo.items()
            },
        )

    localidades_rmr = {}
    for row in _read_dne_rows(DNE_DIR / 'LOG_LOCALIDADE.TXT'):
        if len(row) < 8 or row[1] != 'PE' or row[7] not in RMR_MUNICIPIOS:
            continue
        localidades_rmr[row[0]] = row[7]

    bairros_por_id = {}
    for row in _read_dne_rows(DNE_DIR / 'LOG_BAIRRO.TXT'):
        if len(row) < 4 or row[2] not in localidades_rmr:
            continue
        bairros_por_id[row[0]] = {
            'municipio_codigo': localidades_rmr[row[2]],
            'nome': row[3],
        }

    bairros_por_prefixo: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    def add_prefixo(bairro_id: str, cep_inicio: str, cep_fim: str | None = None) -> None:
        bairro = bairros_por_id.get(bairro_id)
        if not bairro or not cep_inicio.isdigit():
            return
        cep_fim = cep_fim if cep_fim and cep_fim.isdigit() else cep_inicio
        inicio = int(cep_inicio) // 1000
        fim = int(cep_fim) // 1000
        for prefixo in range(inicio, fim + 1):
            bairros_por_prefixo[bairro['municipio_codigo']][f'{prefixo:05d}'].add(bairro['nome'])

    for row in _read_dne_rows(DNE_DIR / 'LOG_FAIXA_BAIRRO.TXT'):
        if len(row) >= 3:
            add_prefixo(row[0], row[1], row[2])

    for row in _read_dne_rows(DNE_DIR / 'LOG_LOGRADOURO_PE.TXT'):
        if len(row) >= 8:
            add_prefixo(row[3], row[7])

    return (
        {},
        {
            municipio: {prefixo: set(bairros) for prefixo, bairros in prefixos.items()}
            for municipio, prefixos in bairros_por_prefixo.items()
        },
    )


@lru_cache(maxsize=1)
def carregar_instalacoes_aneel() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    dados_titular = carregar_dados_titular()
    colunas = [
        'municipio',
        'cod_municipio_ibge',
        'cod_empreendimento',
        'tipo_consumidor',
        'classe_consumo',
        'porte',
        'data_conexao',
        'potencia_kw',
        'qtd_modulos',
        'bairro_estimado',
        'cep_original',
        'cep_prefixo',
    ]
    df = pd.read_parquet(INSTALACOES_PARQUET, columns=colunas)
    df['potencia_kw'] = pd.to_numeric(df['potencia_kw'], errors='coerce').fillna(0)
    df['qtd_modulos'] = pd.to_numeric(df['qtd_modulos'], errors='coerce').fillna(0)

    agregados = {}
    instalacoes_por_municipio = {}
    for municipio, grupo in df.groupby('municipio', sort=True):
        agregados[municipio] = {
            'qtd_instalacoes': int(len(grupo)),
            'potencia_kw': round(float(grupo['potencia_kw'].sum()), 2),
            'qtd_modulos': int(grupo['qtd_modulos'].sum()),
        }
        grupo_ordenado = grupo.sort_values(['potencia_kw', 'data_conexao'], ascending=[False, False])
        instalacoes = []
        for row in grupo_ordenado.itertuples(index=False):
            codigo = _text(row.cod_empreendimento)
            dados_extra = dados_titular.get(codigo, {})
            instalacoes.append({
                'codigo': _text(row.cod_empreendimento),
                'cpf_cnpj': dados_extra.get('cpf_cnpj', ''),
                'titular': dados_extra.get('titular', ''),
                'modalidade_habilitado': dados_extra.get('modalidade_habilitado') or _text(row.modalidade),
                'municipio': _text(row.municipio),
                'municipio_codigo': _text(row.cod_municipio_ibge),
                'bairro': _text(row.bairro_estimado) or 'Nao identificado',
                'classe': _text(row.classe_consumo),
                'tipo': _text(row.tipo_consumidor),
                'porte': _text(row.porte),
                'data_conexao': _date_br(row.data_conexao),
                'potencia_kw': round(_number(row.potencia_kw), 2),
                'qtd_modulos': int(_number(row.qtd_modulos)),
                'cep': _text(row.cep_original),
                'cep_prefixo': _text(row.cep_prefixo),
            })
        instalacoes_por_municipio[municipio] = instalacoes

    return agregados, instalacoes_por_municipio


@lru_cache(maxsize=1)
def carregar_geojson_rmr() -> dict:
    agregados_aneel, instalacoes_por_municipio = carregar_instalacoes_aneel()
    bairros_por_cep_exato, bairros_por_prefixo = carregar_bairros_por_cep()
    municipios = []
    municipios_por_codigo = {}

    municipio_reader = shapefile.Reader(str(MUNICIPIOS_SHP), encoding='cp1252')
    for shape_record in municipio_reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        codigo_municipio = record['CD_MUN']
        if codigo_municipio not in RMR_MUNICIPIOS:
            continue
        nome_municipio = record['NM_MUN']
        metricas = agregados_aneel.get(
            nome_municipio,
            {'qtd_instalacoes': 0, 'potencia_kw': 0.0, 'qtd_modulos': 0},
        )

        feature = _feature(
            shape_record.shape.__geo_interface__,
            {
                'codigo': codigo_municipio,
                'nome': nome_municipio,
                'tipo': 'municipio',
                'metricas': metricas,
            },
        )
        municipios.append(feature)
        municipios_por_codigo[codigo_municipio] = feature

    bairros_por_municipio: dict[str, list[dict]] = {codigo: [] for codigo in RMR_MUNICIPIOS}
    bairro_reader = shapefile.Reader(str(BAIRROS_SHP), encoding='utf-8')
    for shape_record in bairro_reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        codigo_municipio = record['CD_MUN']
        if codigo_municipio not in RMR_MUNICIPIOS:
            continue

        bairros_por_municipio[codigo_municipio].append(
            _feature(
                shape_record.shape.__geo_interface__,
                {
                    'codigo': record['CD_BAIRRO'],
                    'nome': record['NM_BAIRRO'],
                    'municipio_codigo': codigo_municipio,
                    'municipio_nome': record['NM_MUN'],
                    'tipo': 'bairro',
                },
            )
        )

    for codigo_municipio, bairros in bairros_por_municipio.items():
        if bairros or codigo_municipio not in municipios_por_codigo:
            continue

        municipio = municipios_por_codigo[codigo_municipio]
        bairros.append(
            _feature(
                municipio['geometry'],
                {
                    'codigo': f'{codigo_municipio}-sem-bairros',
                    'nome': municipio['properties']['nome'],
                    'municipio_codigo': codigo_municipio,
                    'municipio_nome': municipio['properties']['nome'],
                    'tipo': 'bairro_fallback',
                },
            )
        )

    municipios.sort(key=lambda item: item['properties']['nome'])
    for bairros in bairros_por_municipio.values():
        bairros.sort(key=lambda item: item['properties']['nome'])

    bairros_validos_por_municipio = {
        codigo: {
            _bairro_key(feature['properties']['nome']): feature['properties']['nome']
            for feature in features
            if feature['properties']['tipo'] == 'bairro'
        }
        for codigo, features in bairros_por_municipio.items()
    }
    bairro_metricas: dict[str, dict[str, dict]] = {codigo: {} for codigo in RMR_MUNICIPIOS}

    for municipio_nome, instalacoes in instalacoes_por_municipio.items():
        municipio = next((item for item in municipios if item['properties']['nome'] == municipio_nome), None)
        if not municipio:
            continue
        municipio_codigo = municipio['properties']['codigo']
        bairros_validos = bairros_validos_por_municipio.get(municipio_codigo, {})
        ceps_exatos_municipio = bairros_por_cep_exato.get(municipio_codigo, {})
        prefixos_municipio = bairros_por_prefixo.get(municipio_codigo, {})
        fallback_nome = municipio['properties']['nome'] if not bairros_validos else 'Nao identificado'

        for instalacao in instalacoes:
            cep_original = instalacao['cep']
            cep_mascarado = '***' in cep_original
            cep_exato = ''.join(char for char in cep_original if char.isdigit()) if not cep_mascarado else ''
            candidatos_dne = ceps_exatos_municipio.get(cep_exato, set()) if len(cep_exato) == 8 else set()
            if not candidatos_dne and cep_mascarado:
                candidatos_dne = prefixos_municipio.get(instalacao['cep_prefixo'], set())
            bairros_possiveis = sorted(
                {
                    bairros_validos[_bairro_key(nome)]
                    for nome in candidatos_dne
                    if _bairro_key(nome) in bairros_validos
                }
            )

            bairro_estimado_key = _bairro_key(instalacao['bairro'])
            if not bairros_possiveis and bairro_estimado_key in bairros_validos:
                bairros_possiveis = [bairros_validos[bairro_estimado_key]]

            if not bairros_possiveis:
                bairros_possiveis = [fallback_nome]

            instalacao['bairros_possiveis'] = bairros_possiveis
            peso = 1 / len(bairros_possiveis)
            for bairro_nome in bairros_possiveis:
                metricas = bairro_metricas[municipio_codigo].setdefault(
                    bairro_nome,
                    {'qtd_instalacoes': 0.0, 'potencia_kw': 0.0, 'qtd_modulos': 0.0},
                )
                metricas['qtd_instalacoes'] += peso
                metricas['potencia_kw'] += instalacao['potencia_kw'] * peso
                metricas['qtd_modulos'] += instalacao['qtd_modulos'] * peso

    nao_identificado_por_municipio = {}
    for codigo_municipio, features in bairros_por_municipio.items():
        metricas_nao_identificado = bairro_metricas.get(codigo_municipio, {}).get('Nao identificado')
        if metricas_nao_identificado:
            nao_identificado_por_municipio[codigo_municipio] = {
                'qtd_instalacoes': round(metricas_nao_identificado['qtd_instalacoes'], 2),
                'potencia_kw': round(metricas_nao_identificado['potencia_kw'], 2),
                'qtd_modulos': round(metricas_nao_identificado['qtd_modulos'], 2),
            }

        qtd_features_por_nome = defaultdict(int)
        for feature in features:
            qtd_features_por_nome[feature['properties']['nome']] += 1

        for feature in features:
            nome = feature['properties']['nome']
            metricas = bairro_metricas.get(codigo_municipio, {}).get(
                nome,
                {'qtd_instalacoes': 0.0, 'potencia_kw': 0.0, 'qtd_modulos': 0.0},
            )
            divisor = qtd_features_por_nome[nome]
            feature['properties']['metricas'] = {
                'qtd_instalacoes': round(metricas['qtd_instalacoes'] / divisor, 2),
                'potencia_kw': round(metricas['potencia_kw'] / divisor, 2),
                'qtd_modulos': round(metricas['qtd_modulos'] / divisor, 2),
            }

    maximos_bairros = {
        codigo: max(
            (feature['properties']['metricas']['qtd_instalacoes'] for feature in features),
            default=0,
        )
        for codigo, features in bairros_por_municipio.items()
    }

    maximos = {
        'qtd_instalacoes': max((item['properties']['metricas']['qtd_instalacoes'] for item in municipios), default=0),
        'potencia_kw': max((item['properties']['metricas']['potencia_kw'] for item in municipios), default=0),
        'qtd_modulos': max((item['properties']['metricas']['qtd_modulos'] for item in municipios), default=0),
    }
    totais = {
        'qtd_instalacoes': sum(item['properties']['metricas']['qtd_instalacoes'] for item in municipios),
        'potencia_kw': round(sum(item['properties']['metricas']['potencia_kw'] for item in municipios), 2),
        'qtd_modulos': sum(item['properties']['metricas']['qtd_modulos'] for item in municipios),
    }

    return {
        'municipios': _feature_collection(municipios),
        'maximos': maximos,
        'totais': totais,
        'maximosBairros': maximos_bairros,
        'naoIdentificadoPorMunicipio': nao_identificado_por_municipio,
        'instalacoesPorMunicipio': instalacoes_por_municipio,
        'bairrosPorMunicipio': {
            codigo: _feature_collection(features)
            for codigo, features in bairros_por_municipio.items()
        },
    }


def render_demo_mapa() -> None:
    data = carregar_geojson_rmr()
    payload = json.dumps(data, ensure_ascii=False)

    ui.add_head_html('''
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {
            background: #f8fafc;
        }
        #demo-mapa-rmr {
            width: 100%;
            height: calc(100vh - 252px);
            min-height: 560px;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
        }
        .rs-map-label {
            border: 0;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.88);
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.16);
            color: #0f172a;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 9px;
        }
        .rs-map-legend {
            background: rgba(255, 255, 255, 0.92);
            border-radius: 18px;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.18);
            color: #0f172a;
            line-height: 1.2;
            padding: 12px 14px;
        }
        .rs-map-legend-title {
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .rs-map-legend-row {
            align-items: center;
            display: flex;
            gap: 8px;
            font-size: 12px;
            font-weight: 700;
            margin-top: 6px;
        }
        .rs-map-legend-swatch {
            border: 1px solid rgba(15, 23, 42, 0.16);
            border-radius: 6px;
            display: inline-block;
            height: 14px;
            width: 24px;
        }
        .rs-map-unidentified {
            background: rgba(15, 23, 42, 0.92);
            border-radius: 18px;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.22);
            color: white;
            min-width: 190px;
            padding: 12px 14px;
        }
        .rs-map-unidentified-title {
            color: rgba(255, 255, 255, 0.7);
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 7px;
            text-transform: uppercase;
        }
        .rs-map-unidentified-value {
            font-size: 20px;
            font-weight: 900;
        }
        .rs-map-unidentified-meta {
            color: rgba(255, 255, 255, 0.72);
            font-size: 12px;
            font-weight: 700;
            margin-top: 4px;
        }
        .rs-map-controls {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1rem;
            align-items: center;
        }
        .rs-map-installations {
            max-height: 360px;
            overflow: auto;
        }
        .rs-map-table {
            border-collapse: collapse;
            min-width: 980px;
            width: 100%;
        }
        .rs-map-table th,
        .rs-map-table td {
            border-bottom: 1px solid #e2e8f0;
            padding: 10px 12px;
            text-align: left;
            white-space: nowrap;
        }
        .rs-map-table th {
            background: #f8fafc;
            color: #475569;
            font-size: 12px;
            font-weight: 700;
            position: sticky;
            top: 0;
            z-index: 1;
        }
        .rs-map-table td {
            color: #0f172a;
            font-size: 13px;
        }
        .rs-map-pagination {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            justify-content: flex-end;
            align-items: center;
        }
        .rs-page-button {
            border: 1px solid #cbd5e1;
            border-radius: 999px;
            color: #0f172a;
            font-size: 13px;
            font-weight: 700;
            padding: 8px 14px;
        }
        .rs-page-button:disabled {
            cursor: not-allowed;
            opacity: 0.45;
        }
        @media (max-width: 900px) {
            .rs-map-controls {
                grid-template-columns: 1fr;
            }
            #demo-mapa-rmr {
                height: 560px;
            }
        }
    </style>
    ''')

    with ui.column().classes('w-full min-h-screen gap-5 p-6'):
        with ui.row().classes('w-full items-end justify-between gap-4'):
            with ui.column().classes('gap-1'):
                ui.label('Demo mapa RMR').classes('text-3xl font-bold text-slate-900')
                ui.label('Mapa de calor municipal com dados de geracao distribuida da ANEEL.').classes('text-base text-slate-600')
            with ui.row().classes('gap-2'):
                ui.button('Voltar', on_click=None).props('outline color=primary').classes('rs-map-back')
                ui.button('RMR', on_click=None).props('outline color=primary').classes('rs-map-reset')

        ui.html('''
        <section class="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="rs-map-controls">
                <div class="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <div class="rounded-2xl bg-orange-50 p-4">
                        <div class="text-xs font-bold uppercase text-orange-700">Selecao</div>
                        <div class="rs-selected-name text-xl font-bold text-slate-900">RMR</div>
                    </div>
                    <div class="rounded-2xl bg-blue-50 p-4">
                        <div class="text-xs font-bold uppercase text-blue-700">Instalacoes</div>
                        <div class="rs-total-installations text-xl font-bold text-slate-900">-</div>
                    </div>
                    <div class="rounded-2xl bg-emerald-50 p-4">
                        <div class="text-xs font-bold uppercase text-emerald-700">Potencia instalada</div>
                        <div class="rs-total-power text-xl font-bold text-slate-900">-</div>
                    </div>
                    <div class="rounded-2xl bg-amber-50 p-4">
                        <div class="text-xs font-bold uppercase text-amber-700">Qtd modulos</div>
                        <div class="rs-total-modules text-xl font-bold text-slate-900">-</div>
                    </div>
                </div>
            </div>
        </section>
        ''').classes('w-full')

        ui.html('<div id="demo-mapa-rmr"></div>').classes('w-full')

        ui.html('''
        <section class="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div class="text-xl font-bold text-slate-900">Instalacoes do municipio</div>
                    <div class="rs-list-helper text-sm text-slate-500">Clique em um municipio no mapa para listar as instalacoes.</div>
                </div>
                <div class="rs-map-pagination">
                    <button class="rs-page-button rs-prev-page" type="button">Anterior</button>
                    <span class="rs-page-status text-sm font-semibold text-slate-500"></span>
                    <button class="rs-page-button rs-next-page" type="button">Proxima</button>
                </div>
            </div>
            <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
                <label class="text-sm font-bold text-slate-600">Classe
                    <select class="rs-filter rs-filter-classe mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Tipo
                    <select class="rs-filter rs-filter-tipo mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Porte
                    <select class="rs-filter rs-filter-porte mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Bairro
                    <select class="rs-filter rs-filter-bairro mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
            </div>
            <div class="rs-map-installations">
                <table class="rs-map-table">
                    <thead>
                        <tr>
                            <th>Codigo</th>
                            <th>CPF/CNPJ</th>
                            <th>Titular</th>
                            <th>Municipio</th>
                            <th>Bairros possiveis</th>
                            <th>Classe</th>
                            <th>Tipo</th>
                            <th>Porte</th>
                            <th>Modalidade</th>
                            <th>Data de Conexao</th>
                            <th>Potencia kW</th>
                            <th>Modulos</th>
                            <th>CEP</th>
                        </tr>
                    </thead>
                    <tbody class="rs-installations-body">
                        <tr><td colspan="13">Nenhum municipio selecionado.</td></tr>
                    </tbody>
                </table>
            </div>
        </section>
        ''').classes('w-full')

    ui.add_body_html(f'''
    <script>
    (() => {{
        const data = {payload};
        function init(attempt = 0) {{
            const container = document.getElementById('demo-mapa-rmr');
            const resetButton = document.querySelector('.rs-map-reset');
            const backButton = document.querySelector('.rs-map-back');
            const selectedName = document.querySelector('.rs-selected-name');
            const totalInstallations = document.querySelector('.rs-total-installations');
            const totalPower = document.querySelector('.rs-total-power');
            const totalModules = document.querySelector('.rs-total-modules');
            const listHelper = document.querySelector('.rs-list-helper');
            const pageStatus = document.querySelector('.rs-page-status');
            const prevPageButton = document.querySelector('.rs-prev-page');
            const nextPageButton = document.querySelector('.rs-next-page');
            const installationsBody = document.querySelector('.rs-installations-body');
            const filterClasse = document.querySelector('.rs-filter-classe');
            const filterTipo = document.querySelector('.rs-filter-tipo');
            const filterPorte = document.querySelector('.rs-filter-porte');
            const filterBairro = document.querySelector('.rs-filter-bairro');
            if (!container || !window.L) {{
                if (attempt < 80) setTimeout(() => init(attempt + 1), 100);
                return;
            }}
            if (container.dataset.loaded === 'true') return;
            container.dataset.loaded = 'true';

            const map = L.map(container, {{ zoomControl: true, scrollWheelZoom: true }});
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }}).addTo(map);

            let activeLayer = null;
            let viewMode = 'rmr';
            let selectedMunicipio = null;
            let currentRows = [];
            let currentPage = 1;
            let legendBody = null;
            let unidentifiedBody = null;
            const pageSize = 100;

            const municipioStyle = {{
                color: '#1D293B',
                weight: 1.4,
                fillColor: '#F97316',
                fillOpacity: 0.32,
            }};
            const selectedMunicipioStyle = {{
                color: '#FFFFFF',
                weight: 3.6,
                fillOpacity: 0.82,
            }};

            function escapeHtml(value) {{
                return String(value ?? '').replace(/[&<>"']/g, (char) => ({{
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#39;',
                }})[char]);
            }}

            function setupFilter(select, values) {{
                select.innerHTML = '<option value="">Todos</option>' + values
                    .filter(Boolean)
                    .sort((a, b) => a.localeCompare(b, 'pt-BR'))
                    .map((value) => `<option value="${{escapeHtml(value)}}">${{escapeHtml(value)}}</option>`)
                    .join('');
            }}

            const allRows = Object.values(data.instalacoesPorMunicipio).flat();
            setupFilter(filterClasse, [...new Set(allRows.map((item) => item.classe))]);
            setupFilter(filterTipo, [...new Set(allRows.map((item) => item.tipo))]);
            setupFilter(filterPorte, [...new Set(allRows.map((item) => item.porte))]);
            setupFilter(filterBairro, []);

            function updateBairroFilter() {{
                const current = filterBairro.value;
                const rows = selectedMunicipio ? (data.instalacoesPorMunicipio[selectedMunicipio.nome] ?? []) : allRows;
                const bairros = [...new Set(rows.flatMap((item) => item.bairros_possiveis ?? [item.bairro]))];
                setupFilter(filterBairro, bairros);
                filterBairro.value = bairros.includes(current) ? current : '';
            }}

            function passFilters(item) {{
                return (!filterClasse.value || item.classe === filterClasse.value)
                    && (!filterTipo.value || item.tipo === filterTipo.value)
                    && (!filterPorte.value || item.porte === filterPorte.value)
                    && (!filterBairro.value || (item.bairros_possiveis ?? [item.bairro]).includes(filterBairro.value));
            }}

            function filteredRows(rows) {{
                return rows.filter(passFilters);
            }}

            function sumMetrics(rows) {{
                return rows.reduce((acc, item) => {{
                    acc.qtd_instalacoes += 1;
                    acc.potencia_kw += Number(item.potencia_kw || 0);
                    acc.qtd_modulos += Number(item.qtd_modulos || 0);
                    return acc;
                }}, {{ qtd_instalacoes: 0, potencia_kw: 0, qtd_modulos: 0 }});
            }}

            function rowsForMunicipio(nomeMunicipio) {{
                return filteredRows(data.instalacoesPorMunicipio[nomeMunicipio] ?? []);
            }}

            function metricasMunicipio(nomeMunicipio) {{
                return sumMetrics(rowsForMunicipio(nomeMunicipio));
            }}

            function metricasBairro(nomeMunicipio, nomeBairro) {{
                const rows = (data.instalacoesPorMunicipio[nomeMunicipio] ?? []).filter((item) => {{
                    return (!filterClasse.value || item.classe === filterClasse.value)
                        && (!filterTipo.value || item.tipo === filterTipo.value)
                        && (!filterPorte.value || item.porte === filterPorte.value);
                }});
                return rows.reduce((acc, item) => {{
                    const bairros = item.bairros_possiveis ?? [item.bairro];
                    if (!bairros.includes(nomeBairro)) return acc;
                    const peso = 1 / bairros.length;
                    acc.qtd_instalacoes += peso;
                    acc.potencia_kw += Number(item.potencia_kw || 0) * peso;
                    acc.qtd_modulos += Number(item.qtd_modulos || 0) * peso;
                    return acc;
                }}, {{ qtd_instalacoes: 0, potencia_kw: 0, qtd_modulos: 0 }});
            }}

            function metricValue(properties) {{
                if (properties.tipo === 'municipio') return metricasMunicipio(properties.nome).qtd_instalacoes;
                return Number(properties.metricas?.qtd_instalacoes ?? 0);
            }}

            function heatColor(value, maxValue) {{
                if (!maxValue || value <= 0) return '#E0F2FE';
                const ratio = Math.min(value / maxValue, 1);
                if (ratio >= 0.78) return '#DC2626';
                if (ratio >= 0.55) return '#F97316';
                if (ratio >= 0.32) return '#FACC15';
                if (ratio >= 0.14) return '#22C55E';
                return '#38BDF8';
            }}

            function municipioMax() {{
                return Math.max(...data.municipios.features.map((feature) => metricasMunicipio(feature.properties.nome).qtd_instalacoes), 0);
            }}

            function municipioHeatStyle(feature) {{
                const value = metricValue(feature.properties);
                const maxValue = municipioMax();
                return {{
                    color: '#1D293B',
                    weight: 1.4,
                    fillColor: heatColor(value, maxValue),
                    fillOpacity: 0.72,
                }};
            }}

            function updateLegend(maxValue, title = 'Instalacoes') {{
                if (!legendBody) return;
                const ranges = [
                    {{ color: '#38BDF8', label: `Ate ${{Math.round(maxValue * 0.14).toLocaleString('pt-BR')}}` }},
                    {{ color: '#22C55E', label: `${{Math.round(maxValue * 0.14).toLocaleString('pt-BR')}} a ${{Math.round(maxValue * 0.32).toLocaleString('pt-BR')}}` }},
                    {{ color: '#FACC15', label: `${{Math.round(maxValue * 0.32).toLocaleString('pt-BR')}} a ${{Math.round(maxValue * 0.55).toLocaleString('pt-BR')}}` }},
                    {{ color: '#F97316', label: `${{Math.round(maxValue * 0.55).toLocaleString('pt-BR')}} a ${{Math.round(maxValue * 0.78).toLocaleString('pt-BR')}}` }},
                    {{ color: '#DC2626', label: `Acima de ${{Math.round(maxValue * 0.78).toLocaleString('pt-BR')}}` }},
                ];
                legendBody.innerHTML = `
                    <div class="rs-map-legend-title">${{title}}</div>
                    ${{ranges.map((range) => `
                        <div class="rs-map-legend-row">
                            <span class="rs-map-legend-swatch" style="background:${{range.color}}"></span>
                            <span>${{range.label}}</span>
                        </div>
                    `).join('')}}
                `;
            }}

            function addLegend() {{
                const legend = L.control({{ position: 'bottomright' }});
                legend.onAdd = () => {{
                    const div = L.DomUtil.create('div', 'rs-map-legend');
                    legendBody = div;
                    L.DomEvent.disableClickPropagation(div);
                    return div;
                }};
                legend.addTo(map);
                updateLegend(Number(data.maximos?.qtd_instalacoes ?? 0));
            }}

            function updateUnidentified(codigoMunicipio = null) {{
                if (!unidentifiedBody) return;
                if (!codigoMunicipio) {{
                    unidentifiedBody.style.display = 'none';
                    return;
                }}
                const municipio = data.municipios.features.find((feature) => feature.properties.codigo === codigoMunicipio)?.properties;
                const rows = municipio ? rowsForMunicipio(municipio.nome).filter((item) => (item.bairros_possiveis ?? []).includes('Nao identificado')) : [];
                const metrics = sumMetrics(rows);
                if (!metrics || !Number(metrics.qtd_instalacoes ?? 0)) {{
                    unidentifiedBody.style.display = 'none';
                    return;
                }}
                unidentifiedBody.style.display = 'block';
                unidentifiedBody.innerHTML = `
                    <div class="rs-map-unidentified-title">Nao identificado</div>
                    <div class="rs-map-unidentified-value">${{Number(metrics.qtd_instalacoes ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}}</div>
                    <div class="rs-map-unidentified-meta">${{Number(metrics.potencia_kw ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} kW</div>
                    <div class="rs-map-unidentified-meta">${{Number(metrics.qtd_modulos ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} modulos</div>
                `;
            }}

            function addUnidentifiedBox() {{
                const control = L.control({{ position: 'topright' }});
                control.onAdd = () => {{
                    const div = L.DomUtil.create('div', 'rs-map-unidentified');
                    div.style.display = 'none';
                    unidentifiedBody = div;
                    L.DomEvent.disableClickPropagation(div);
                    return div;
                }};
                control.addTo(map);
            }}

            function addLabels(layer, labelAccessor) {{
                layer.eachLayer((item) => {{
                    const label = labelAccessor(item.feature.properties);
                    item.bindTooltip(label, {{
                        permanent: true,
                        direction: 'center',
                        className: 'rs-map-label',
                    }});
                }});
            }}

            function setLayer(layer) {{
                if (activeLayer) activeLayer.removeFrom(map);
                activeLayer = layer.addTo(map);
                map.fitBounds(activeLayer.getBounds(), {{ padding: [24, 24] }});
            }}

            function rowsForCurrentScope() {{
                if (viewMode === 'municipio' && selectedMunicipio) return rowsForMunicipio(selectedMunicipio.nome);
                return filteredRows(allRows).sort((a, b) => b.potencia_kw - a.potencia_kw);
            }}

            function metricsForCurrentScope() {{
                return sumMetrics(rowsForCurrentScope());
            }}

            function scopeLabel() {{
                if (viewMode === 'municipio' && selectedMunicipio) return selectedMunicipio.nome;
                return 'RMR';
            }}

            function updateSummary() {{
                const metrics = metricsForCurrentScope();
                selectedName.textContent = scopeLabel();
                totalInstallations.textContent = Number(metrics.qtd_instalacoes ?? 0).toLocaleString('pt-BR');
                totalPower.textContent = `${{Number(metrics.potencia_kw ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} kW`;
                totalModules.textContent = Number(metrics.qtd_modulos ?? 0).toLocaleString('pt-BR');
            }}

            function renderTablePage(page = currentPage) {{
                const totalPages = Math.max(Math.ceil(currentRows.length / pageSize), 1);
                currentPage = Math.min(Math.max(page, 1), totalPages);
                const start = (currentPage - 1) * pageSize;
                const visible = currentRows.slice(start, start + pageSize);

                pageStatus.textContent = `${{currentPage}} / ${{totalPages}}`;
                prevPageButton.disabled = currentPage <= 1;
                nextPageButton.disabled = currentPage >= totalPages;
                installationsBody.innerHTML = visible.map((item) => `
                    <tr>
                        <td>${{escapeHtml(item.codigo)}}</td>
                        <td>${{escapeHtml(item.cpf_cnpj)}}</td>
                        <td>${{escapeHtml(item.titular)}}</td>
                        <td>${{escapeHtml(item.municipio)}}</td>
                        <td>${{escapeHtml((item.bairros_possiveis ?? [item.bairro]).join(', '))}}</td>
                        <td>${{escapeHtml(item.classe)}}</td>
                        <td>${{escapeHtml(item.tipo)}}</td>
                        <td>${{escapeHtml(item.porte)}}</td>
                        <td>${{escapeHtml(item.modalidade_habilitado)}}</td>
                        <td>${{escapeHtml(item.data_conexao)}}</td>
                        <td>${{Number(item.potencia_kw).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}}</td>
                        <td>${{Number(item.qtd_modulos).toLocaleString('pt-BR')}}</td>
                        <td>${{escapeHtml(item.cep)}}</td>
                    </tr>
                `).join('') || '<tr><td colspan="13">Nenhuma instalacao encontrada.</td></tr>';
            }}

            function renderInstallations(page = 1) {{
                currentRows = rowsForCurrentScope();
                const scope = scopeLabel();
                listHelper.textContent = `${{scope}}: ${{currentRows.length.toLocaleString('pt-BR')}} instalacoes encontradas. Ordenacao por maior potencia.`;
                renderTablePage(page);
            }}

            function renderBairros(codigoMunicipio, nomeMunicipio) {{
                const bairros = data.bairrosPorMunicipio[codigoMunicipio];
                const metricasPorBairro = Object.fromEntries(
                    bairros.features.map((feature) => [feature.properties.nome, metricasBairro(nomeMunicipio, feature.properties.nome)])
                );
                const maxBairro = Math.max(
                    ...Object.values(metricasPorBairro).map((metrics) => metrics.qtd_instalacoes),
                    0,
                );
                const estiloBairro = (feature) => {{
                    const value = Number(metricasPorBairro[feature.properties.nome]?.qtd_instalacoes ?? 0);
                    return {{
                        color: '#1D293B',
                        weight: 1.1,
                        fillColor: heatColor(value, maxBairro),
                        fillOpacity: 0.72,
                    }};
                }};
                const layer = L.geoJSON(bairros, {{
                    style: estiloBairro,
                    onEachFeature: (feature, item) => {{
                        const metrics = metricasPorBairro[feature.properties.nome] ?? {{ qtd_instalacoes: 0, potencia_kw: 0, qtd_modulos: 0 }};
                        item.on('mouseover', () => {{
                            item.setStyle(selectedMunicipioStyle);
                            item.bringToFront();
                        }});
                        item.on('mouseout', () => item.setStyle(estiloBairro(feature)));
                        item.bindPopup(`
                            <strong>${{feature.properties.nome}}</strong><br>
                            ${{Number(metrics.qtd_instalacoes ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} instalacoes estimadas<br>
                            ${{Number(metrics.potencia_kw ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} kW<br>
                            ${{Number(metrics.qtd_modulos ?? 0).toLocaleString('pt-BR', {{ maximumFractionDigits: 2 }})}} modulos
                        `);
                    }},
                }});
                addLabels(layer, (properties) => properties.nome);
                setLayer(layer);
                updateLegend(maxBairro, `Bairros de ${{nomeMunicipio}}`);
                updateUnidentified(codigoMunicipio);
            }}

            function renderMunicipios() {{
                const layer = L.geoJSON(data.municipios, {{
                    style: municipioHeatStyle,
                    onEachFeature: (feature, item) => {{
                        item.on('mouseover', () => {{
                            item.setStyle(selectedMunicipioStyle);
                            item.bringToFront();
                        }});
                        item.on('mouseout', () => item.setStyle(municipioHeatStyle(feature)));
                        item.on('click', () => {{
                            viewMode = 'municipio';
                            selectedMunicipio = feature.properties;
                            updateBairroFilter();
                            updateSummary();
                            renderInstallations(1);
                            renderBairros(feature.properties.codigo, feature.properties.nome);
                        }});
                    }},
                }});
                addLabels(layer, (properties) => properties.nome);
                setLayer(layer);
                updateSummary();
                updateLegend(municipioMax(), 'Municipios');
                updateUnidentified(null);
            }}

            resetButton?.addEventListener('click', () => {{
                viewMode = 'rmr';
                selectedMunicipio = null;
                filterBairro.value = '';
                updateBairroFilter();
                renderMunicipios();
                renderInstallations(1);
            }});
            backButton?.addEventListener('click', () => {{
                if (viewMode === 'municipio') {{
                    viewMode = 'rmr';
                    selectedMunicipio = null;
                    filterBairro.value = '';
                    updateBairroFilter();
                    renderMunicipios();
                    renderInstallations(1);
                }}
            }});
            prevPageButton?.addEventListener('click', () => renderTablePage(currentPage - 1));
            nextPageButton?.addEventListener('click', () => renderTablePage(currentPage + 1));
            [filterClasse, filterTipo, filterPorte, filterBairro].forEach((select) => select.addEventListener('change', () => {{
                if (select !== filterBairro) updateBairroFilter();
                if (viewMode === 'municipio' && selectedMunicipio) renderBairros(selectedMunicipio.codigo, selectedMunicipio.nome);
                else renderMunicipios();
                updateSummary();
                renderInstallations(1);
            }}));
            addLegend();
            addUnidentifiedBox();
            viewMode = 'rmr';
            updateBairroFilter();
            renderMunicipios();
            updateSummary();
            renderInstallations(1);
            setTimeout(() => map.invalidateSize(), 100);
        }}

        init();
    }})();
    </script>
    ''')
