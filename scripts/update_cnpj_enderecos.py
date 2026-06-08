from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.database import db
from src.models import CnpjCache

BASE_DIR = Path(__file__).resolve().parent.parent
EMPREENDIMENTOS_CSV = BASE_DIR / 'data' / 'processed' / 'aneel' / 'empreendimento-geracao-distribuida-rmr.csv'
PARQUET_PATH = BASE_DIR / 'data' / 'processed' / 'aneel' / 'rmr_instalacoes.parquet'

DELAY_SECONDS = 3.5


def only_digits(value: object) -> str:
    return ''.join(ch for ch in str(value) if ch.isdigit())


def carregar_cnpjs_do_csv() -> list[str]:
    if not EMPREENDIMENTOS_CSV.exists():
        print(f'Arquivo nao encontrado: {EMPREENDIMENTOS_CSV}')
        return []

    linhas = EMPREENDIMENTOS_CSV.read_text(encoding='latin1').splitlines()
    if not linhas:
        return []

    header = linhas[0].split(';')
    try:
        idx = header.index('NumCPFCNPJ')
    except ValueError:
        print('Coluna NumCPFCNPJ nao encontrada no CSV.')
        return []

    cnpjs_unicos: set[str] = set()
    for linha in linhas[1:]:
        partes = linha.split(';')
        if idx >= len(partes):
            continue
        cnpj_raw = only_digits(partes[idx])
        if len(cnpj_raw) == 14:
            cnpjs_unicos.add(cnpj_raw)

    return sorted(cnpjs_unicos)


def consultar_brasilapi(cnpj: str) -> dict | None:
    url = f'https://brasilapi.com.br/api/cnpj/v1/{cnpj}'
    request = Request(url, headers={'User-Agent': 'RadarSolar/1.0'})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        if exc.code == 404:
            print(f'  CNPJ {cnpj} nao encontrado (404)')
            return {'cnpj': cnpj, 'razao_social': None}
        if exc.code == 429:
            print(f'  Rate limited. Aguardando...')
            time.sleep(10)
            return consultar_brasilapi(cnpj)
        print(f'  HTTP {exc.code} para {cnpj}')
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f'  Erro na requisicao {cnpj}: {exc}')
        return None


def extrair_dados_cnpj(dados: dict) -> dict:
    endereco = dados.get('estabelecimento') or dados
    return {
        'cnpj': only_digits(dados.get('cnpj', '')),
        'razao_social': dados.get('razao_social'),
        'nome_fantasia': dados.get('nome_fantasia'),
        'logradouro': endereco.get('logradouro'),
        'numero': endereco.get('numero'),
        'complemento': endereco.get('complemento'),
        'cep': only_digits(endereco.get('cep', '')),
        'bairro': endereco.get('bairro'),
        'cidade': endereco.get('cidade'),
        'estado': endereco.get('uf') or endereco.get('estado'),
        'telefone1': endereco.get('telefone1'),
        'telefone2': endereco.get('telefone2'),
        'email': endereco.get('email'),
    }


GEOCODING_DELAY = 1.1
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'


def montar_endereco_completo(dados: dict) -> str | None:
    end = dados.get('estabelecimento') or dados
    partes = [end.get('logradouro'), end.get('numero'), end.get('bairro'),
              end.get('cidade'), end.get('uf') or end.get('estado')]
    partes = [p for p in partes if p]
    if not partes:
        return None
    return ', '.join(partes)


def geocodificar(endereco: str) -> tuple[float | None, float | None]:
    params = f'?q={quote(endereco)}&format=json&limit=1'
    request = Request(f'{NOMINATIM_URL}{params}',
                      headers={'User-Agent': 'RadarSolar/1.0 (geocoding)'})
    try:
        with urlopen(request, timeout=10) as resp:
            resultados = json.loads(resp.read().decode('utf-8'))
        if resultados:
            return (float(resultados[0]['lat']), float(resultados[0]['lon']))
    except (URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        print(f'    Erro geocodificacao: {exc}')
    return (None, None)


def carregar_cnpj_por_empreendimento() -> dict[str, str]:
    colunas = ['CodEmpreendimento', 'NumCPFCNPJ', 'SigTipoConsumidor']
    df = pd.read_csv(EMPREENDIMENTOS_CSV, sep=';', encoding='latin1', usecols=colunas)
    df = df[df['SigTipoConsumidor'] == 'PJ']
    mapa: dict[str, str] = {}
    for _, row in df.iterrows():
        cnpj = only_digits(row['NumCPFCNPJ'])
        if len(cnpj) == 14:
            mapa[str(row['CodEmpreendimento']).strip()] = cnpj
    return mapa


def atualizar_parquet() -> None:
    if not PARQUET_PATH.exists():
        print('  Parquet nao encontrado, pulando.')
        return

    cnpj_por_emp = carregar_cnpj_por_empreendimento()
    cache_por_cnpj: dict[str, CnpjCache] = {
        c.cnpj: c for c in CnpjCache.select()
    }
    if not cache_por_cnpj:
        print('  Cache vazio, nada a atualizar.')
        return

    df = pd.read_parquet(PARQUET_PATH)
    mask_pj = df['tipo_consumidor'] == 'PJ'
    atualizados_cep = 0
    atualizados_bairro = 0

    for idx in df[mask_pj].index:
        cod_emp = str(df.at[idx, 'cod_empreendimento']).strip()
        cnpj = cnpj_por_emp.get(cod_emp)
        if not cnpj:
            continue
        cache = cache_por_cnpj.get(cnpj)
        if not cache:
            continue

        cep_cache = only_digits(cache.cep or '')
        if len(cep_cache) == 8:
            cep_atual = str(df.at[idx, 'cep_original'] or '').strip()
            if cep_atual != cep_cache:
                df.at[idx, 'cep_original'] = cep_cache
                df.at[idx, 'cep_prefixo'] = cep_cache[:5]
                atualizados_cep += 1

        if cache.bairro:
            bairro_atual = str(df.at[idx, 'bairro_estimado'] or '').strip()
            if bairro_atual != cache.bairro:
                df.at[idx, 'bairro_estimado'] = cache.bairro
                atualizados_bairro += 1

    print(f'  CEPs atualizados: {atualizados_cep}')
    print(f'  Bairros atualizados: {atualizados_bairro}')

    if atualizados_cep or atualizados_bairro:
        df.to_parquet(PARQUET_PATH, index=False)
        print(f'  Parquet salvo.')


def main() -> int:
    db.connect()
    db.create_tables([CnpjCache])

    ja_cacheados = {c.cnpj for c in CnpjCache.select(CnpjCache.cnpj)}
    cnpjs_pendentes = [c for c in carregar_cnpjs_do_csv() if c not in ja_cacheados]

    print(f'CNPJs no CSV: {len(ja_cacheados) + len(cnpjs_pendentes)}')
    print(f'Ja cacheados: {len(ja_cacheados)}')
    print(f'Pendentes: {len(cnpjs_pendentes)}')

    if not cnpjs_pendentes:
        print('Nada a fazer.')
        db.close()
        return 0

    for i, cnpj in enumerate(cnpjs_pendentes, start=1):
        print(f'[{i}/{len(cnpjs_pendentes)}] Consultando {cnpj}...')
        dados = consultar_brasilapi(cnpj)
        if dados is None:
            print(f'  Pulando {cnpj} apos erro.')
            time.sleep(DELAY_SECONDS)
            continue

        endereco = montar_endereco_completo(dados)
        lat = lng = None
        if endereco:
            print(f'  Geocodificando: {endereco}')
            lat, lng = geocodificar(endereco)
            if lat and lng:
                print(f'    -> {lat:.5f}, {lng:.5f}')
            else:
                print('    -> sem coordenadas')
            time.sleep(GEOCODING_DELAY)

        with db.atomic():
            CnpjCache.get_or_create(
                cnpj=only_digits(dados.get('cnpj', cnpj)),
                defaults={
                    **extrair_dados_cnpj(dados),
                    'latitude': lat,
                    'longitude': lng,
                    'fetched_at': __import__('datetime').datetime.now(),
                },
            )

        if i < len(cnpjs_pendentes):
            time.sleep(DELAY_SECONDS)

    print('Atualizando parquet com dados do cache...')
    atualizar_parquet()

    print('Concluido.')
    db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
