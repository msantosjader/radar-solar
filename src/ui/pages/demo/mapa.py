from __future__ import annotations

import json
import secrets
import time
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse, Response
import pandas as pd
import shapefile
from nicegui import app, ui

from src.models import CnpjCache, InstalacaoSolar, Lead
from src.normalize import normalizar_inversor, normalizar_modulo
from src.utils import log_aviso, log_info, log_dados, log_ok

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
LEAD_STATUS_LABELS = {
    'Novo': 'Novo',
    'Em Contato': 'Em andamento',
    'Concluído': 'Concluido',
}
MAPA_EMPRESA_TOKENS: dict[str, float] = {}
MAPA_TOKEN_TTL_SECONDS = 15 * 60


def _geocodificar_endereco(instalacao: InstalacaoSolar) -> tuple[float, float] | None:
    partes = [
        _text(instalacao.logradouro),
        _text(instalacao.numero),
        _text(instalacao.cep),
        _text(instalacao.cidade),
        _text(instalacao.estado),
        'Brasil',
    ]
    endereco = ', '.join(part for part in partes if part)
    if not endereco:
        return None

    query = urlencode({'format': 'json', 'limit': '1', 'q': endereco})
    request = Request(
        f'https://nominatim.openstreetmap.org/search?{query}',
        headers={'User-Agent': 'RadarSolar/1.0 (contato@radarsolar.local)'},
    )
    try:
        with urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    if not data:
        return None
    try:
        return float(data[0]['lat']), float(data[0]['lon'])
    except (KeyError, TypeError, ValueError):
        return None


def _shape_centroid(geometry: dict) -> tuple[float, float] | None:
    points: list[tuple[float, float]] = []

    def collect(coords):
        if not coords:
            return
        first = coords[0]
        if isinstance(first, (int, float)) and len(coords) >= 2:
            points.append((float(coords[1]), float(coords[0])))
            return
        for item in coords:
            collect(item)

    collect(geometry.get('coordinates', []))
    if not points:
        return None
    return sum(lat for lat, _ in points) / len(points), sum(lng for _, lng in points) / len(points)


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
        log_aviso('Mapa: arquivo de empreendimentos CSV nao encontrado')
        return {}

    colunas = ['CodEmpreendimento', 'NumCPFCNPJ', 'NomTitularEmpreendimento', 'DscModalidadeHabilitado']
    df = pd.read_csv(EMPREENDIMENTOS_CSV, sep=';', encoding='latin1', usecols=colunas)
    log_dados('Mapa: dados titular carregados do CSV', len(df), fonte=EMPREENDIMENTOS_CSV.name)
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
def carregar_instalacoes_aneel() -> tuple[dict[str, dict], dict[str, list[dict]], dict]:
    log_info('Mapa: carregando instalacoes ANEEL do Parquet...')
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
        'fabricante_modulo',
        'fabricante_inversor',
        'modalidade',
        'qtd_ucs_recebem_credito',
        'potencia_modulos_kw',
        'potencia_inversores_kw',
        'area_arranjo_m2',
    ]
    df = pd.read_parquet(INSTALACOES_PARQUET, columns=colunas)
    log_dados('Mapa: instalacoes ANEEL carregadas do Parquet', len(df), fonte=INSTALACOES_PARQUET.name)
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
            data_conexao_parsed = pd.to_datetime(row.data_conexao, errors='coerce')
            data_conexao_ano = data_conexao_parsed.year if pd.notna(data_conexao_parsed) else None
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
                'data_conexao_ano': data_conexao_ano,
                'potencia_kw': round(_number(row.potencia_kw), 2),
                'qtd_modulos': int(_number(row.qtd_modulos)),
                'fabricante_modulo': normalizar_modulo(_text(row.fabricante_modulo)),
                'fabricante_inversor': normalizar_inversor(_text(row.fabricante_inversor)),
                'qtd_uc_credito': int(_number(row.qtd_ucs_recebem_credito)),
                'potencia_modulos_kw': round(_number(row.potencia_modulos_kw), 2),
                'potencia_inversores_kw': round(_number(row.potencia_inversores_kw), 2),
                'area_arranjo_m2': round(_number(row.area_arranjo_m2), 2),
                'cep': _text(row.cep_original),
                'cep_prefixo': _text(row.cep_prefixo),
            })
        instalacoes_por_municipio[municipio] = instalacoes

    serie_anual = (
        df['data_conexao'].dt.year.dropna().astype(int).value_counts().sort_index()
    )
    df['fabricante_modulo_norm'] = df['fabricante_modulo'].apply(
        lambda v: normalizar_modulo(_text(v)) if pd.notna(v) else ''
    )
    df['fabricante_inversor_norm'] = df['fabricante_inversor'].apply(
        lambda v: normalizar_inversor(_text(v)) if pd.notna(v) else ''
    )
    fabricantes_modulo = (
        df.loc[df['fabricante_modulo_norm'] != '', 'fabricante_modulo_norm']
        .value_counts().head(15)
    )
    fabricantes_inversor = (
        df.loc[df['fabricante_inversor_norm'] != '', 'fabricante_inversor_norm']
        .value_counts().head(15)
    )

    tipo_counts = df['tipo_consumidor'].value_counts()
    classe_counts = df['classe_consumo'].value_counts()
    porte_counts = df['porte'].value_counts()
    modalidade_counts = df['modalidade'].value_counts()

    serie_por_modalidade = df.groupby([df['data_conexao'].dt.year, 'modalidade']).size().unstack(fill_value=0)
    serie_por_modalidade.index = serie_por_modalidade.index.astype(int)
    serie_por_modalidade_labels = [str(y) for y in serie_por_modalidade.index.tolist()]
    serie_por_modalidade_datasets = [
        {'label': col, 'data': [int(v) for v in serie_por_modalidade[col].values.tolist()]}
        for col in serie_por_modalidade.columns
    ]

    charts = {
        'seriePorModalidade': {
            'labels': serie_por_modalidade_labels,
            'datasets': serie_por_modalidade_datasets,
        },
        'porTipoPF_PJ': {
            'labels': tipo_counts.index.tolist(),
            'values': [int(v) for v in tipo_counts.values.tolist()],
        },
        'topFabricantesModulo': {
            'labels': fabricantes_modulo.index.tolist(),
            'values': [int(v) for v in fabricantes_modulo.values.tolist()],
        },
        'topFabricantesInversor': {
            'labels': fabricantes_inversor.index.tolist(),
            'values': [int(v) for v in fabricantes_inversor.values.tolist()],
        },
        'porClasse': {
            'labels': classe_counts.index.tolist(),
            'values': [int(v) for v in classe_counts.values.tolist()],
        },
        'porPorte': {
            'labels': porte_counts.index.tolist(),
            'values': [int(v) for v in porte_counts.values.tolist()],
        },
        'porModalidade': {
            'labels': modalidade_counts.index.tolist(),
            'values': [int(v) for v in modalidade_counts.values.tolist()],
        },
    }

    return agregados, instalacoes_por_municipio, charts


@lru_cache(maxsize=1)
def carregar_geojson_rmr() -> dict:
    log_info('Mapa: construindo GeoJSON da RMR (shapefiles + instalacoes)...')
    agregados_aneel, instalacoes_por_municipio, charts = carregar_instalacoes_aneel()
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

        mascaras_4_por_municipio: dict[str, dict[str, set[str]]] = {}
        for codigo_municipio, prefixos in bairros_por_prefixo.items():
            mascaras_4: dict[str, set[str]] = {}
            for prefixo_5, bairros in prefixos.items():
                prefixo_4 = prefixo_5[:4]
                mascaras_4.setdefault(prefixo_4, set()).update(bairros)
            mascaras_4_por_municipio[codigo_municipio] = mascaras_4

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
            mascaras_4_municipio = mascaras_4_por_municipio.get(municipio_codigo, {})
            fallback_nome = municipio['properties']['nome'] if not bairros_validos else 'Nao identificado'

            for instalacao in instalacoes:
                cep_original = instalacao['cep']
                cep_mascarado = '***' in cep_original
                cep_exato = ''.join(char for char in cep_original if char.isdigit()) if not cep_mascarado else ''
                candidatos_dne = ceps_exatos_municipio.get(cep_exato, set()) if len(cep_exato) == 8 else set()
                if not candidatos_dne:
                    candidatos_dne = prefixos_municipio.get(instalacao['cep_prefixo'], set())
                if not candidatos_dne and instalacao['tipo'] == 'PJ':
                    prefixo_4 = instalacao['cep_prefixo'][:4] if len(instalacao['cep_prefixo']) >= 4 else ''
                    candidatos_dne = mascaras_4_municipio.get(prefixo_4, set())
                bairros_possiveis = sorted({
                    bairros_validos[_bairro_key(nome)]
                    for nome in candidatos_dne
                    if _bairro_key(nome) in bairros_validos
                })
                if not bairros_possiveis:
                    for nome in candidatos_dne:
                        key = _bairro_key(nome)
                        for valid_key, valid_nome in bairros_validos.items():
                            if valid_key in key or key in valid_key:
                                bairros_possiveis = [valid_nome]
                                break
                        if bairros_possiveis:
                            break

                bairro_estimado_key = _bairro_key(instalacao['bairro'])
                if not bairros_possiveis and bairro_estimado_key in bairros_validos:
                    bairros_possiveis = [bairros_validos[bairro_estimado_key]]
                if not bairros_possiveis:
                    for valid_key, valid_nome in bairros_validos.items():
                        if valid_key in bairro_estimado_key or bairro_estimado_key in valid_key:
                            bairros_possiveis = [valid_nome]
                            break

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
        'charts': charts,
    }


def carregar_leads_mapa(data: dict) -> list[dict]:
    municipios_por_nome = {
        _norm(feature['properties']['nome']): feature
        for feature in data['municipios']['features']
    }
    bairros_por_municipio = data['bairrosPorMunicipio']
    bairros_por_cep_exato, bairros_por_prefixo = carregar_bairros_por_cep()

    leads = (
        Lead.select()
        .where(Lead.status.in_(list(LEAD_STATUS_LABELS)))
        .order_by(Lead.criado_em.desc())
    )
    pins: list[dict] = []

    for lead in leads:
        if not lead.cliente_id:
            continue

        instalacao = InstalacaoSolar.select().where(InstalacaoSolar.usuario == lead.cliente_id).first()
        if not instalacao:
            continue

        lat = instalacao.latitude
        lng = instalacao.longitude
        aproximado = False
        municipio_nome = _text(instalacao.cidade)
        municipio = municipios_por_nome.get(_norm(municipio_nome))
        municipio_codigo = municipio['properties']['codigo'] if municipio else ''

        if lat is None or lng is None:
            coordenada_exata = _geocodificar_endereco(instalacao)
            if coordenada_exata:
                lat, lng = coordenada_exata
                instalacao.latitude = lat
                instalacao.longitude = lng
                instalacao.save()

        if lat is None or lng is None:
            aproximado = True
            cep = ''.join(char for char in _text(instalacao.cep) if char.isdigit())
            candidatos = set()
            if municipio_codigo and len(cep) == 8:
                candidatos = bairros_por_cep_exato.get(municipio_codigo, {}).get(cep, set())
            if municipio_codigo and not candidatos and len(cep) >= 5:
                candidatos = bairros_por_prefixo.get(municipio_codigo, {}).get(cep[:5], set())

            bairro_centroid = None
            bairros = bairros_por_municipio.get(municipio_codigo, {}).get('features', []) if municipio_codigo else []
            bairros_por_key = {
                _bairro_key(feature['properties']['nome']): feature
                for feature in bairros
                if feature['properties']['tipo'] == 'bairro'
            }
            for candidato in candidatos:
                feature = bairros_por_key.get(_bairro_key(candidato))
                if not feature:
                    continue
                bairro_centroid = _shape_centroid(feature['geometry'])
                if bairro_centroid:
                    break

            if bairro_centroid:
                lat, lng = bairro_centroid
            elif municipio:
                municipio_centroid = _shape_centroid(municipio['geometry'])
                if municipio_centroid:
                    lat, lng = municipio_centroid

        if lat is None or lng is None:
            continue

        endereco = ', '.join(
            part
            for part in [
                _text(instalacao.logradouro),
                _text(instalacao.numero),
                municipio_nome,
                _text(instalacao.estado),
            ]
            if part
        )
        pins.append({
            'id': lead.id,
            'nome': _text(lead.nome_contato),
            'telefone': _text(lead.telefone_contato),
            'status': _text(lead.status),
            'status_label': LEAD_STATUS_LABELS.get(_text(lead.status), _text(lead.status)),
            'descricao': _text(lead.descricao_servico),
            'endereco': endereco,
            'cep': _text(instalacao.cep),
            'lat': float(lat),
            'lng': float(lng),
            'aproximado': aproximado,
        })

    return pins


def carregar_pjs_mapa(data: dict) -> list[dict]:
    instalacoes = []
    for lista in data['instalacoesPorMunicipio'].values():
        instalacoes.extend(lista)

    pjs = [inst for inst in instalacoes if inst.get('tipo') == 'PJ' and inst.get('cpf_cnpj')]
    pins: list[dict] = []
    cnpj_cache: dict[str, CnpjCache] = {
        c.cnpj: c for c in CnpjCache.select()
    }

    for inst in pjs:
        cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
        if len(cnpj) != 14:
            continue
        cache = cnpj_cache.get(cnpj)
        if not cache or cache.latitude is None or cache.longitude is None:
            continue
        logradouro_rel = ''
        numero_rel = ''
        bairro_rel = ''
        endereco_rel = inst.get('municipio', '')
        cep = inst.get('cep', '')
        if cache and cache.logradouro:
            logradouro_rel = cache.logradouro or ''
            numero_rel = cache.numero or ''
            bairro_rel = cache.bairro or ''
            endereco_rel = ', '.join(p for p in [logradouro_rel, numero_rel, bairro_rel, cache.cidade or '', cache.estado or ''] if p)
            cep = cache.cep or cep
        else:
            bairro_rel = inst.get('bairro', '')
            if bairro_rel and bairro_rel != 'Nao identificado':
                endereco_rel = f'{inst["municipio"]}, {bairro_rel}'

        lat = cache.latitude
        lng = cache.longitude

        pins.append({
            'codigo': inst['codigo'],
            'titular': inst['titular'],
            'cnpj': cnpj,
            'endereco': endereco_rel,
            'logradouro': logradouro_rel,
            'numero': numero_rel,
            'bairro': bairro_rel,
            'cep': cep,
            'municipio': inst['municipio'],
            'uf': (cache.estado if cache else None) or '',
            'data_instalacao': inst.get('data_conexao', ''),
            'qtd_modulos': inst.get('qtd_modulos', 0),
            'potencia_kw': inst['potencia_kw'],
            'telefone1': cache.telefone1 if cache else None,
            'telefone2': cache.telefone2 if cache else None,
            'email': cache.email if cache else None,
            'lat': float(lat),
            'lng': float(lng),
        })

    return pins


def _estimar_coordenada_por_cep(
    municipio_codigo: str, cep_digits: str, prefixo: str,
    bairros_por_cep_exato: dict, bairros_por_prefixo: dict, data: dict,
) -> tuple[float | None, float | None]:
    candidatos: set[str] = set()
    if municipio_codigo and len(cep_digits) == 8:
        candidatos = bairros_por_cep_exato.get(municipio_codigo, {}).get(cep_digits, set())
    if not candidatos and municipio_codigo and len(prefixo) >= 5:
        candidatos = bairros_por_prefixo.get(municipio_codigo, {}).get(prefixo[:5], set())

    bairros = data.get('bairrosPorMunicipio', {}).get(municipio_codigo, {}).get('features', [])
    if candidatos:
        bairros_por_key = {
            _bairro_key(f['properties']['nome']): f
            for f in bairros if f['properties']['tipo'] == 'bairro'
        }
        for candidato in candidatos:
            feature = bairros_por_key.get(_bairro_key(candidato))
            if not feature:
                continue
            c = _shape_centroid(feature['geometry'])
            if c:
                return c

    for feature in bairros:
        if feature['properties'].get('tipo') == 'bairro_fallback':
            c = _shape_centroid(feature['geometry'])
            if c:
                return c

    for feature in data['municipios']['features']:
        if feature['properties']['codigo'] == municipio_codigo:
            c = _shape_centroid(feature['geometry'])
            if c:
                return c

    return None, None


def carregar_mapa_base_json() -> str:
    return json.dumps(carregar_geojson_rmr(), ensure_ascii=False)


def montar_mapa_json(leads: list[dict] | None = None, pjs: list[dict] | None = None) -> str:
    base_json = carregar_mapa_base_json()[:-1]
    extra = []
    extra.append(f'"leads":{json.dumps(leads or [], ensure_ascii=False)}')
    extra.append(f'"pjs":{json.dumps(pjs or [], ensure_ascii=False)}')
    return f'{base_json},{",".join(extra)}}}'


def carregar_mapa_data(include_leads: bool = False) -> dict:
    base = carregar_geojson_rmr()
    data = {**base}
    data['leads'] = carregar_leads_mapa(data) if include_leads else []
    return data


@app.get('/api/demo/mapa-rmr')
def api_demo_mapa_rmr() -> Response:
    data = carregar_geojson_rmr()
    return Response(
        montar_mapa_json(pjs=carregar_pjs_mapa(data)),
        media_type='application/json',
        headers={'Cache-Control': 'no-store'},
    )


@app.get('/api/empresa/mapa-rmr')
def api_empresa_mapa_rmr(request: FastAPIRequest) -> JSONResponse:
    token = request.query_params.get('token', '')
    now = time.time()
    for stored_token, expires_at in list(MAPA_EMPRESA_TOKENS.items()):
        if expires_at < now:
            MAPA_EMPRESA_TOKENS.pop(stored_token, None)
    if not token or MAPA_EMPRESA_TOKENS.get(token, 0) < now:
        return JSONResponse({'error': 'Nao autorizado'}, status_code=401)
    data = carregar_geojson_rmr()
    return Response(
        montar_mapa_json(
            leads=carregar_leads_mapa(data),
            pjs=carregar_pjs_mapa(data),
        ),
        media_type='application/json',
        headers={'Cache-Control': 'no-store'},
    )


def render_demo_mapa(show_header: bool = True, include_leads: bool = False) -> None:
    if include_leads:
        token = secrets.token_urlsafe(24)
        MAPA_EMPRESA_TOKENS[token] = time.time() + MAPA_TOKEN_TTL_SECONDS
        data_url = f'/api/empresa/mapa-rmr?token={token}'
    else:
        data_url = '/api/demo/mapa-rmr'
    _render_demo_mapa_content(data_url, show_header=show_header)


def _render_mapa_header() -> None:
    with ui.row().classes('w-full items-end justify-between gap-4'):
        with ui.column().classes('gap-1'):
            ui.label('Demo mapa RMR').classes('text-3xl font-bold text-slate-900')
            ui.label('Mapa de calor municipal com dados de geracao distribuida da ANEEL.').classes('text-base text-slate-600')


def _render_mapa_summary() -> None:
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


def _render_mapa_charts() -> None:
    ui.html('''
        <section class="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="rs-chart-title mb-4 text-xl font-bold text-slate-900">Graficos - RMR</div>
            <div class="mb-2 text-xs font-bold uppercase text-slate-500">Barras</div>
            <div class="rs-charts-grid">
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Conexoes por ano por modalidade</div>
                    <canvas id="chart-series-modalidade"></canvas>
                </div>
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Top fabricantes de modulos</div>
                    <canvas id="chart-modulos"></canvas>
                </div>
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Top fabricantes de inversores</div>
                    <canvas id="chart-inversores"></canvas>
                </div>
            </div>
            <div class="mb-2 mt-4 text-xs font-bold uppercase text-slate-500">Pizzas</div>
            <div class="rs-charts-grid rs-pies-grid">
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">PF vs PJ</div>
                    <canvas id="chart-tipo"></canvas>
                </div>
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Por classe</div>
                    <canvas id="chart-classe"></canvas>
                </div>
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Por porte</div>
                    <canvas id="chart-porte"></canvas>
                </div>
                <div class="rs-chart-box">
                    <div class="mb-2 text-xs font-bold uppercase text-slate-500">Modalidade</div>
                    <canvas id="chart-modalidade"></canvas>
                </div>
            </div>
        </section>
    ''').classes('w-full')


def _render_mapa_table() -> None:
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
                <label class="text-sm font-bold text-slate-600">Modalidade
                    <select class="rs-filter rs-filter-modalidade mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Bairro
                    <select class="rs-filter rs-filter-bairro mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Fabricante Modulo
                    <select class="rs-filter rs-filter-fab-mod mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
                </label>
                <label class="text-sm font-bold text-slate-600">Fabricante Inversor
                    <select class="rs-filter rs-filter-fab-inv mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900"></select>
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
                            <th>Fab. Modulo</th>
                            <th>Fab. Inversor</th>
                            <th>Qtd UC Credito</th>
                            <th>CEP</th>
                        </tr>
                    </thead>
                    <tbody class="rs-installations-body">
                        <tr><td colspan="16">Nenhum municipio selecionado.</td></tr>
                    </tbody>
                </table>
            </div>
        </section>
    ''').classes('w-full')


def _inject_mapa_script(data_url: str) -> None:
    ui.add_body_html(f'''
    <script>window.DATA_URL = {json.dumps(data_url)};</script>
    <script src="/demo/static/mapa.js"></script>
    ''')


def _render_demo_mapa_content(data_url: str, show_header: bool = True) -> None:
    ui.add_head_html('<link rel="stylesheet" href="/demo/static/mapa.css">')

    container_classes = 'w-full gap-5 p-6'
    if show_header:
        container_classes += ' min-h-screen'

    with ui.column().classes(container_classes):
        if show_header:
            _render_mapa_header()

        _render_mapa_summary()
        ui.html('<div id="demo-mapa-rmr">Carregando dados do mapa...</div>').classes('w-full')
        _render_mapa_charts()
        _render_mapa_table()

    _inject_mapa_script(data_url)
