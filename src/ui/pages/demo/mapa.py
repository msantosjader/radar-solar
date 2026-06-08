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
def carregar_instalacoes_aneel() -> tuple[dict[str, dict], dict[str, list[dict]], dict]:
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
    bairros_por_cep_exato, bairros_por_prefixo = carregar_bairros_por_cep()

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

        lat = lng = None
        if cache and cache.latitude and cache.longitude:
            lat = cache.latitude
            lng = cache.longitude
        else:
            municipio_codigo = inst.get('municipio_codigo', '')
            cep_digits = ''.join(ch for ch in cep if ch.isdigit())
            prefixo = inst.get('cep_prefixo', '')
            lat, lng = _estimar_coordenada_por_cep(
                municipio_codigo, cep_digits, prefixo,
                bairros_por_cep_exato, bairros_por_prefixo, data,
            )

        if not lat or not lng:
            continue

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
        headers={'Cache-Control': 'public, max-age=300'},
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


def _render_demo_mapa_content(data_url: str, show_header: bool = True) -> None:

    ui.add_head_html('''
    <style>
        body {
            background: #f8fafc;
        }
        #demo-mapa-rmr {
            align-items: center;
            background: linear-gradient(135deg, #f8fafc, #eef2ff);
            color: #475569;
            display: flex;
            font-size: 14px;
            font-weight: 800;
            width: 100%;
            height: calc(100vh - 420px);
            justify-content: center;
            min-height: 400px;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
        }
        #demo-mapa-rmr.rs-map-ready {
            display: block;
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
        .rs-lead-legend {
            background: rgba(255, 255, 255, 0.94);
            border-radius: 18px;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.18);
            color: #0f172a;
            padding: 12px 14px;
        }
        .rs-lead-legend-title {
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .rs-lead-legend-row {
            align-items: center;
            display: flex;
            gap: 8px;
            font-size: 12px;
            font-weight: 700;
            margin-top: 6px;
        }
        .rs-lead-legend-dot {
            border: 2px solid white;
            border-radius: 999px;
            box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18);
            display: inline-block;
            height: 12px;
            width: 12px;
        }
        .rs-lead-pin {
            height: 42px;
            position: relative;
            width: 30px;
        }
        .rs-lead-pin::before {
            background: var(--lead-color);
            border: 3px solid #fff;
            border-radius: 50% 50% 50% 0;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.35);
            content: '';
            height: 24px;
            left: 3px;
            position: absolute;
            top: 0;
            transform: rotate(-45deg);
            width: 24px;
        }
        .rs-lead-pin::after {
            background: #fff;
            border-radius: 999px;
            content: '';
            height: 8px;
            left: 11px;
            position: absolute;
            top: 8px;
            width: 8px;
        }
        .rs-label-toggle,
        .rs-map-back-control {
            background: rgba(255, 255, 255, 0.94);
            border: 0;
            border-radius: 14px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
            color: #0f172a;
            cursor: pointer;
            font-size: 12px;
            font-weight: 800;
            padding: 10px 12px;
            text-transform: uppercase;
        }
        #demo-mapa-rmr.rs-hide-labels .rs-map-label {
            display: none;
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
        .rs-chart-box {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
            padding: 20px;
            min-height: 260px;
        }
        .rs-chart-box canvas {
            width: 100% !important;
            height: 220px !important;
        }
        .rs-charts-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: 1fr;
        }
        @media (min-width: 768px) {
            .rs-charts-grid {
                grid-template-columns: 1fr 1fr 1fr;
            }
            .rs-pies-grid {
                grid-template-columns: 1fr 1fr 1fr 1fr;
            }
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
                height: 420px;
            }
        }
    </style>
    ''')

    container_classes = 'w-full gap-5 p-6'
    if show_header:
        container_classes += ' min-h-screen'

    with ui.column().classes(container_classes):
        if show_header:
            with ui.row().classes('w-full items-end justify-between gap-4'):
                with ui.column().classes('gap-1'):
                    ui.label('Demo mapa RMR').classes('text-3xl font-bold text-slate-900')
                    ui.label('Mapa de calor municipal com dados de geracao distribuida da ANEEL.').classes('text-base text-slate-600')

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

        ui.html('<div id="demo-mapa-rmr">Carregando dados do mapa...</div>').classes('w-full')

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

    ui.add_body_html(f'''
    <script>
    (() => {{
        const dataUrl = {json.dumps(data_url)};
        let data = null;

        function loadStyleOnce(id, href) {{
            if (document.getElementById(id)) return;
            const link = document.createElement('link');
            link.id = id;
            link.rel = 'stylesheet';
            link.href = href;
            document.head.appendChild(link);
        }}

        function loadScriptOnce(id, src, globalName) {{
            if (globalName && window[globalName]) return Promise.resolve();
            const existing = document.getElementById(id);
            if (existing) {{
                return new Promise((resolve, reject) => {{
                    existing.addEventListener('load', resolve, {{ once: true }});
                    existing.addEventListener('error', reject, {{ once: true }});
                    if (globalName && window[globalName]) resolve();
                }});
            }}
            return new Promise((resolve, reject) => {{
                const script = document.createElement('script');
                script.id = id;
                script.src = src;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            }});
        }}

        async function ensureMapAssets() {{
            loadStyleOnce('leaflet-css', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css');
            await loadScriptOnce('leaflet-js', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'L');
            await loadScriptOnce('chart-js', 'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js', 'Chart');
        }}

        async function init(attempt = 0) {{
            const container = document.getElementById('demo-mapa-rmr');
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
            const filterFabMod = document.querySelector('.rs-filter-fab-mod');
            const filterFabInv = document.querySelector('.rs-filter-fab-inv');
            const filterModalidade = document.querySelector('.rs-filter-modalidade');
            const chartTitle = document.querySelector('.rs-chart-title');
            const chartSeriesModalidade = document.getElementById('chart-series-modalidade');
            const chartModulos = document.getElementById('chart-modulos');
            const chartInversores = document.getElementById('chart-inversores');
            const chartTipo = document.getElementById('chart-tipo');
            const chartClasse = document.getElementById('chart-classe');
            const chartPorte = document.getElementById('chart-porte');
            const chartModalidade = document.getElementById('chart-modalidade');
            let chartSeriesModalidadeInstance = null;
            let chartModulosInstance = null;
            let chartInversoresInstance = null;
            let chartTipoInstance = null;
            let chartClasseInstance = null;
            let chartPorteInstance = null;
            let chartModalidadeInstance = null;
            if (!container) {{
                if (attempt < 80) setTimeout(() => init(attempt + 1), 100);
                return;
            }}
            if (container.dataset.loaded === 'true') return;
            container.dataset.loaded = 'true';

            try {{
                await ensureMapAssets();
            }} catch (error) {{
                container.textContent = `Nao foi possivel carregar as bibliotecas do mapa (${{error.message || 'erro de rede'}}).`;
                console.error('Erro ao carregar bibliotecas do mapa:', error);
                return;
            }}

            try {{
                const response = await fetch(dataUrl, {{ credentials: 'same-origin' }});
                if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
                data = await response.json();
            }} catch (error) {{
                container.textContent = `Nao foi possivel carregar os dados do mapa (${{error.message}}).`;
                console.error('Erro ao carregar mapa:', error);
                return;
            }}
            container.textContent = '';
            container.classList.add('rs-map-ready');

            const map = L.map(container, {{ zoomControl: true, scrollWheelZoom: true }});
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }}).addTo(map);
            map.createPane('leadPane');
            map.getPane('leadPane').style.zIndex = 760;
            map.getPane('leadPane').style.pointerEvents = 'auto';

            const leadStatusColors = {{
                'Novo': '#2563eb',
                'Em Contato': '#f97316',
                'Concluído': '#16a34a',
            }};
            const leadStatusLabels = {{
                'Novo': 'Novo',
                'Em Contato': 'Em andamento',
                'Concluído': 'Concluido',
            }};
            const leadLayer = L.layerGroup([], {{ pane: 'leadPane' }}).addTo(map);
            const pjLayer = L.layerGroup([], {{ pane: 'leadPane' }});

            let activeLayer = null;
            let viewMode = 'rmr';
            let selectedMunicipio = null;
            let currentRows = [];
            let currentPage = 1;
            let legendBody = null;
            let unidentifiedBody = null;
            let backControlButton = null;
            let labelsVisible = true;
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

            function formatCnpj(value) {{
                const digits = String(value ?? '').replace(/\\D/g, '');
                if (digits.length !== 14) return escapeHtml(value);
                return `${{digits.slice(0, 2)}}.${{digits.slice(2, 5)}}.${{digits.slice(5, 8)}}/${{digits.slice(8, 12)}}-${{digits.slice(12)}}`;
            }}

            function formatCep(value) {{
                const digits = String(value ?? '').replace(/\\D/g, '');
                if (digits.length !== 8) return escapeHtml(value);
                return `${{digits.slice(0, 2)}}.${{digits.slice(2, 5)}}-${{digits.slice(5)}}`;
            }}

            function computeChartData(installations) {{
                const yearCounts = {{}};
                const modCounts = {{}};
                const invCounts = {{}};
                const tipoCounts = {{}};
                const classeCounts = {{}};
                const porteCounts = {{}};
                const modalidadeCounts = {{}};
                const yearModCounts = {{}};
                const modKeys = new Set();
                installations.forEach((item) => {{
                    const y = item.data_conexao_ano;
                    const mod = item.modalidade_habilitado;
                    if (y) yearCounts[y] = (yearCounts[y] || 0) + 1;
                    if (item.fabricante_modulo) modCounts[item.fabricante_modulo] = (modCounts[item.fabricante_modulo] || 0) + 1;
                    if (item.fabricante_inversor) invCounts[item.fabricante_inversor] = (invCounts[item.fabricante_inversor] || 0) + 1;
                    if (item.tipo) tipoCounts[item.tipo] = (tipoCounts[item.tipo] || 0) + 1;
                    if (item.classe) classeCounts[item.classe] = (classeCounts[item.classe] || 0) + 1;
                    if (item.porte) porteCounts[item.porte] = (porteCounts[item.porte] || 0) + 1;
                    if (mod) modalidadeCounts[mod] = (modalidadeCounts[mod] || 0) + 1;
                    if (y && mod) {{
                        const key = `${{y}}::${{mod}}`;
                        yearModCounts[key] = (yearModCounts[key] || 0) + 1;
                        modKeys.add(mod);
                    }}
                }});
                const years = Object.keys(yearCounts).sort((a, b) => a - b);
                const sortedMod = Object.entries(modCounts).sort((a, b) => b[1] - a[1]).slice(0, 15);
                const sortedInv = Object.entries(invCounts).sort((a, b) => b[1] - a[1]).slice(0, 15);
                const sortedTipo = Object.entries(tipoCounts).sort((a, b) => b[1] - a[1]);
                const sortedClasse = Object.entries(classeCounts).sort((a, b) => b[1] - a[1]);
                const sortedPorte = Object.entries(porteCounts).sort((a, b) => b[1] - a[1]);
                const sortedModalidade = Object.entries(modalidadeCounts).sort((a, b) => b[1] - a[1]);

                return {{
                    topFabricantesModulo: {{
                        labels: sortedMod.map((e) => e[0]),
                        values: sortedMod.map((e) => e[1]),
                    }},
                    topFabricantesInversor: {{
                        labels: sortedInv.map((e) => e[0]),
                        values: sortedInv.map((e) => e[1]),
                    }},
                    porTipoPF_PJ: {{
                        labels: sortedTipo.map((e) => e[0]),
                        values: sortedTipo.map((e) => e[1]),
                    }},
                    porClasse: {{
                        labels: sortedClasse.map((e) => e[0]),
                        values: sortedClasse.map((e) => e[1]),
                    }},
                    porPorte: {{
                        labels: sortedPorte.map((e) => e[0]),
                        values: sortedPorte.map((e) => e[1]),
                    }},
                    porModalidade: {{
                        labels: sortedModalidade.map((e) => e[0]),
                        values: sortedModalidade.map((e) => e[1]),
                    }},
                    seriePorModalidade: {{
                        labels: years.map(String),
                        datasets: Array.from(modKeys).sort().map((mod) => ({{
                            label: mod,
                            data: years.map((y) => yearModCounts[`${{y}}::${{mod}}`] || 0),
                        }})),
                    }},
                }};
            }}

            function renderOneChart(instance, canvas, config) {{
                if (instance) {{ instance.destroy(); instance = null; }}
                if (!canvas) return null;
                try {{
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return null;
                    const total = config.data.datasets[0]?.data.reduce((a, b) => a + b, 0) || 1;
                    const colors = config.data.labels.map((_, i) => {{
                        const ratio = total ? config.data.datasets[0].data[i] / total : 0;
                if (ratio > 0.75) return '#DC2626';
                if (ratio > 0.50) return '#F97316';
                if (ratio > 0.25) return '#FACC15';
                return '#22C55E';
                    }});
                    config.data.datasets[0].backgroundColor = colors;
                    config.data.datasets[0].borderRadius = 4;
                    return new Chart(ctx, config);
                }} catch (e) {{ return null; }}
            }}

            function renderPieChart(instance, canvas, config) {{
                if (instance) {{ instance.destroy(); instance = null; }}
                if (!canvas) return null;
                try {{
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return null;
                    const total = config.data.datasets[0]?.data.reduce((a, b) => a + b, 0) || 0;
                    config.options.plugins.tooltip = {{
                        callbacks: {{
                            label: (ctx) => {{
                                const val = ctx.parsed || 0;
                                const pct = total ? ((val / total) * 100).toFixed(1) : 0;
                                return ` ${{ctx.label}}: ${{val.toLocaleString('pt-BR')}} (${{pct}}%)`;
                            }},
                        }},
                    }};
                    return new Chart(ctx, config);
                }} catch (e) {{ return null; }}
            }}

            function makeBarConfig(labels, values, label, horizontal) {{
                return {{
                    type: 'bar',
                    data: {{ labels, datasets: [{{ label, data: values }}] }},
                    options: {{
                        indexAxis: horizontal ? 'y' : undefined,
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: false }} }},
                        scales: {{
                            x: {{ beginAtZero: true, grid: horizontal ? {{ color: '#e2e8f0' }} : {{ display: false }}, ticks: {{ font: {{ size: horizontal ? 11 : 11 }} }} }},
                            y: horizontal ? {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }} : {{ beginAtZero: true, grid: {{ color: '#e2e8f0' }}, ticks: {{ font: {{ size: 11 }} }} }},
                        }},
                    }},
                }};
            }}

            function makePieConfig(labels, values) {{
                const palette = ['#F97316','#3B82F6','#22C55E','#FACC15','#DC2626','#8B5CF6','#06B6D4','#EC4899','#14B8A6','#EAB308','#64748B','#F472B6'];
                const colors = labels.map((_, i) => palette[i % palette.length]);
                const total = values.reduce((a, b) => a + b, 0) || 1;
                const legendLabels = labels.map((label, i) => {{
                    const pct = ((values[i] / total) * 100).toFixed(1);
                    return `${{label}} (${{pct}}%)`;
                }});
                return {{
                    type: 'pie',
                    data: {{ labels: legendLabels, datasets: [{{ data: values, backgroundColor: colors, borderWidth: 0 }}] }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ position: 'bottom', labels: {{ boxWidth: 14, padding: 10, font: {{ size: 12 }} }} }},
                        }},
                    }},
                }};
            }}

            function renderStackedBar(instance, canvas, config) {{
                if (instance) {{ instance.destroy(); instance = null; }}
                if (!canvas) return null;
                try {{
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return null;
                    return new Chart(ctx, config);
                }} catch (e) {{ return null; }}
            }}

            function renderCharts(municipioName) {{
                let c;
                if (municipioName) {{
                    const rows = data.instalacoesPorMunicipio[municipioName] || [];
                    const filtered = rows.filter(passFilters);
                    c = computeChartData(filtered);
                    if (chartTitle) chartTitle.textContent = 'Graficos - ' + municipioName;
                }} else {{
                    c = data.charts || {{}};
                    if (chartTitle) chartTitle.textContent = 'Graficos - RMR';
                }}
                const sm = c.seriePorModalidade;
                if (sm && sm.labels && sm.datasets) {{
                    const palette = ['#F97316','#3B82F6','#22C55E','#FACC15','#DC2626','#8B5CF6','#06B6D4','#EC4899','#14B8A6','#EAB308'];
                    sm.datasets.forEach((ds, i) => {{
                        ds.backgroundColor = palette[i % palette.length];
                        ds.borderWidth = 0;
                    }});
                    chartSeriesModalidadeInstance = renderStackedBar(chartSeriesModalidadeInstance, chartSeriesModalidade, {{
                        type: 'bar',
                        data: {{ labels: sm.labels, datasets: sm.datasets }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {{ x: {{ stacked: true }}, y: {{ stacked: true, beginAtZero: true }} }},
                            plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, padding: 8, font: {{ size: 10 }} }} }} }},
                        }},
                    }});
                }}
                chartModulosInstance = renderOneChart(chartModulosInstance, chartModulos, makeBarConfig(
                    c.topFabricantesModulo?.labels || [], c.topFabricantesModulo?.values || [], 'Instalacoes', true
                ));
                chartInversoresInstance = renderOneChart(chartInversoresInstance, chartInversores, makeBarConfig(
                    c.topFabricantesInversor?.labels || [], c.topFabricantesInversor?.values || [], 'Instalacoes', true
                ));
                chartClasseInstance = renderPieChart(chartClasseInstance, chartClasse, makePieConfig(
                    c.porClasse?.labels || [], c.porClasse?.values || []
                ));
                chartTipoInstance = renderPieChart(chartTipoInstance, chartTipo, makePieConfig(
                    c.porTipoPF_PJ?.labels || [], c.porTipoPF_PJ?.values || []
                ));
                chartPorteInstance = renderPieChart(chartPorteInstance, chartPorte, makePieConfig(
                    c.porPorte?.labels || [], c.porPorte?.values || []
                ));
                chartModalidadeInstance = renderPieChart(chartModalidadeInstance, chartModalidade, makePieConfig(
                    c.porModalidade?.labels || [], c.porModalidade?.values || []
                ));
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
            setupFilter(filterFabMod, [...new Set(allRows.map((item) => item.fabricante_modulo).filter(Boolean))]);
            setupFilter(filterFabInv, [...new Set(allRows.map((item) => item.fabricante_inversor).filter(Boolean))]);
            setupFilter(filterModalidade, [...new Set(allRows.map((item) => item.modalidade_habilitado).filter(Boolean))]);

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
                    && (!filterBairro.value || (item.bairros_possiveis ?? [item.bairro]).includes(filterBairro.value))
                    && (!filterFabMod.value || item.fabricante_modulo === filterFabMod.value)
                    && (!filterFabInv.value || item.fabricante_inversor === filterFabInv.value)
                    && (!filterModalidade.value || item.modalidade_habilitado === filterModalidade.value);
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
                if (ratio > 0.75) return '#DC2626';
                if (ratio > 0.50) return '#F97316';
                if (ratio > 0.25) return '#FACC15';
                return '#22C55E';
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
                    {{ color: '#22C55E', label: `Ate ${{Math.round(maxValue * 0.25).toLocaleString('pt-BR')}}` }},
                    {{ color: '#FACC15', label: `${{Math.round(maxValue * 0.25).toLocaleString('pt-BR')}} a ${{Math.round(maxValue * 0.50).toLocaleString('pt-BR')}}` }},
                    {{ color: '#F97316', label: `${{Math.round(maxValue * 0.50).toLocaleString('pt-BR')}} a ${{Math.round(maxValue * 0.75).toLocaleString('pt-BR')}}` }},
                    {{ color: '#DC2626', label: `Acima de ${{Math.round(maxValue * 0.75).toLocaleString('pt-BR')}}` }},
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

            function renderLeadPins() {{
                leadLayer.clearLayers();
                (data.leads || []).forEach((lead) => {{
                    const lat = Number(lead.lat);
                    const lng = Number(lead.lng);
                    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
                    const color = leadStatusColors[lead.status] || '#64748b';
                    const icon = L.divIcon({{
                        className: '',
                        html: `<div class="rs-lead-pin" style="--lead-color:${{color}}"></div>`,
                        iconSize: [30, 42],
                        iconAnchor: [15, 39],
                        popupAnchor: [0, -38],
                    }});
                    const marker = L.marker([lat, lng], {{
                        icon,
                        pane: 'leadPane',
                        zIndexOffset: 10000,
                    }});
                    marker.bindPopup(`
                        <strong>Lead #${{escapeHtml(lead.id)}}</strong><br>
                        ${{escapeHtml(lead.nome)}}<br>
                        <span>Status: ${{escapeHtml(lead.status_label || leadStatusLabels[lead.status] || lead.status)}}</span><br>
                        ${{lead.telefone ? `<span>Contato: ${{escapeHtml(lead.telefone)}}</span><br>` : ''}}
                        ${{lead.endereco ? `<span>${{escapeHtml(lead.endereco)}}</span><br>` : ''}}
                        ${{lead.cep ? `<span>CEP: ${{escapeHtml(lead.cep)}}</span><br>` : ''}}
                        ${{lead.aproximado ? '<em>Localizacao aproximada</em><br>' : ''}}
                        ${{lead.descricao ? `<small>${{escapeHtml(lead.descricao)}}</small>` : ''}}
                    `);
                    marker.addTo(leadLayer);
                }});
            }}

            function renderPjPins() {{
                pjLayer.clearLayers();
                (data.pjs || []).forEach((pj) => {{
                    const lat = Number(pj.lat);
                    const lng = Number(pj.lng);
                    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
                    const icon = L.divIcon({{
                        className: '',
                        html: `<div class="rs-lead-pin" style="--lead-color:#7c3aed"></div>`,
                        iconSize: [30, 42],
                        iconAnchor: [15, 39],
                        popupAnchor: [0, -38],
                    }});
                    const marker = L.marker([lat, lng], {{ icon, pane: 'leadPane', zIndexOffset: 9000 }});
                    const logradouro = pj.logradouro
                        ? `${{escapeHtml(pj.logradouro)}}${{pj.numero ? ', ' + escapeHtml(pj.numero) : ''}}`
                        : '-';
                    const cidadeUf = pj.municipio
                        ? `${{escapeHtml(String(pj.municipio).toUpperCase())}}${{pj.uf ? '/' + escapeHtml(String(pj.uf).toUpperCase()) : ''}}`
                        : '-';
                    const telefone = pj.telefone1
                        ? `${{escapeHtml(pj.telefone1)}}${{pj.telefone2 ? ' / ' + escapeHtml(pj.telefone2) : ''}}`
                        : '-';
                    const modulosPotencia = `${{Number(pj.qtd_modulos || 0).toLocaleString('pt-BR')}} mod / ${{Number(pj.potencia_kw || 0).toLocaleString('pt-BR')}} kW`;
                    marker.bindPopup(`
                        <div style="font-size:13px;line-height:1.6">
                        <strong>${{escapeHtml(pj.codigo)}}</strong><br>
                        ${{escapeHtml(pj.titular)}}<br>
                        ${{formatCnpj(pj.cnpj)}}<br>
                        ${{logradouro}}<br>
                        ${{cidadeUf}}<br>
                        ${{pj.cep ? formatCep(pj.cep) : '-'}}<br>
                        ${{pj.data_instalacao ? escapeHtml(pj.data_instalacao) : '-'}}<br>
                        ${{modulosPotencia}}<br>
                        ${{telefone}}<br>
                        ${{pj.email ? escapeHtml(pj.email) : '-'}}
                        </div>
                    `);
                    marker.addTo(pjLayer);
                }});
            }}

            let pjVisible = false;

            function addLeadLegend() {{
                if (!(data.leads || []).length) return;
                const legend = L.control({{ position: 'bottomleft' }});
                legend.onAdd = () => {{
                    const div = L.DomUtil.create('div', 'rs-lead-legend');
                    L.DomEvent.disableClickPropagation(div);
                    div.innerHTML = `
                        <div class="rs-lead-legend-title">Leads</div>
                        ${{Object.entries(leadStatusColors).map(([status, color]) => `
                            <div class="rs-lead-legend-row">
                                <span class="rs-lead-legend-dot" style="background:${{color}}"></span>
                                <span>${{leadStatusLabels[status] || status}}</span>
                            </div>
                        `).join('')}}
                    `;
                    return div;
                }};
                legend.addTo(map);
            }}

            function updateLabelToggle(button) {{
                container.classList.toggle('rs-hide-labels', !labelsVisible);
                if (button) button.textContent = labelsVisible ? 'Ocultar nomes' : 'Mostrar nomes';
            }}

            function addLabelToggle() {{
                const control = L.control({{ position: 'topleft' }});
                control.onAdd = () => {{
                    const container = L.DomUtil.create('div', 'rs-label-toggle-group');
                    L.DomEvent.disableClickPropagation(container);

                    const labelBtn = L.DomUtil.create('button', 'rs-label-toggle');
                    labelBtn.type = 'button';
                    L.DomEvent.on(labelBtn, 'click', (event) => {{
                        L.DomEvent.preventDefault(event);
                        labelsVisible = !labelsVisible;
                        updateLabelToggle(labelBtn);
                    }});
                    updateLabelToggle(labelBtn);
                    container.appendChild(labelBtn);

                    if ((data.pjs || []).length) {{
                        const pjBtn = L.DomUtil.create('button', 'rs-label-toggle');
                        pjBtn.type = 'button';
                        pjBtn.style.marginTop = '4px';
                        L.DomEvent.on(pjBtn, 'click', (event) => {{
                            L.DomEvent.preventDefault(event);
                            pjVisible = !pjVisible;
                            if (pjVisible) {{
                                pjLayer.addTo(map);
                            }} else {{
                                map.removeLayer(pjLayer);
                            }}
                            pjBtn.textContent = pjVisible ? 'Ocultar empresas' : 'Mostrar empresas';
                        }});
                        pjBtn.textContent = 'Mostrar empresas';
                        container.appendChild(pjBtn);
                    }}

                    return container;
                }};
                control.addTo(map);
            }}

            function updateBackControl() {{
                if (!backControlButton) return;
                backControlButton.style.display = viewMode === 'municipio' ? 'block' : 'none';
            }}

            function addBackControl() {{
                const control = L.control({{ position: 'topright' }});
                control.onAdd = () => {{
                    const button = L.DomUtil.create('button', 'rs-map-back-control');
                    button.type = 'button';
                    button.textContent = 'Voltar';
                    backControlButton = button;
                    L.DomEvent.disableClickPropagation(button);
                    L.DomEvent.on(button, 'click', (event) => {{
                        L.DomEvent.preventDefault(event);
                        if (viewMode === 'municipio') resetToRmr();
                    }});
                    updateBackControl();
                    return button;
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
                        <td>${{escapeHtml(item.fabricante_modulo)}}</td>
                        <td>${{escapeHtml(item.fabricante_inversor)}}</td>
                        <td>${{Number(item.qtd_uc_credito).toLocaleString('pt-BR')}}</td>
                        <td>${{escapeHtml(item.cep)}}</td>
                    </tr>
                `).join('') || '<tr><td colspan="16">Nenhuma instalacao encontrada.</td></tr>';
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
                updateBackControl();
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
                            renderCharts(feature.properties.nome);
                        }});
                    }},
                }});
                addLabels(layer, (properties) => properties.nome);
                setLayer(layer);
                updateSummary();
                updateLegend(municipioMax(), 'Instalacoes');
                updateUnidentified(null);
                updateBackControl();
            }}

            function resetToRmr() {{
                viewMode = 'rmr';
                selectedMunicipio = null;
                filterBairro.value = '';
                filterFabMod.value = '';
                filterFabInv.value = '';
                updateBairroFilter();
                renderMunicipios();
                renderCharts();
                renderInstallations(1);
            }}
            prevPageButton?.addEventListener('click', () => renderTablePage(currentPage - 1));
            nextPageButton?.addEventListener('click', () => renderTablePage(currentPage + 1));
            [filterClasse, filterTipo, filterPorte, filterBairro, filterFabMod, filterFabInv, filterModalidade].forEach((select) => select.addEventListener('change', () => {{
                if (select !== filterBairro && select !== filterFabMod && select !== filterFabInv && select !== filterModalidade) updateBairroFilter();
                if (viewMode === 'municipio' && selectedMunicipio) renderBairros(selectedMunicipio.codigo, selectedMunicipio.nome);
                else renderMunicipios();
                updateSummary();
                renderInstallations(1);
                if (viewMode === 'municipio' && selectedMunicipio) renderCharts(selectedMunicipio.nome);
                else renderCharts();
            }}));
            addLegend();
            addUnidentifiedBox();
            addLabelToggle();
            addBackControl();
            addLeadLegend();
            renderLeadPins();
            renderPjPins();
            viewMode = 'rmr';
            updateBairroFilter();
            renderMunicipios();
            renderCharts();
            updateSummary();
            renderInstallations(1);
            setTimeout(() => map.invalidateSize(), 100);
        }}

        init();
    }})();
    </script>
    ''')
