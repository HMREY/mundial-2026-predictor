#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v66 — Generador del UNIVERSO de selecciones nacionales del modelo internacional.

Motivación
----------
`config.TEAMS` tenía 49 selecciones (las clasificadas al Mundial 2026), pero el
histórico real (`historico_partidos.csv`) cubre **326 selecciones** y el modelo
YA se entrena sobre todas ellas (`train_tda_model` no filtra por TEAMS). El
cuello de botella era la CONFIGURACIÓN: `team_stats.json`, el selector de la UI
y el mapeo de fixtures de ESPN sólo conocían 49 códigos.

Este módulo deriva **programáticamente** desde el histórico:
  * TEAMS          — selecciones con >= UMBRAL_PARTIDOS partidos (200 con 100).
  * TEAM_NAMES_EN  — nombre exacto tal y como lo publica el dataset de Kaggle
                     (es la clave del mapeo con ESPN).
  * TEAM_STYLE     — 'bloque_alto' / 'bloque_bajo' por percentil de ELO final,
                     en vez del default ciego de `.get(equipo, 'bloque_alto')`.
  * NOMBRES_PAIS   — nombre en español para la UI.
  * ALIAS_ESPN     — nombres alternativos con los que ESPN publica al equipo
                     ("Czechia", "Türkiye", "Bosnia-Herzegovina", ...).

No se ejecuta en producción: se corre a mano y escribe `config_selecciones.py`,
que `config.py` importa. Así el criterio queda documentado y es reproducible.

Uso:
    .venv\\Scripts\\python.exe generar_universo_selecciones.py [--umbral 100]
"""

import argparse
import collections
import json
import unicodedata

import pandas as pd

HISTORICO = 'historico_partidos.csv'
SALIDA = 'config_selecciones.py'
UMBRAL_PARTIDOS = 100          # >=100 partidos desde 1990 => exactamente 200


def _norm(s: str) -> str:
    n = unicodedata.normalize('NFKD', str(s))
    n = ''.join(c for c in n if not unicodedata.combining(c)).lower()
    for ch in ".,'-/()":
        n = n.replace(ch, ' ')
    return ' '.join(n.split())


# ---------------------------------------------------------------------------
# Códigos FIFA de las selecciones que NO estaban en las 49 originales.
# Clave = nombre normalizado tal y como lo publica Kaggle (martj42).
# ---------------------------------------------------------------------------
CODIGOS_FIFA = {
    'zambia': 'ZAM', 'united arab emirates': 'UAE', 'oman': 'OMA',
    'kuwait': 'KUW', 'sweden': 'SWE', 'bahrain': 'BHR',
    'trinidad and tobago': 'TRI', 'thailand': 'THA', 'south africa': 'RSA',
    'poland': 'POL', 'china': 'CHN', 'china pr': 'CHN', 'iraq': 'IRQ',
    'estonia': 'EST', 'el salvador': 'SLV', 'uganda': 'UGA',
    'turkey': 'TUR', 'turkiye': 'TUR', 'finland': 'FIN', 'romania': 'ROU',
    'russia': 'RUS', 'kenya': 'KEN', 'mali': 'MLI', 'greece': 'GRE',
    'singapore': 'SGP', 'republic of ireland': 'IRL', 'ireland': 'IRL',
    'malawi': 'MWI', 'hungary': 'HUN', 'burkina faso': 'BFA', 'syria': 'SYR',
    'tanzania': 'TAN', 'iceland': 'ISL', 'malaysia': 'MAS',
    'venezuela': 'VEN', 'zimbabwe': 'ZIM', 'guatemala': 'GUA',
    'czech republic': 'CZE', 'czechia': 'CZE', 'bolivia': 'BOL',
    'latvia': 'LVA', 'slovakia': 'SVK', 'angola': 'ANG', 'indonesia': 'IDN',
    'dr congo': 'COD', 'congo dr': 'COD', 'lithuania': 'LTU',
    'bulgaria': 'BUL', 'sudan': 'SDN', 'malta': 'MLT', 'ukraine': 'UKR',
    'mozambique': 'MOZ', 'slovenia': 'SVN', 'botswana': 'BOT',
    'gabon': 'GAB', 'cyprus': 'CYP', 'albania': 'ALB', 'wales': 'WAL',
    'azerbaijan': 'AZE', 'togo': 'TOG', 'israel': 'ISR', 'georgia': 'GEO',
    'guinea': 'GUI', 'north macedonia': 'MKD', 'macedonia': 'MKD',
    'northern ireland': 'NIR', 'india': 'IND', 'haiti': 'HAI',
    'belarus': 'BLR', 'lebanon': 'LIB', 'moldova': 'MDA', 'vietnam': 'VIE',
    'luxembourg': 'LUX', 'bosnia and herzegovina': 'BIH',
    'bosnia herzegovina': 'BIH', 'namibia': 'NAM', 'cuba': 'CUB',
    'north korea': 'PRK', 'korea dpr': 'PRK', 'armenia': 'ARM',
    'rwanda': 'RWA', 'kazakhstan': 'KAZ', 'lesotho': 'LES',
    'faroe islands': 'FRO', 'myanmar': 'MYA', 'eswatini': 'SWZ',
    'swaziland': 'SWZ', 'liechtenstein': 'LIE', 'hong kong': 'HKG',
    'ethiopia': 'ETH', 'philippines': 'PHI', 'libya': 'LBY',
    'benin': 'BEN', 'congo': 'CGO', 'yemen': 'YEM', 'bangladesh': 'BAN',
    'andorra': 'AND', 'madagascar': 'MAD', 'san marino': 'SMR',
    'palestine': 'PLE', 'maldives': 'MDV', 'mauritius': 'MRI',
    'barbados': 'BRB', 'martinique': 'MTQ', 'saint kitts and nevis': 'SKN',
    'nepal': 'NEP', 'sri lanka': 'SRI', 'cambodia': 'CAM',
    'liberia': 'LBR', 'grenada': 'GRN', 'tajikistan': 'TJK',
    'burundi': 'BDI', 'mauritania': 'MTN', 'antigua and barbuda': 'ATG',
    'niger': 'NIG', 'sierra leone': 'SLE', 'suriname': 'SUR',
    'kyrgyzstan': 'KGZ', 'laos': 'LAO', 'guyana': 'GUY',
    'saint lucia': 'LCA', 'curacao': 'CUW', 'fiji': 'FIJ',
    'gambia': 'GAM', 'nicaragua': 'NCA', 'solomon islands': 'SOL',
    'turkmenistan': 'TKM', 'saint vincent and the grenadines': 'VIN',
    'guadeloupe': 'GPE', 'montenegro': 'MNE', 'equatorial guinea': 'EQG',
    'pakistan': 'PAK', 'bermuda': 'BER', 'gibraltar': 'GIB',
    'seychelles': 'SEY', 'new caledonia': 'NCL', 'vanuatu': 'VAN',
    'dominican republic': 'DOM', 'taiwan': 'TPE', 'chinese taipei': 'TPE',
    'dominica': 'DMA', 'comoros': 'COM', 'tahiti': 'TAH',
    'guinea bissau': 'GNB', 'french guiana': 'GYF', 'afghanistan': 'AFG',
    'jersey': 'JEY', 'puerto rico': 'PUR', 'macau': 'MAC', 'belize': 'BLZ',
    'british virgin islands': 'VGB', 'cayman islands': 'CAY', 'guam': 'GUM',
    'guernsey': 'GGY', 'chad': 'CHA', 'central african republic': 'CTA',
    'kosovo': 'KVX', 'papua new guinea': 'PNG', 'brunei': 'BRU',
    'zanzibar': 'ZAN', 'bhutan': 'BHU',
    # Reserva (por debajo del umbral hoy, pero si el histórico crece entran
    # solas sin tocar código).
    'south sudan': 'SSD', 'somalia': 'SOM', 'djibouti': 'DJI',
    'eritrea': 'ERI', 'mongolia': 'MNG', 'timor leste': 'TLS',
    'bahamas': 'BAH', 'aruba': 'ARU', 'us virgin islands': 'VIR',
    'united states virgin islands': 'VIR', 'british virgin islands ': 'VGB',
    'anguilla': 'AIA', 'montserrat': 'MSR', 'turks and caicos islands': 'TCA',
    'sao tome and principe': 'STP', 'american samoa': 'ASA', 'samoa': 'SAM',
    'tonga': 'TGA', 'cook islands': 'COK', 'sint maarten': 'SMA',
    'bonaire': 'BOE', 'saint martin': 'SMT', 'kiribati': 'KIR',
    'tuvalu': 'TUV', 'nauru': 'NRU', 'niue': 'NIU', 'palau': 'PLW',
    'northern mariana islands': 'NMI', 'greenland': 'GRL',
    'monaco': 'MON', 'vatican city': 'VAT',
}

# ---------------------------------------------------------------------------
# Nombre en español para la UI (clave = nombre normalizado en inglés).
# Los que no estén aquí conservan el nombre en inglés (degradación limpia).
# ---------------------------------------------------------------------------
NOMBRES_ES = {
    'zambia': 'Zambia', 'united arab emirates': 'Emiratos Árabes Unidos',
    'oman': 'Omán', 'kuwait': 'Kuwait', 'sweden': 'Suecia',
    'bahrain': 'Baréin', 'trinidad and tobago': 'Trinidad y Tobago',
    'thailand': 'Tailandia', 'south africa': 'Sudáfrica', 'poland': 'Polonia',
    'china': 'China', 'iraq': 'Irak', 'estonia': 'Estonia',
    'el salvador': 'El Salvador', 'uganda': 'Uganda', 'turkey': 'Turquía',
    'finland': 'Finlandia', 'romania': 'Rumanía', 'russia': 'Rusia',
    'kenya': 'Kenia', 'mali': 'Malí', 'greece': 'Grecia',
    'singapore': 'Singapur', 'republic of ireland': 'Irlanda',
    'malawi': 'Malaui', 'hungary': 'Hungría', 'burkina faso': 'Burkina Faso',
    'syria': 'Siria', 'tanzania': 'Tanzania', 'iceland': 'Islandia',
    'malaysia': 'Malasia', 'venezuela': 'Venezuela', 'zimbabwe': 'Zimbabue',
    'guatemala': 'Guatemala', 'czech republic': 'Chequia', 'bolivia': 'Bolivia',
    'latvia': 'Letonia', 'slovakia': 'Eslovaquia', 'angola': 'Angola',
    'indonesia': 'Indonesia', 'dr congo': 'RD Congo', 'lithuania': 'Lituania',
    'bulgaria': 'Bulgaria', 'sudan': 'Sudán', 'malta': 'Malta',
    'ukraine': 'Ucrania', 'mozambique': 'Mozambique', 'slovenia': 'Eslovenia',
    'botswana': 'Botsuana', 'gabon': 'Gabón', 'cyprus': 'Chipre',
    'albania': 'Albania', 'wales': 'Gales', 'azerbaijan': 'Azerbaiyán',
    'togo': 'Togo', 'israel': 'Israel', 'georgia': 'Georgia',
    'guinea': 'Guinea', 'north macedonia': 'Macedonia del Norte',
    'northern ireland': 'Irlanda del Norte', 'india': 'India', 'haiti': 'Haití',
    'belarus': 'Bielorrusia', 'lebanon': 'Líbano', 'moldova': 'Moldavia',
    'vietnam': 'Vietnam', 'luxembourg': 'Luxemburgo',
    'bosnia and herzegovina': 'Bosnia y Herzegovina', 'namibia': 'Namibia',
    'cuba': 'Cuba', 'north korea': 'Corea del Norte', 'armenia': 'Armenia',
    'rwanda': 'Ruanda', 'kazakhstan': 'Kazajistán', 'lesotho': 'Lesoto',
    'faroe islands': 'Islas Feroe', 'myanmar': 'Myanmar',
    'eswatini': 'Esuatini', 'liechtenstein': 'Liechtenstein',
    'hong kong': 'Hong Kong', 'ethiopia': 'Etiopía', 'philippines': 'Filipinas',
    'libya': 'Libia', 'benin': 'Benín', 'congo': 'Congo', 'yemen': 'Yemen',
    'bangladesh': 'Bangladés', 'andorra': 'Andorra', 'madagascar': 'Madagascar',
    'san marino': 'San Marino', 'palestine': 'Palestina',
    'maldives': 'Maldivas', 'mauritius': 'Mauricio', 'barbados': 'Barbados',
    'martinique': 'Martinica', 'saint kitts and nevis': 'San Cristóbal y Nieves',
    'nepal': 'Nepal', 'sri lanka': 'Sri Lanka', 'cambodia': 'Camboya',
    'liberia': 'Liberia', 'grenada': 'Granada', 'tajikistan': 'Tayikistán',
    'burundi': 'Burundi', 'mauritania': 'Mauritania',
    'antigua and barbuda': 'Antigua y Barbuda', 'niger': 'Níger',
    'sierra leone': 'Sierra Leona', 'suriname': 'Surinam',
    'kyrgyzstan': 'Kirguistán', 'laos': 'Laos', 'guyana': 'Guyana',
    'saint lucia': 'Santa Lucía', 'curacao': 'Curazao', 'fiji': 'Fiyi',
    'gambia': 'Gambia', 'nicaragua': 'Nicaragua',
    'solomon islands': 'Islas Salomón', 'turkmenistan': 'Turkmenistán',
    'saint vincent and the grenadines': 'San Vicente y las Granadinas',
    'guadeloupe': 'Guadalupe', 'montenegro': 'Montenegro',
    'equatorial guinea': 'Guinea Ecuatorial', 'pakistan': 'Pakistán',
    'bermuda': 'Bermudas', 'gibraltar': 'Gibraltar', 'seychelles': 'Seychelles',
    'new caledonia': 'Nueva Caledonia', 'vanuatu': 'Vanuatu',
    'dominican republic': 'República Dominicana', 'taiwan': 'Taipéi Chino',
    'dominica': 'Dominica', 'comoros': 'Comoras', 'tahiti': 'Tahití',
    'guinea bissau': 'Guinea-Bisáu', 'french guiana': 'Guayana Francesa',
    'afghanistan': 'Afganistán', 'jersey': 'Jersey', 'puerto rico': 'Puerto Rico',
    'macau': 'Macao', 'belize': 'Belice',
    'british virgin islands': 'Islas Vírgenes Británicas',
    'cayman islands': 'Islas Caimán', 'guam': 'Guam', 'guernsey': 'Guernsey',
    'chad': 'Chad', 'central african republic': 'República Centroafricana',
    'kosovo': 'Kosovo', 'papua new guinea': 'Papúa Nueva Guinea',
    'brunei': 'Brunéi', 'zanzibar': 'Zanzíbar', 'bhutan': 'Bután',
}

# ---------------------------------------------------------------------------
# Alias con los que OTRAS fuentes (sobre todo ESPN) publican al equipo.
# Se añaden al catálogo de la UI para que el mapeo sea EXACTO y no dependa del
# fuzzy (con 200 selecciones el fuzzy confunde Congo/DR Congo, Guinea/Guinea
# Ecuatorial, Sudán/Sudán del Sur...).
# ---------------------------------------------------------------------------
ALIAS_EXTRA = {
    'CZE': ['Czechia', 'Czech Republic'],
    'TUR': ['Türkiye', 'Turkiye', 'Turkey'],
    'IRL': ['Republic of Ireland', 'Ireland', 'Rep. of Ireland'],
    'BIH': ['Bosnia-Herzegovina', 'Bosnia and Herzegovina', 'Bosnia & Herzegovina'],
    'MKD': ['North Macedonia', 'Macedonia', 'FYR Macedonia'],
    'PRK': ['North Korea', 'Korea DPR', 'Korea Republic DPR'],
    'KOR': ['South Korea', 'Korea Republic'],
    'CHN': ['China', 'China PR'],
    'TPE': ['Chinese Taipei', 'Taiwan'],
    'COD': ['DR Congo', 'Congo DR', 'Democratic Republic of the Congo',
            'Congo-Kinshasa'],
    'CGO': ['Congo', 'Congo Republic', 'Congo-Brazzaville'],
    'SWZ': ['Eswatini', 'Swaziland'],
    'CPV': ['Cape Verde', 'Cabo Verde'],
    'CIV': ['Ivory Coast', "Côte d'Ivoire", 'Cote dIvoire'],
    'USA': ['United States', 'USA', 'United States of America'],
    'CUW': ['Curaçao', 'Curacao'],
    'KVX': ['Kosovo'],
    'VIN': ['Saint Vincent and the Grenadines', 'St. Vincent & Grenadines',
            'St Vincent and the Grenadines'],
    'SKN': ['Saint Kitts and Nevis', 'St. Kitts & Nevis'],
    'LCA': ['Saint Lucia', 'St. Lucia'],
    'ATG': ['Antigua and Barbuda', 'Antigua & Barbuda'],
    'TRI': ['Trinidad and Tobago', 'Trinidad & Tobago'],
    'NED': ['Netherlands', 'Holland'],
    'GNB': ['Guinea-Bissau', 'Guinea Bissau'],
    'EQG': ['Equatorial Guinea'],
    'VGB': ['British Virgin Islands'],
    'VIR': ['US Virgin Islands', 'U.S. Virgin Islands'],
    'IRN': ['Iran', 'IR Iran'],
    'KSA': ['Saudi Arabia'],
    'UAE': ['United Arab Emirates', 'UAE'],
    'RSA': ['South Africa'],
    'SDN': ['Sudan'],
    'SSD': ['South Sudan'],
}


def cargar_conteo(historico: str = HISTORICO) -> collections.Counter:
    df = pd.read_csv(historico, usecols=['home_team', 'away_team'])
    return collections.Counter(df['home_team'].tolist() + df['away_team'].tolist())


def elo_final(historico: str = HISTORICO) -> dict:
    """ELO final por selección replayando el histórico (mismo K que data_fetcher)."""
    df = pd.read_csv(historico, parse_dates=['date'],
                     usecols=['date', 'MATCH_ID', 'home_team', 'away_team',
                              'home_goals', 'away_goals', 'tournament'])
    df = df.sort_values(['date', 'MATCH_ID'], kind='mergesort')
    elo = {}
    for f in df.itertuples(index=False):
        rh, ra = elo.get(f.home_team, 1500.0), elo.get(f.away_team, 1500.0)
        eh = 1 / (1 + 10 ** ((ra - rh) / 400))
        sh = 1.0 if f.home_goals > f.away_goals else (0.5 if f.home_goals == f.away_goals else 0.0)
        k = 48 if 'World Cup' in str(f.tournament) else (20 if 'Friendly' in str(f.tournament) else 32)
        elo[f.home_team] = rh + k * (sh - eh)
        elo[f.away_team] = ra + k * ((1 - sh) - (1 - eh))
    return elo


def construir(umbral: int = UMBRAL_PARTIDOS) -> dict:
    # Referencia = SIEMPRE las 49 del Mundial 2026 (no `config.TEAMS`, que ya
    # puede venir ampliado por una ejecución anterior de este mismo generador).
    from config import TEAMS_MUNDIAL_2026 as TEAMS_ACTUAL
    import config as _c
    # Códigos ya conocidos (49 originales + los que generó una corrida previa):
    # el histórico puede venir ya migrado a códigos, y hay que reconocerlos.
    EN_ACTUAL = dict(_c.TEAM_NAMES_EN)
    CODIGOS_CONOCIDOS = set(EN_ACTUAL)

    conteo = cargar_conteo()
    elos = elo_final()
    presentes = {n: c for n, c in conteo.items() if c >= umbral}

    # nombre-del-histórico -> (codigo, nombre_en)
    inverso_actual = {v: k for k, v in EN_ACTUAL.items()}
    filas, sin_codigo = [], []
    for nombre, n in sorted(presentes.items(), key=lambda kv: -kv[1]):
        if nombre in CODIGOS_CONOCIDOS:                  # ya es código FIFA
            codigo, nombre_en = nombre, EN_ACTUAL[nombre]
        elif nombre in inverso_actual:
            codigo, nombre_en = inverso_actual[nombre], nombre
        else:
            codigo = CODIGOS_FIFA.get(_norm(nombre))
            nombre_en = nombre
            if not codigo:
                sin_codigo.append(nombre)
                continue
        filas.append({'codigo': codigo, 'nombre_en': nombre_en,
                      'partidos': n, 'elo': round(elos.get(nombre, 1500.0), 1),
                      'nombre_es': NOMBRES_ES.get(_norm(nombre_en), nombre_en)})

    if sin_codigo:
        raise SystemExit(f"❌ {len(sin_codigo)} selecciones sin código FIFA: {sin_codigo}")

    dup = [c for c, k in collections.Counter(f['codigo'] for f in filas).items() if k > 1]
    if dup:
        raise SystemExit(f"❌ códigos duplicados: {dup}")

    # ---- TEAM_STYLE por percentil de ELO -----------------------------------
    # Criterio (v66): las selecciones del cuartil superior de ELO son las que
    # de verdad imponen el balón => 'bloque_alto'. El resto, 'bloque_bajo'.
    # Antes, las 277 selecciones fuera de la lista caían todas en el default
    # 'bloque_alto' de `.get()`, lo que anulaba la feature CHOQUE_ESTILOS.
    serie = pd.Series({f['codigo']: f['elo'] for f in filas})
    corte = float(serie.quantile(0.75))
    for f in filas:
        f['estilo'] = 'bloque_alto' if f['elo'] >= corte else 'bloque_bajo'

    return {'filas': filas, 'corte_elo': corte, 'umbral': umbral,
            'previos': list(TEAMS_ACTUAL)}


def _bloque_dict(nombre: str, pares, comentario: str = '') -> str:
    linea = [f'{comentario}{nombre} = {{']
    for k, v in pares:
        linea.append(f"    {k!r}: {v!r},")
    linea.append('}')
    return '\n'.join(linea)


def escribir(datos: dict, salida: str = SALIDA) -> None:
    filas = sorted(datos['filas'], key=lambda f: f['codigo'])
    previos = datos['previos']
    codigos = [f['codigo'] for f in filas]

    partes = ['#!/usr/bin/env python3', '# -*- coding: utf-8 -*-',
              '"""', 'v66 — Universo de selecciones nacionales del modelo internacional.',
              '',
              'GENERADO AUTOMÁTICAMENTE por `generar_universo_selecciones.py`.',
              'NO editar a mano: vuelve a ejecutar el generador.',
              '',
              f'Criterio: selecciones con >= {datos["umbral"]} partidos en '
              f'{HISTORICO} (desde 1990).',
              f'Resultado: {len(filas)} selecciones (antes {len(previos)}).',
              f'TEAM_STYLE: "bloque_alto" si ELO final >= {datos["corte_elo"]:.1f} '
              '(percentil 75), si no "bloque_bajo".',
              '"""', '']

    partes.append('# Las 49 selecciones del Mundial 2026: se conservan como '
                  'subconjunto de referencia')
    partes.append('# para poder comparar la precisión manzana-con-manzana con '
                  'el modelo previo a v66.')
    partes.append('TEAMS_MUNDIAL_2026 = [')
    for i in range(0, len(previos), 10):
        partes.append('    ' + ', '.join(repr(c) for c in previos[i:i + 10]) + ',')
    partes.append(']')
    partes.append('')

    partes.append(f'# {len(codigos)} selecciones con historial suficiente.')
    partes.append('TEAMS = [')
    for i in range(0, len(codigos), 10):
        partes.append('    ' + ', '.join(repr(c) for c in codigos[i:i + 10]) + ',')
    partes.append(']')
    partes.append('')

    partes.append('# Nombre EXACTO del dataset de Kaggle/ESPN (clave del mapeo de fixtures).')
    partes.append(_bloque_dict('TEAM_NAMES_EN', [(f['codigo'], f['nombre_en']) for f in filas]))
    partes.append('')
    partes.append(_bloque_dict('TEAM_STYLE', [(f['codigo'], f['estilo']) for f in filas]))
    partes.append('')
    partes.append('# Nombre en español para la interfaz.')
    partes.append(_bloque_dict('TEAM_NAMES_ES', [(f['codigo'], f['nombre_es']) for f in filas]))
    partes.append('')
    partes.append('# Partidos en el histórico (insumo de la feature NIVEL_DATOS y de la UI).')
    partes.append(_bloque_dict('TEAM_PARTIDOS', [(f['codigo'], f['partidos']) for f in filas]))
    partes.append('')
    partes.append('# ELO final replayando el histórico. Lo usa el generador sintético para')
    partes.append('# estimar el "tier" de las selecciones que no están en su tabla manual:')
    partes.append('# sin esto, las 151 nuevas compartían todas el tier por defecto 0.5 y el')
    partes.append('# aumento de datos generaba partidos irrealmente parejos.')
    partes.append(_bloque_dict('TEAM_ELO', [(f['codigo'], f['elo']) for f in filas]))
    partes.append('')
    partes.append('# Alias con los que otras fuentes publican al equipo (mapeo EXACTO,')
    partes.append('# imprescindible con 200 selecciones para que el fuzzy no confunda')
    partes.append('# Congo/RD Congo, Guinea/Guinea Ecuatorial, Sudán/Sudán del Sur...).')
    alias = {f['codigo']: sorted(set(ALIAS_EXTRA.get(f['codigo'], []) + [f['nombre_en']]))
             for f in filas}
    partes.append(_bloque_dict('TEAM_ALIAS', sorted(alias.items())))
    partes.append('')

    with open(salida, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(partes) + '\n')

    resumen = {
        'umbral_partidos': datos['umbral'],
        'n_selecciones': len(filas),
        'n_previas': len(previos),
        'corte_elo_estilo': round(datos['corte_elo'], 1),
        'bloque_alto': sum(1 for f in filas if f['estilo'] == 'bloque_alto'),
        'bloque_bajo': sum(1 for f in filas if f['estilo'] == 'bloque_bajo'),
        'nuevas': sorted(c for c in codigos if c not in previos),
    }
    with open('universo_selecciones.json', 'w', encoding='utf-8') as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=1)
    print(f"✅ {salida}: {len(filas)} selecciones "
          f"({resumen['bloque_alto']} bloque alto / {resumen['bloque_bajo']} bajo). "
          f"Nuevas: {len(resumen['nuevas'])}.")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--umbral', type=int, default=UMBRAL_PARTIDOS)
    a = ap.parse_args()
    escribir(construir(a.umbral))
