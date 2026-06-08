from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

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


@lru_cache(maxsize=1)
def carregar_geojson_rmr() -> dict:
    municipios = []
    municipios_por_codigo = {}

    municipio_reader = shapefile.Reader(str(MUNICIPIOS_SHP), encoding='cp1252')
    for shape_record in municipio_reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        codigo_municipio = record['CD_MUN']
        if codigo_municipio not in RMR_MUNICIPIOS:
            continue

        feature = _feature(
            shape_record.shape.__geo_interface__,
            {
                'codigo': codigo_municipio,
                'nome': record['NM_MUN'],
                'tipo': 'municipio',
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

    return {
        'municipios': _feature_collection(municipios),
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
            height: calc(100vh - 164px);
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
    </style>
    ''')

    with ui.column().classes('w-full min-h-screen gap-5 p-6'):
        with ui.row().classes('w-full items-end justify-between gap-4'):
            with ui.column().classes('gap-1'):
                ui.label('Demo mapa RMR').classes('text-3xl font-bold text-slate-900')
                ui.label('Clique em um municipio para abrir a visao por bairros.').classes('text-base text-slate-600')
            ui.button('Voltar para municipios', on_click=None).props('outline color=primary').classes('rs-map-reset')

        ui.html('<div id="demo-mapa-rmr"></div>').classes('w-full')

    ui.add_body_html(f'''
    <script>
    (() => {{
        const data = {payload};
        function init(attempt = 0) {{
            const container = document.getElementById('demo-mapa-rmr');
            const resetButton = document.querySelector('.rs-map-reset');
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

            const municipioStyle = {{
                color: '#1D293B',
                weight: 1.4,
                fillColor: '#F97316',
                fillOpacity: 0.32,
            }};
            const bairroStyle = {{
                color: '#0F172A',
                weight: 1.1,
                fillColor: '#38BDF8',
                fillOpacity: 0.28,
            }};
            const selectedMunicipioStyle = {{
                color: '#F97316',
                weight: 2.6,
                fillColor: '#F97316',
                fillOpacity: 0.18,
            }};

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

            function renderMunicipios() {{
                const layer = L.geoJSON(data.municipios, {{
                    style: municipioStyle,
                    onEachFeature: (feature, item) => {{
                        item.on('mouseover', () => item.setStyle(selectedMunicipioStyle));
                        item.on('mouseout', () => item.setStyle(municipioStyle));
                        item.on('click', () => renderBairros(feature.properties.codigo, feature.properties.nome));
                    }},
                }});
                addLabels(layer, (properties) => properties.nome);
                setLayer(layer);
            }}

            function renderBairros(codigoMunicipio, nomeMunicipio) {{
                const bairros = data.bairrosPorMunicipio[codigoMunicipio];
                const layer = L.geoJSON(bairros, {{
                    style: bairroStyle,
                    onEachFeature: (feature, item) => {{
                        item.bindPopup(`<strong>${{feature.properties.nome}}</strong><br>${{nomeMunicipio}}`);
                    }},
                }});
                addLabels(layer, (properties) => properties.nome);
                setLayer(layer);
            }}

            resetButton?.addEventListener('click', renderMunicipios);
            renderMunicipios();
            setTimeout(() => map.invalidateSize(), 100);
        }}

        init();
    }})();
    </script>
    ''')
