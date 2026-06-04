from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / 'data' / 'raw'
ANEEL_RAW_DIR = RAW_DIR / 'aneel'
MANIFEST_PATH = ANEEL_RAW_DIR / 'manifest.json'

ANEEL_RESOURCES = {
    'empreendimentos': {
        'url': 'https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/resource/b1bd71e7-d0ad-4214-9053-cbd58e9564a7/download/empreendimento-geracao-distribuida.zip',
        'filename': 'empreendimento-geracao-distribuida.zip',
    },
    'info_tecnica_fotovoltaica': {
        'url': 'https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/resource/49fa9ca0-f609-4ae3-a6f7-b97bd0945a3a/download/empreendimento-gd-informacoes-tecnicas-fotovoltaica.csv',
        'filename': 'empreendimento-gd-informacoes-tecnicas-fotovoltaica.csv',
    },
}


@dataclass(frozen=True)
class RemoteMetadata:
    etag: str | None
    last_modified: str | None
    content_length: str | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {'resources': {}}
    with MANIFEST_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def save_manifest(manifest: dict) -> None:
    ANEEL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest['updated_at'] = utc_now_iso()
    with MANIFEST_PATH.open('w', encoding='utf-8') as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write('\n')


def fetch_remote_metadata(url: str) -> RemoteMetadata | None:
    request = Request(url, method='HEAD', headers={'User-Agent': 'RadarSolarDataPipeline/1.0'})
    try:
        with urlopen(request, timeout=30) as response:
            return RemoteMetadata(
                etag=response.headers.get('ETag'),
                last_modified=response.headers.get('Last-Modified'),
                content_length=response.headers.get('Content-Length'),
            )
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f'AVISO: nao foi possivel consultar metadados remotos: {exc}')
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_to_temp(url: str) -> Path:
    request = Request(url, headers={'User-Agent': 'RadarSolarDataPipeline/1.0'})
    temp = tempfile.NamedTemporaryFile(delete=False, prefix='aneel_', suffix='.download')
    temp_path = Path(temp.name)
    temp.close()

    try:
        with urlopen(request, timeout=120) as response, temp_path.open('wb') as file:
            shutil.copyfileobj(response, file)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return temp_path


def metadata_matches(previous: dict, remote: RemoteMetadata | None) -> bool:
    if remote is None:
        return False
    comparable = ['etag', 'last_modified', 'content_length']
    available = [field for field in comparable if getattr(remote, field) and previous.get(field)]
    if not available:
        return False
    return all(previous.get(field) == getattr(remote, field) for field in available)


def update_resource(name: str, config: dict, manifest: dict, force: bool = False) -> bool:
    ANEEL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    resources = manifest.setdefault('resources', {})
    previous = resources.get(name, {})
    destination = ANEEL_RAW_DIR / config['filename']

    print(f'\n{name}: verificando versao remota')
    remote = fetch_remote_metadata(config['url'])

    if not force and destination.exists() and metadata_matches(previous, remote):
        print(f'{name}: sem alteracao pelos metadados remotos; download ignorado')
        return False

    if force:
        print(f'{name}: download forcado')
    elif not destination.exists():
        print(f'{name}: arquivo local ausente; baixando')
    else:
        print(f'{name}: metadados mudaram ou indisponiveis; baixando para confirmar sha256')

    temp_path = download_to_temp(config['url'])
    try:
        new_sha256 = sha256_file(temp_path)
        old_sha256 = previous.get('sha256')

        if not force and destination.exists() and old_sha256 == new_sha256:
            print(f'{name}: conteudo identico pelo sha256; arquivo local mantido')
            changed = False
        else:
            shutil.move(str(temp_path), destination)
            print(f'{name}: arquivo atualizado em {destination.relative_to(BASE_DIR)}')
            changed = True

        resources[name] = {
            'url': config['url'],
            'filename': config['filename'],
            'etag': remote.etag if remote else None,
            'last_modified': remote.last_modified if remote else None,
            'content_length': remote.content_length if remote else None,
            'sha256': new_sha256,
            'downloaded_at': utc_now_iso(),
            'changed': changed,
        }
        return changed
    finally:
        temp_path.unlink(missing_ok=True)


def validate_supporting_raw_data() -> bool:
    ibge_dir = RAW_DIR / 'ibge'

    checks = [
        ('IBGE municipios PE', ibge_dir / 'PE_Municipios_2024' / 'PE_Municipios_2024.shp'),
        ('IBGE bairros PE', ibge_dir / 'PE_bairros_CD2022' / 'PE_bairros_CD2022.shp'),
        ('Correios DNE delimitado', RAW_DIR / 'correios' / 'eDNE_Basico_26031' / 'Delimitado' / 'LOG_BAIRRO.TXT'),
        ('Correios DNE faixas bairro', RAW_DIR / 'correios' / 'eDNE_Basico_26031' / 'Delimitado' / 'LOG_FAIXA_BAIRRO.TXT'),
        ('Correios DNE localidades', RAW_DIR / 'correios' / 'eDNE_Basico_26031' / 'Delimitado' / 'LOG_LOCALIDADE.TXT'),
    ]

    print('\nValidando bases auxiliares')
    all_ok = True
    for label, path in checks:
        exists = path.exists()
        status = 'OK' if exists else 'AUSENTE'
        all_ok = all_ok and exists
        print(f'- {label}: {status} ({path.relative_to(BASE_DIR)})')
    return all_ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Baixa bases ANEEL quando houver nova versao disponivel.')
    parser.add_argument('--force', action='store_true', help='Baixa novamente mesmo se metadados/sha256 indicarem igualdade.')
    parser.add_argument('--validate-only', action='store_true', help='Valida estrutura local sem baixar ANEEL.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not validate_supporting_raw_data():
        print('\nERRO: bases auxiliares obrigatorias ausentes em data/raw.', file=sys.stderr)
        return 1

    if args.validate_only:
        return 0

    manifest = load_manifest()
    any_changed = False
    for name, config in ANEEL_RESOURCES.items():
        try:
            changed = update_resource(name, config, manifest, force=args.force)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f'ERRO: falha ao baixar {name}: {exc}', file=sys.stderr)
            return 1
        any_changed = any_changed or changed

    manifest['last_run'] = {
        'checked_at': utc_now_iso(),
        'any_changed': any_changed,
    }
    save_manifest(manifest)
    print(f'\nConcluido. Houve atualizacao: {any_changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
