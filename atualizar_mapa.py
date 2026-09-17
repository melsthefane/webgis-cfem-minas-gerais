import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from io import BytesIO

import folium
import geopandas as gpd
import pandas as pd
import requests


# ============================================================
# WEBGIS CFEM - MINAS GERAIS
# ETAPA 10
# RESPONSIVIDADE + FILTRO DE UM OU MÚLTIPLOS MESES
# ============================================================

URL_CFEM = (
    "https://dadosabertos.anm.gov.br/CFEM/"
    "CFEM_Arrecadacao_2022_2026.csv"
)

ARQUIVO_MUNICIPIOS = "municipios_mg.geojson"
ARQUIVO_SAIDA = "index.html"
ARQUIVO_DADOS = "dados_cfem.json"

print("=" * 70)
print("WEBGIS CFEM - MINAS GERAIS")
print("RESPONSIVIDADE + FILTRO MENSAL")
print("=" * 70)


# ============================================================
# 1. DOWNLOAD ANM
# ============================================================

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}

print("\nBaixando CSV da ANM...")

response = requests.get(
    URL_CFEM,
    headers=headers,
    timeout=180
)

response.raise_for_status()

print(
    f"Download concluído: "
    f"{len(response.content) / 1024 / 1024:.2f} MB"
)


# ============================================================
# 2. DATA DE ATUALIZAÇÃO DO CSV
# ============================================================

ultima_modificacao = response.headers.get("Last-Modified")

data_atualizacao_anm = "Não informada"
data_atualizacao_anm_iso = None

if ultima_modificacao:

    try:

        data_http = parsedate_to_datetime(
            ultima_modificacao
        )

        data_atualizacao_anm = (
            data_http.strftime("%d/%m/%Y")
        )

        data_atualizacao_anm_iso = (
            data_http.strftime("%Y-%m-%d")
        )

        print("Last-Modified:", ultima_modificacao)

    except Exception as erro:

        print(
            "Erro ao interpretar Last-Modified:",
            erro
        )

print(
    "Atualização dos dados ANM:",
    data_atualizacao_anm
)

data_geracao_webgis = (
    datetime.now().strftime("%d/%m/%Y %H:%M")
)


# ============================================================
# 3. LER CSV
# ============================================================

print("\nLendo CSV...")

cfem = pd.read_csv(
    BytesIO(response.content),
    sep=None,
    engine="python",
    encoding="latin1"
)

print(
    f"Registros encontrados: {len(cfem):,}"
)


# ============================================================
# 4. FILTRAR MINAS GERAIS
# ============================================================

cfem_mg = cfem[
    cfem["UF"]
    .astype(str)
    .str.strip()
    .str.upper()
    .eq("MG")
].copy()

print(
    f"Registros MG: {len(cfem_mg):,}"
)


# ============================================================
# 5. VALOR RECOLHIDO
# ============================================================

cfem_mg["ValorRecolhido"] = (
    cfem_mg["ValorRecolhido"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)

cfem_mg["ValorRecolhido"] = pd.to_numeric(
    cfem_mg["ValorRecolhido"],
    errors="coerce"
).fillna(0)


# ============================================================
# 6. CÓDIGO MUNICIPAL
# ============================================================

cfem_mg["CodigoMunicipio"] = (
    cfem_mg["CodigoMunicipio"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(7)
)


# ============================================================
# 7. ANO
# ============================================================

cfem_mg["Ano"] = pd.to_numeric(
    cfem_mg["Ano"],
    errors="coerce"
)

cfem_mg = cfem_mg[
    cfem_mg["Ano"].notna()
].copy()

cfem_mg["Ano"] = (
    cfem_mg["Ano"].astype(int)
)


# ============================================================
# 8. MÊS
# ============================================================
#
# O CSV da ANM possui a coluna "Mês".
# Aqui ela é convertida para números 1...12.
#
# A rotina também suporta, por segurança:
# Janeiro, Fevereiro etc.
# ============================================================

mapa_meses_python = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12
}


def converter_mes(valor):

    if pd.isna(valor):
        return None

    texto = str(valor).strip()

    try:

        numero = int(float(texto))

        if 1 <= numero <= 12:
            return numero

    except (ValueError, TypeError):
        pass

    texto_normalizado = (
        texto
        .lower()
        .replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )

    mapa_normalizado = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12
    }

    return mapa_normalizado.get(
        texto_normalizado
    )


cfem_mg["Mes"] = (
    cfem_mg["Mês"]
    .apply(converter_mes)
)

cfem_mg = cfem_mg[
    cfem_mg["Mes"].notna()
].copy()

cfem_mg["Mes"] = (
    cfem_mg["Mes"].astype(int)
)

print(
    "Meses encontrados:",
    sorted(cfem_mg["Mes"].unique().tolist())
)


# ============================================================
# 9. TEXTOS
# ============================================================

cfem_mg["Município"] = (
    cfem_mg["Município"]
    .fillna("")
    .astype(str)
    .str.strip()
)

cfem_mg["Substância"] = (
    cfem_mg["Substância"]
    .fillna("Não informada")
    .astype(str)
    .str.strip()
)

cfem_mg.loc[
    cfem_mg["Substância"].eq(""),
    "Substância"
] = "Não informada"


# ============================================================
# 10. ANOS
# ============================================================

anos = sorted(
    cfem_mg["Ano"]
    .unique()
    .tolist()
)

if not anos:
    raise ValueError("Nenhum ano encontrado.")

ano_padrao = max(anos)

print("Anos:", anos)
print("Ano padrão:", ano_padrao)


# ============================================================
# 11. AGREGAÇÃO MENSAL
#
# IMPORTANTE:
# Não agregamos mais somente por ano.
#
# O mês é preservado para permitir:
#
# Janeiro
# Janeiro + Fevereiro
# Janeiro + Março + Julho
# Todos os meses
# etc.
# ============================================================

cfem_total_mensal = (
    cfem_mg
    .groupby(
        [
            "Ano",
            "Mes",
            "CodigoMunicipio",
            "Município"
        ],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido":
                "CFEM_Total"
        }
    )
)

cfem_total_mensal["CFEM_Total"] = (
    cfem_total_mensal["CFEM_Total"]
    .astype(float)
)


# ============================================================
# 12. AGREGAÇÃO MENSAL POR SUBSTÂNCIA
# ============================================================

cfem_substancias_mensal = (
    cfem_mg
    .groupby(
        [
            "Ano",
            "Mes",
            "CodigoMunicipio",
            "Município",
            "Substância"
        ],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido":
                "CFEM_Total"
        }
    )
)

cfem_substancias_mensal["CFEM_Total"] = (
    cfem_substancias_mensal["CFEM_Total"]
    .astype(float)
)


# ============================================================
# 13. SUBSTÂNCIAS
# ============================================================

todas_substancias = sorted(
    cfem_substancias_mensal[
        "Substância"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist(),
    key=lambda x: x.upper()
)

ranking_substancias = (
    cfem_substancias_mensal
    .groupby(
        "Substância",
        as_index=False
    )["CFEM_Total"]
    .sum()
    .sort_values(
        "CFEM_Total",
        ascending=False
    )
)

principais_substancias = (
    ranking_substancias
    .head(10)["Substância"]
    .tolist()
)


# ============================================================
# 14. JSON
# ============================================================

dados_webgis = {

    "metadata": {

        "titulo":
            "Mapa de Arrecadação da CFEM — Minas Gerais",

        "descricao":
            "Compensação Financeira pela Exploração "
            "de Recursos Minerais",

        "autoria":
            "Melissa Carvalho",

        "anos":
            [int(x) for x in anos],

        "ano_padrao":
            int(ano_padrao),

        "meses":
            list(range(1, 13)),

        "substancias":
            todas_substancias,

        "principais_substancias":
            principais_substancias,

        "data_atualizacao_anm":
            data_atualizacao_anm,

        "data_atualizacao_anm_iso":
            data_atualizacao_anm_iso,

        "gerado_em":
            data_geracao_webgis
    },

    "totais":
        cfem_total_mensal.to_dict(
            orient="records"
        ),

    "substancias":
        cfem_substancias_mensal.to_dict(
            orient="records"
        )
}


with open(
    ARQUIVO_DADOS,
    "w",
    encoding="utf-8"
) as arquivo:

    json.dump(
        dados_webgis,
        arquivo,
        ensure_ascii=False,
        separators=(",", ":")
    )


print(
    f"JSON criado: {ARQUIVO_DADOS}"
)


# ============================================================
# 15. MUNICÍPIOS
# ============================================================

print("\nCarregando municípios...")

municipios = gpd.read_file(
    ARQUIVO_MUNICIPIOS
)

municipios = municipios.to_crs(
    epsg=4326
)

municipios["CD_MUN"] = (
    municipios["CD_MUN"]
    .astype(str)
    .str.replace(
        r"\.0$",
        "",
        regex=True
    )
    .str.zfill(7)
)

municipios = municipios[
    [
        "CD_MUN",
        "NM_MUN",
        "geometry"
    ]
].copy()


# ============================================================
# 16. DADOS INICIAIS
#
# Ano padrão + todos os meses.
# ============================================================

dados_iniciais = (
    cfem_total_mensal[
        cfem_total_mensal["Ano"]
        .eq(ano_padrao)
    ]
    .groupby(
        [
            "CodigoMunicipio",
            "Município"
        ],
        as_index=False
    )["CFEM_Total"]
    .sum()
)

geo_inicial = municipios.merge(
    dados_iniciais[
        [
            "CodigoMunicipio",
            "CFEM_Total"
        ]
    ],
    left_on="CD_MUN",
    right_on="CodigoMunicipio",
    how="left"
)

geo_inicial["CFEM_Total"] = (
    geo_inicial["CFEM_Total"]
    .fillna(0)
    .astype(float)
)

geo_inicial["Ano"] = (
    int(ano_padrao)
)


# ============================================================
# 17. CORES
# ============================================================

def cor_cfem(valor):

    valor = float(valor or 0)

    if valor <= 0:
        return "#eeeeee"

    elif valor <= 10_000:
        return "#ffffcc"

    elif valor <= 100_000:
        return "#ffeda0"

    elif valor <= 1_000_000:
        return "#fed976"

    elif valor <= 10_000_000:
        return "#feb24c"

    elif valor <= 100_000_000:
        return "#f03b20"

    return "#bd0026"


# ============================================================
# 18. MAPA
# ============================================================

mapa_cfem = folium.Map(
    location=[
        -18.5,
        -44.5
    ],
    zoom_start=6,
    tiles=None,
    control_scale=True,
    prefer_canvas=True
)


# ============================================================
# 19. MAPAS BASE
# ============================================================

folium.TileLayer(

    tiles=(
        "https://{s}.tile-cyclosm.openstreetmap.fr/"
        "cyclosm/{z}/{x}/{y}.png"
    ),

    name="CyclOSM",

    attr=(
        "CyclOSM | © OpenStreetMap contributors"
    ),

    overlay=False,
    control=True,
    show=True

).add_to(mapa_cfem)


folium.TileLayer(

    tiles=(
        "https://server.arcgisonline.com/"
        "ArcGIS/rest/services/"
        "World_Topo_Map/MapServer/"
        "tile/{z}/{y}/{x}"
    ),

    name="Esri World Topo",

    attr="Tiles © Esri",

    overlay=False,
    control=True,
    show=False

).add_to(mapa_cfem)


# ============================================================
# 20. MUNICÍPIOS
# ============================================================

camada_municipios = folium.GeoJson(

    geo_inicial[
        [
            "CD_MUN",
            "NM_MUN",
            "Ano",
            "CFEM_Total",
            "geometry"
        ]
    ],

    name="CFEM",

    control=False,

    style_function=lambda feature: {

        "fillColor":
            cor_cfem(
                feature[
                    "properties"
                ]["CFEM_Total"]
            ),

        "color":
            "#555555",

        "weight":
            0.6,

        "fillOpacity":
            0.80
    }

).add_to(mapa_cfem)


nome_camada_js = (
    camada_municipios.get_name()
)

nome_mapa_js = (
    mapa_cfem.get_name()
)


# ============================================================
# 21. LIMITES MG
# ============================================================

minx, miny, maxx, maxy = (
    municipios.total_bounds
)

limites_mg = [
    [
        float(miny),
        float(minx)
    ],
    [
        float(maxy),
        float(maxx)
    ]
]

limites_mg_json = json.dumps(
    limites_mg
)


# ============================================================
# 22. TÍTULO
# ============================================================

titulo_html = """
<div id="titulo-webgis">

    <div class="titulo-desktop">
        Mapa de Arrecadação da CFEM — Minas Gerais
    </div>

    <div class="titulo-mobile">
        CFEM — Minas Gerais
    </div>

    <div class="titulo-subtitulo">
        Compensação Financeira pela Exploração
        de Recursos Minerais
    </div>

</div>
"""

mapa_cfem.get_root().html.add_child(
    folium.Element(
        titulo_html
    )
)


# ============================================================
# 23. VARIÁVEIS JAVASCRIPT
# ============================================================

anos_json = json.dumps(
    [int(x) for x in anos],
    ensure_ascii=False
)

substancias_json = json.dumps(
    todas_substancias,
    ensure_ascii=False
)

principais_json = json.dumps(
    principais_substancias,
    ensure_ascii=False
)

municipios_json = json.dumps(
    municipios[
        [
            "CD_MUN",
            "NM_MUN"
        ]
    ]
    .sort_values("NM_MUN")
    .to_dict(orient="records"),
    ensure_ascii=False
)

data_atualizacao_anm_json = json.dumps(
    data_atualizacao_anm,
    ensure_ascii=False
)


# ============================================================
# 24. INTERFACE
#
# NÃO USAR F-STRING.
# ============================================================

interface_html = r"""
<style>

/* ==========================================================
   GERAL
   ========================================================== */

html,
body {
    margin:0;
    padding:0;
}

#titulo-webgis,
#painel-cfem,
#legenda-cfem,
#modal-sobre-cfem,
#botao-mobile-consulta,
#botao-mobile-legenda {
    font-family:Arial, Helvetica, sans-serif;
}


/* ==========================================================
   TÍTULO
   ========================================================== */

#titulo-webgis {

    position:fixed;

    top:10px;
    left:70px;

    z-index:9997;

    background:rgba(255,255,255,.96);

    border:1px solid #888;
    border-radius:7px;

    padding:9px 16px;

    box-shadow:
        0 2px 7px rgba(0,0,0,.25);

    pointer-events:none;
}

.titulo-desktop {

    display:block;

    font-size:19px;
    font-weight:bold;

    white-space:nowrap;
}

.titulo-mobile {
    display:none;
}

.titulo-subtitulo {

    font-size:12px;

    margin-top:4px;
}


/* ==========================================================
   PAINEL
   ========================================================== */

#painel-cfem {

    position:fixed;

    top:90px;
    right:20px;

    width:365px;

    max-height:calc(100vh - 115px);

    overflow-y:auto;
    overflow-x:hidden;

    z-index:9999;

    background:
        rgba(255,255,255,.97);

    border:1px solid #999;

    border-radius:8px;

    padding:14px;

    box-sizing:border-box;

    box-shadow:
        0 2px 8px rgba(0,0,0,.28);
}


.cabecalho-painel {

    display:flex;

    justify-content:
        space-between;

    align-items:center;
}

.cabecalho-painel h3 {

    margin:0;

    font-size:16px;
}

#fechar-painel-mobile {

    display:none;

    width:36px;
    height:36px;

    border:0;

    background:#eee;

    border-radius:50%;

    font-size:22px;

    cursor:pointer;
}


/* ==========================================================
   FORMULÁRIO
   ========================================================== */

.rotulo-cfem {

    display:block;

    font-size:12px;
    font-weight:bold;

    margin:10px 0 5px;

    color:#444;
}

#filtro-ano,
#busca-substancia,
#busca-municipio {

    width:100%;

    min-height:40px;

    padding:8px;

    box-sizing:border-box;

    border:1px solid #aaa;

    border-radius:5px;

    background:#fff;

    font-size:13px;
}


#lista-substancias,
#lista-municipios {

    display:none;

    max-height:220px;

    overflow-y:auto;

    margin-top:3px;

    border:1px solid #bbb;

    border-radius:5px;

    background:#fff;

    box-shadow:
        0 2px 5px rgba(0,0,0,.15);
}


.item-substancia,
.item-municipio {

    padding:10px;

    font-size:12px;

    cursor:pointer;

    border-bottom:
        1px solid #eee;
}

.item-substancia:hover,
.item-municipio:hover {

    background:#eee;
}

.item-principal {
    font-weight:bold;
}


#botao-voltar-mg {

    width:100%;

    min-height:40px;

    margin-top:8px;

    border:1px solid #999;

    border-radius:5px;

    background:#f5f5f5;

    cursor:pointer;
}


/* ==========================================================
   FILTRO DE MESES
   ========================================================== */

#bloco-periodo {

    margin-top:10px;
}

#controle-periodo {

    display:flex;

    gap:6px;
}

.botao-periodo {

    flex:1;

    min-height:38px;

    border:1px solid #999;

    border-radius:5px;

    background:#f5f5f5;

    cursor:pointer;

    font-size:11px;
}

.botao-periodo.ativo {

    background:#333;

    color:#fff;

    border-color:#333;
}


#painel-meses {

    display:none;

    margin-top:7px;

    padding:9px;

    border:1px solid #ccc;

    border-radius:6px;

    background:#fafafa;
}

#painel-meses.aberto {
    display:block;
}


.grade-meses {

    display:grid;

    grid-template-columns:
        1fr 1fr 1fr;

    gap:5px;
}


.item-mes {

    display:flex;

    align-items:center;

    gap:5px;

    min-height:31px;

    padding:4px 5px;

    box-sizing:border-box;

    background:#fff;

    border:1px solid #ddd;

    border-radius:4px;

    cursor:pointer;

    font-size:10px;
}

.item-mes input {

    margin:0;
}


.acoes-meses {

    display:flex;

    gap:6px;

    margin-top:8px;
}


.botao-meses {

    flex:1;

    min-height:32px;

    border:1px solid #aaa;

    border-radius:4px;

    background:#fff;

    cursor:pointer;

    font-size:10px;
}


#resumo-meses {

    margin-top:7px;

    padding:6px 7px;

    background:#fff;

    border:1px solid #ddd;

    border-radius:4px;

    font-size:10px;

    color:#555;

    line-height:1.4;
}


/* ==========================================================
   SEÇÕES
   ========================================================== */

.secao {

    margin-top:13px;

    padding-top:10px;

    border-top:
        1px solid #ddd;
}

.secao-titulo {

    margin-bottom:7px;

    font-size:12px;

    font-weight:bold;

    color:#444;
}


/* ==========================================================
   INDICADORES
   ========================================================== */

.grade-indicadores {

    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:7px;
}

.cartao-indicador {

    border:1px solid #ddd;

    border-radius:6px;

    background:#fafafa;

    padding:8px;
}

.cartao-indicador.total {

    grid-column:1/-1;
}

.indicador-rotulo {

    font-size:10px;

    color:#666;
}

.indicador-valor {

    margin-top:4px;

    font-size:14px;

    font-weight:bold;
}

.indicador-detalhe {

    margin-top:3px;

    font-size:10px;

    color:#666;
}


/* ==========================================================
   RANKING
   ========================================================== */

#lista-ranking {

    border:1px solid #ddd;

    border-radius:6px;

    overflow:hidden;
}

.item-ranking {

    display:grid;

    grid-template-columns:
        28px 1fr auto;

    gap:6px;

    align-items:center;

    padding:7px 8px;

    border-bottom:
        1px solid #eee;

    cursor:pointer;
}

.item-ranking:hover {

    background:#f1f1f1;
}

.item-ranking.selecionado {

    background:#e8e8e8;

    box-shadow:
        inset 3px 0 0 #222;
}

.ranking-posicao {

    font-size:11px;

    font-weight:bold;

    color:#777;
}

.ranking-municipio {

    min-width:0;

    overflow:hidden;

    text-overflow:ellipsis;

    white-space:nowrap;

    font-size:11px;

    font-weight:600;
}

.ranking-valor {

    font-size:10px;

    font-weight:bold;

    white-space:nowrap;
}


/* ==========================================================
   MUNICÍPIO
   ========================================================== */

#painel-municipio {

    display:none;

    margin-top:13px;

    padding-top:10px;

    border-top:
        2px solid #777;
}

#municipio-nome {

    margin-bottom:8px;

    font-size:17px;

    font-weight:bold;
}

.municipio-grade {

    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:7px;
}

.municipio-cartao {

    border:1px solid #ddd;

    border-radius:6px;

    background:#fafafa;

    padding:8px;
}

.municipio-cartao.principal {

    grid-column:1/-1;
}

.municipio-rotulo {

    font-size:9px;

    color:#666;
}

.municipio-valor {

    margin-top:4px;

    font-size:13px;

    font-weight:bold;
}


/* ==========================================================
   SÉRIE
   ========================================================== */

#serie-barras {

    border:1px solid #ddd;

    border-radius:6px;

    padding:8px;
}

.serie-linha {

    display:grid;

    grid-template-columns:
        42px 1fr 82px;

    gap:6px;

    align-items:center;

    min-height:27px;
}

.serie-ano {

    font-size:10px;

    font-weight:bold;
}

.serie-barra-fundo {

    height:11px;

    background:#eee;

    border-radius:3px;

    overflow:hidden;
}

.serie-barra {

    height:100%;

    background:#777;
}

.serie-linha.ativa
.serie-barra {

    background:#222;
}

.serie-valor {

    font-size:9px;

    text-align:right;
}

.serie-nota {

    margin-top:7px;

    font-size:9px;

    line-height:1.4;

    color:#777;
}


/* ==========================================================
   DADOS
   ========================================================== */

.botoes-etapa9 {

    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:7px;
}

.botao-etapa9 {

    min-height:40px;

    border:1px solid #888;

    border-radius:5px;

    background:#f5f5f5;

    cursor:pointer;

    font-size:11px;

    font-weight:600;
}


#info-atualizacao-painel {

    margin-top:8px;

    padding:8px;

    background:#fafafa;

    border:1px solid #ddd;

    border-radius:5px;

    font-size:10px;

    line-height:1.4;
}


#status-consulta {

    margin-top:12px;

    padding-top:9px;

    border-top:
        1px solid #ddd;

    font-size:11px;

    color:#555;

    line-height:1.5;
}


/* ==========================================================
   LEGENDA
   ========================================================== */

#legenda-cfem {

    position:fixed;

    bottom:30px;
    left:30px;

    width:285px;

    z-index:9996;

    background:
        rgba(255,255,255,.96);

    border:1px solid #888;

    border-radius:7px;

    padding:12px;

    box-sizing:border-box;

    box-shadow:
        0 2px 7px rgba(0,0,0,.25);

    font-size:12px;
}

.legenda-titulo {

    margin-bottom:8px;

    font-size:14px;

    font-weight:bold;
}

.legenda-item {

    margin-bottom:4px;
}

.caixa-cor {

    display:inline-block;

    width:16px;
    height:16px;

    margin-right:6px;

    vertical-align:middle;

    border:1px solid #999;
}

.creditos-cfem {

    margin-top:9px;

    padding-top:7px;

    border-top:
        1px solid #bbb;

    font-size:10px;

    line-height:1.45;
}


/* ==========================================================
   MOBILE BUTTONS
   ========================================================== */

#botao-mobile-consulta,
#botao-mobile-legenda {

    display:none;
}


/* ==========================================================
   MODAL
   ========================================================== */

#modal-sobre-cfem {

    display:none;

    position:fixed;

    inset:0;

    z-index:20000;

    background:
        rgba(0,0,0,.48);

    padding:25px;

    box-sizing:border-box;

    align-items:center;

    justify-content:center;
}

#modal-sobre-cfem.aberto {

    display:flex;
}

#conteudo-modal {

    position:relative;

    width:min(
        680px,
        calc(100vw - 40px)
    );

    max-height:
        calc(100vh - 50px);

    overflow-y:auto;

    background:#fff;

    border-radius:9px;

    padding:20px;

    box-sizing:border-box;
}

#fechar-modal {

    position:absolute;

    top:10px;
    right:12px;

    width:34px;
    height:34px;

    border:0;

    border-radius:50%;

    font-size:20px;

    cursor:pointer;
}

.tabela-metadados {

    width:100%;

    border-collapse:collapse;

    font-size:11px;
}

.tabela-metadados td {

    padding:7px 5px;

    border-bottom:
        1px solid #eee;
}

.tabela-metadados
td:first-child {

    width:180px;

    font-weight:bold;
}


/* ==========================================================
   MOBILE
   ========================================================== */

@media(max-width:768px) {


    #titulo-webgis {

        top:10px;

        left:72px;
        right:70px;

        width:auto;

        padding:8px 10px;

        text-align:center;
    }


    .titulo-desktop {
        display:none;
    }

    .titulo-mobile {

        display:block;

        font-size:14px;

        font-weight:bold;

        white-space:nowrap;
    }

    .titulo-subtitulo {
        display:none;
    }


    /* PAINEL INFERIOR */

    #painel-cfem {

        position:fixed;

        top:auto;
        left:0;
        right:0;
        bottom:0;

        width:100%;

        height:72vh;

        max-height:72vh;

        overflow-y:auto;

        border:0;

        border-top:
            1px solid #888;

        border-radius:
            18px 18px 0 0;

        padding:
            12px
            14px
            calc(
                22px +
                env(
                    safe-area-inset-bottom
                )
            );

        z-index:15000;

        box-shadow:
            0 -4px 18px
            rgba(0,0,0,.30);

        transform:
            translateY(105%);

        transition:
            transform .25s ease;
    }


    #painel-cfem.aberto {

        transform:
            translateY(0);
    }


    #fechar-painel-mobile {

        display:block;
    }


    .cabecalho-painel {

        position:sticky;

        top:-12px;

        z-index:20;

        background:#fff;

        margin:
            -12px -14px 5px;

        padding:10px 14px;

        border-bottom:
            1px solid #eee;
    }


    /* TOUCH */

    #filtro-ano,
    #busca-substancia,
    #busca-municipio,
    #botao-voltar-mg,
    .botao-etapa9,
    .botao-periodo {

        min-height:46px;

        font-size:16px;
    }


    .rotulo-cfem {

        font-size:13px;

        margin-top:13px;
    }


    .item-substancia,
    .item-municipio {

        min-height:44px;

        display:flex;

        align-items:center;

        box-sizing:border-box;

        font-size:14px;
    }


    /* MESES */

    .grade-meses {

        grid-template-columns:
            1fr 1fr;
    }


    .item-mes {

        min-height:44px;

        font-size:13px;
    }


    .item-mes input {

        width:18px;

        height:18px;
    }


    .botao-meses {

        min-height:42px;

        font-size:12px;
    }


    #resumo-meses {

        font-size:12px;
    }


    /* BOTÃO CONSULTA */

    #botao-mobile-consulta {

        display:block;

        position:fixed;

        left:50%;

        bottom:
            calc(
                22px +
                env(
                    safe-area-inset-bottom
                )
            );

        transform:
            translateX(-50%);

        z-index:12000;

        min-width:190px;

        min-height:48px;

        padding:10px 18px;

        border:
            1px solid #555;

        border-radius:24px;

        background:
            rgba(255,255,255,.97);

        box-shadow:
            0 3px 12px
            rgba(0,0,0,.30);

        font-size:14px;

        font-weight:bold;

        cursor:pointer;
    }


    body.painel-mobile-aberto
    #botao-mobile-consulta {

        display:none;
    }


    /* LEGENDA */

    #botao-mobile-legenda {

        display:block;

        position:fixed;

        left:12px;

        bottom:
            calc(
                82px +
                env(
                    safe-area-inset-bottom
                )
            );

        z-index:11999;

        min-height:42px;

        padding:8px 13px;

        border:
            1px solid #666;

        border-radius:21px;

        background:
            rgba(255,255,255,.96);

        box-shadow:
            0 2px 8px
            rgba(0,0,0,.25);

        font-size:12px;

        font-weight:bold;
    }


    #legenda-cfem {

        display:none;

        position:fixed;

        left:12px;

        bottom:
            calc(
                132px +
                env(
                    safe-area-inset-bottom
                )
            );

        width:245px;

        max-height:55vh;

        overflow-y:auto;

        z-index:11998;

        padding:10px;

        font-size:11px;
    }


    #legenda-cfem.aberta {

        display:block;
    }


    #legenda-cfem
    .creditos-cfem {

        display:none;
    }


    body.painel-mobile-aberto
    #legenda-cfem,

    body.painel-mobile-aberto
    #botao-mobile-legenda {

        display:none !important;
    }


    /* OUTROS */

    .leaflet-control-zoom a {

        width:42px !important;

        height:42px !important;

        line-height:
            42px !important;

        font-size:
            22px !important;
    }


    .leaflet-tooltip {

        max-width:220px;

        white-space:normal;

        font-size:11px;
    }


    .botoes-etapa9 {

        grid-template-columns:1fr;
    }


    #modal-sobre-cfem {

        padding:10px;
    }


    #conteudo-modal {

        width:100%;

        max-height:88vh;

        padding:18px;
    }

}


/* ==========================================================
   CELULAR MUITO ESTREITO
   ========================================================== */

@media(max-width:400px) {

    #titulo-webgis {

        left:66px;
        right:62px;

        padding:7px 5px;
    }

    .titulo-mobile {

        font-size:12px;
    }

    #painel-cfem {

        height:75vh;

        max-height:75vh;
    }

    #legenda-cfem {

        width:220px;
    }

    .grade-indicadores {

        grid-template-columns:1fr;
    }

    .cartao-indicador.total {

        grid-column:auto;
    }

}

</style>


<!-- ========================================================
     MOBILE
     ======================================================== -->

<button
    id="botao-mobile-legenda"
    type="button">
    Legenda
</button>

<button
    id="botao-mobile-consulta"
    type="button">
    ☰ Consulta CFEM
</button>


<!-- ========================================================
     PAINEL
     ======================================================== -->

<div id="painel-cfem">

<div class="cabecalho-painel">

<h3>
Consulta CFEM
</h3>

<button
    id="fechar-painel-mobile"
    type="button">
×
</button>

</div>


<!-- ANO -->

<label class="rotulo-cfem">
Ano
</label>

<select id="filtro-ano">
</select>


<!-- PERÍODO -->

<div id="bloco-periodo">

<label class="rotulo-cfem">
Período
</label>

<div id="controle-periodo">

<button
    id="botao-ano-completo"
    class="botao-periodo ativo"
    type="button">
Ano completo
</button>

<button
    id="botao-selecionar-meses"
    class="botao-periodo"
    type="button">
Selecionar meses
</button>

</div>


<div id="painel-meses">

<div class="grade-meses">

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="1">
Janeiro
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="2">
Fevereiro
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="3">
Março
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="4">
Abril
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="5">
Maio
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="6">
Junho
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="7">
Julho
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="8">
Agosto
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="9">
Setembro
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="10">
Outubro
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="11">
Novembro
</label>

<label class="item-mes">
<input
    type="checkbox"
    class="checkbox-mes"
    value="12">
Dezembro
</label>

</div>


<div class="acoes-meses">

<button
    id="selecionar-todos-meses"
    class="botao-meses"
    type="button">
Todos
</button>

<button
    id="limpar-meses"
    class="botao-meses"
    type="button">
Limpar
</button>

</div>


<div id="resumo-meses">
Ano completo
</div>

</div>

</div>


<!-- SUBSTÂNCIA -->

<label class="rotulo-cfem">
Substância mineral
</label>

<input
    id="busca-substancia"
    value="Todas as substâncias"
    autocomplete="off"
>

<div id="lista-substancias">
</div>


<!-- MUNICÍPIO -->

<label class="rotulo-cfem">
Município
</label>

<input
    id="busca-municipio"
    placeholder="Digite o nome do município..."
    autocomplete="off"
>

<div id="lista-municipios">
</div>


<button
    id="botao-voltar-mg"
    type="button">
Visualizar todo o estado
</button>


<!-- ========================================================
     INDICADORES
     ======================================================== -->

<div class="secao">

<div class="secao-titulo">
Indicadores da consulta
</div>

<div class="grade-indicadores">


<div class="cartao-indicador total">

<div class="indicador-rotulo">
CFEM total
</div>

<div
    id="indicador-total"
    class="indicador-valor">
R$ 0,00
</div>

</div>


<div class="cartao-indicador">

<div class="indicador-rotulo">
Municípios com arrecadação
</div>

<div
    id="indicador-municipios"
    class="indicador-valor">
0
</div>

</div>


<div class="cartao-indicador">

<div class="indicador-rotulo">
Maior arrecadação municipal
</div>

<div
    id="indicador-maior-valor"
    class="indicador-valor">
R$ 0,00
</div>

<div
    id="indicador-maior-municipio"
    class="indicador-detalhe">
—
</div>

</div>

</div>

</div>


<!-- ========================================================
     RANKING
     ======================================================== -->

<div class="secao">

<div class="secao-titulo">
Ranking municipal — TOP 10
</div>

<div id="lista-ranking">
</div>

</div>


<!-- ========================================================
     MUNICÍPIO SELECIONADO
     ======================================================== -->

<div id="painel-municipio">

<div
style="
font-size:9px;
color:#777;
text-transform:uppercase;
">
Município selecionado
</div>

<div id="municipio-nome">
—
</div>


<div class="municipio-grade">


<div class="municipio-cartao principal">

<div
    id="municipio-valor-rotulo"
    class="municipio-rotulo">
CFEM
</div>

<div
    id="municipio-valor"
    class="municipio-valor">
R$ 0,00
</div>

</div>


<div class="municipio-cartao">

<div class="municipio-rotulo">
Participação em MG
</div>

<div
    id="municipio-participacao"
    class="municipio-valor">
0,00%
</div>

</div>


<div class="municipio-cartao">

<div class="municipio-rotulo">
Posição estadual
</div>

<div
    id="municipio-posicao"
    class="municipio-valor">
—
</div>

</div>

</div>


<!-- SÉRIE -->

<div class="secao">

<div class="secao-titulo">
Série histórica da CFEM
</div>

<div
    id="serie-substancia"
    style="
    font-size:9px;
    color:#777;
    margin-bottom:4px;
    ">
</div>

<div
    id="serie-periodo"
    style="
    font-size:9px;
    color:#777;
    margin-bottom:7px;
    ">
</div>

<div id="serie-barras">
</div>

<div
    id="serie-nota"
    class="serie-nota">
</div>

</div>

</div>


<!-- ========================================================
     DADOS
     ======================================================== -->

<div class="secao">

<div class="secao-titulo">
Dados e informações
</div>

<div class="botoes-etapa9">

<button
    id="botao-download-csv"
    class="botao-etapa9"
    type="button">
Baixar consulta CSV
</button>

<button
    id="botao-sobre"
    class="botao-etapa9"
    type="button">
Sobre o WebGIS
</button>

</div>


<div id="info-atualizacao-painel">

<b>Atualização dos dados ANM:</b>
__DATA_ATUALIZACAO_ANM__

</div>

</div>


<div id="status-consulta">

<b>Exibindo:</b>

<span id="status-ano">
__ANO_PADRAO__
</span>

·

<span id="status-periodo">
Ano completo
</span>

·

<span id="status-substancia">
Todas as substâncias
</span>

</div>

</div>


<!-- ========================================================
     LEGENDA
     ======================================================== -->

<div id="legenda-cfem">

<div class="legenda-titulo">
CFEM arrecadada
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#eeeeee">
</span>
Sem arrecadação
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#ffffcc">
</span>
Até R$ 10 mil
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#ffeda0">
</span>
R$ 10 mil – R$ 100 mil
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#fed976">
</span>
R$ 100 mil – R$ 1 milhão
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#feb24c">
</span>
R$ 1 mi – R$ 10 milhões
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#f03b20">
</span>
R$ 10 mi – R$ 100 milhões
</div>

<div class="legenda-item">
<span
class="caixa-cor"
style="background:#bd0026">
</span>
Acima de R$ 100 milhões
</div>


<div class="creditos-cfem">

<b>Autoria:</b>
Melissa Carvalho

<br>

<b>Atualização dos dados ANM:</b>
__DATA_ATUALIZACAO_ANM__

<br>

<b>Fontes:</b>
Malha Municipal de Minas Gerais — IBGE;

<br>

Arrecadação da CFEM (2022–2026) — ANM.

</div>

</div>


<!-- ========================================================
     SOBRE
     ======================================================== -->

<div id="modal-sobre-cfem">

<div id="conteudo-modal">

<button
    id="fechar-modal"
    type="button">
×
</button>

<h2>
Sobre o WebGIS CFEM
</h2>

<p>
Este WebGIS apresenta a distribuição espacial
da arrecadação da Compensação Financeira pela
Exploração de Recursos Minerais (CFEM) nos
municípios de Minas Gerais.
</p>

<p>
A consulta pode ser realizada por ano, por um
ou vários meses, por substância mineral e por
município.
</p>

<p>
Ao selecionar vários meses, os valores apresentados
no mapa, indicadores, ranking, município e arquivo
CSV correspondem à soma dos meses selecionados.
</p>

<h4>Série histórica</h4>

<p>
Quando meses específicos são selecionados, a série
histórica utiliza os mesmos meses em todos os anos.
Isso permite comparar períodos equivalentes.
</p>

<h4>Fontes</h4>

<p>
Dados de arrecadação: Agência Nacional de Mineração — ANM.
</p>

<p>
Malha municipal: Instituto Brasileiro de Geografia
e Estatística — IBGE.
</p>

<h4>Metadados</h4>

<table class="tabela-metadados">

<tr>
<td>Autoria</td>
<td>Melissa Carvalho</td>
</tr>

<tr>
<td>Atualização dos dados ANM</td>
<td>__DATA_ATUALIZACAO_ANM__</td>
</tr>

<tr>
<td>WebGIS gerado em</td>
<td>__DATA_GERACAO_WEBGIS__</td>
</tr>

<tr>
<td>Dados CFEM</td>
<td>Agência Nacional de Mineração — ANM</td>
</tr>

<tr>
<td>Malha municipal</td>
<td>IBGE</td>
</tr>

</table>

</div>

</div>


<script>

document.addEventListener(
"DOMContentLoaded",
async function() {


/* ==========================================================
   CONSTANTES
   ========================================================== */

const mapa = __MAPA_JS__;

const camadaMunicipios =
    __CAMADA_MUNICIPIOS__;

const anos =
    __ANOS_JSON__;

const substancias =
    __SUBSTANCIAS_JSON__;

const principais =
    __PRINCIPAIS_JSON__;

const municipiosBusca =
    __MUNICIPIOS_JSON__;

const limitesMG =
    __LIMITES_MG__;

const anoPadrao =
    __ANO_PADRAO__;

const dataAtualizacaoANM =
    __DATA_ATUALIZACAO_ANM_JSON__;


const nomesMeses = {

    1:"Janeiro",
    2:"Fevereiro",
    3:"Março",
    4:"Abril",
    5:"Maio",
    6:"Junho",
    7:"Julho",
    8:"Agosto",
    9:"Setembro",
    10:"Outubro",
    11:"Novembro",
    12:"Dezembro"

};


const abreviacoesMeses = {

    1:"Jan",
    2:"Fev",
    3:"Mar",
    4:"Abr",
    5:"Mai",
    6:"Jun",
    7:"Jul",
    8:"Ago",
    9:"Set",
    10:"Out",
    11:"Nov",
    12:"Dez"

};


/* ==========================================================
   ESTADO
   ========================================================== */

let dadosCFEM = null;

let substanciaSelecionada =
    "TODAS";

/*
    null = ano completo.

    Array = meses selecionados.
*/
let mesesSelecionados =
    null;


let codigoMunicipioSelecionado =
    null;

let nomeMunicipioSelecionado =
    null;

let camadaMunicipioSelecionado =
    null;

let valoresConsultaAtual =
    new Map();

let rankingConsultaAtual =
    [];


/* ==========================================================
   ELEMENTOS
   ========================================================== */

const painel =
document.getElementById(
    "painel-cfem"
);

const botaoConsulta =
document.getElementById(
    "botao-mobile-consulta"
);

const fecharPainel =
document.getElementById(
    "fechar-painel-mobile"
);

const botaoLegenda =
document.getElementById(
    "botao-mobile-legenda"
);

const legenda =
document.getElementById(
    "legenda-cfem"
);


const filtroAno =
document.getElementById(
    "filtro-ano"
);


const botaoAnoCompleto =
document.getElementById(
    "botao-ano-completo"
);

const botaoSelecionarMeses =
document.getElementById(
    "botao-selecionar-meses"
);

const painelMeses =
document.getElementById(
    "painel-meses"
);

const checkboxesMeses =
Array.from(
    document.querySelectorAll(
        ".checkbox-mes"
    )
);

const selecionarTodosMeses =
document.getElementById(
    "selecionar-todos-meses"
);

const limparMeses =
document.getElementById(
    "limpar-meses"
);

const resumoMeses =
document.getElementById(
    "resumo-meses"
);


const buscaSubstancia =
document.getElementById(
    "busca-substancia"
);

const listaSubstancias =
document.getElementById(
    "lista-substancias"
);

const buscaMunicipio =
document.getElementById(
    "busca-municipio"
);

const listaMunicipios =
document.getElementById(
    "lista-municipios"
);

const botaoVoltarMG =
document.getElementById(
    "botao-voltar-mg"
);


const indicadorTotal =
document.getElementById(
    "indicador-total"
);

const indicadorMunicipios =
document.getElementById(
    "indicador-municipios"
);

const indicadorMaiorValor =
document.getElementById(
    "indicador-maior-valor"
);

const indicadorMaiorMunicipio =
document.getElementById(
    "indicador-maior-municipio"
);


const listaRanking =
document.getElementById(
    "lista-ranking"
);


const painelMunicipio =
document.getElementById(
    "painel-municipio"
);

const municipioNome =
document.getElementById(
    "municipio-nome"
);

const municipioValor =
document.getElementById(
    "municipio-valor"
);

const municipioValorRotulo =
document.getElementById(
    "municipio-valor-rotulo"
);

const municipioParticipacao =
document.getElementById(
    "municipio-participacao"
);

const municipioPosicao =
document.getElementById(
    "municipio-posicao"
);


const serieSubstancia =
document.getElementById(
    "serie-substancia"
);

const seriePeriodo =
document.getElementById(
    "serie-periodo"
);

const serieBarras =
document.getElementById(
    "serie-barras"
);

const serieNota =
document.getElementById(
    "serie-nota"
);


const statusAno =
document.getElementById(
    "status-ano"
);

const statusPeriodo =
document.getElementById(
    "status-periodo"
);

const statusSubstancia =
document.getElementById(
    "status-substancia"
);


const modal =
document.getElementById(
    "modal-sobre-cfem"
);


/* ==========================================================
   MOBILE
   ========================================================== */

function ehMobile() {

    return window.matchMedia(
        "(max-width:768px)"
    ).matches;

}


function abrirPainelMobile() {

    if (!ehMobile())
        return;

    legenda.classList.remove(
        "aberta"
    );

    painel.classList.add(
        "aberto"
    );

    document.body.classList.add(
        "painel-mobile-aberto"
    );

}


function fecharPainelMobile() {

    painel.classList.remove(
        "aberto"
    );

    document.body.classList.remove(
        "painel-mobile-aberto"
    );

}


botaoConsulta.onclick =
function() {

    abrirPainelMobile();

};


fecharPainel.onclick =
function() {

    fecharPainelMobile();

};


botaoLegenda.onclick =
function() {

    legenda.classList.toggle(
        "aberta"
    );

    botaoLegenda.textContent =
        legenda.classList.contains(
            "aberta"
        )
        ?
        "Fechar legenda"
        :
        "Legenda";

};


/* ==========================================================
   MAPAS AUXILIARES
   ========================================================== */

const municipioPorCodigo =
    new Map();

const layerPorCodigo =
    new Map();


municipiosBusca.forEach(
function(m) {

    municipioPorCodigo.set(
        String(m.CD_MUN),
        m
    );

});


camadaMunicipios.eachLayer(
function(layer) {

    if (!layer.feature)
        return;

    const codigo =
        String(
            layer.feature
            .properties
            .CD_MUN
        );

    layerPorCodigo.set(
        codigo,
        layer
    );

});


/* ==========================================================
   FUNÇÕES GERAIS
   ========================================================== */

function normalizar(texto) {

    return String(texto || "")
    .normalize("NFD")
    .replace(
        /[\u0300-\u036f]/g,
        ""
    )
    .toLowerCase()
    .trim();

}


function moeda(valor) {

    return Number(valor || 0)
    .toLocaleString(
        "pt-BR",
        {
            style:"currency",
            currency:"BRL"
        }
    );

}


function moedaCompacta(valor) {

    valor =
        Number(valor || 0);

    if (valor >= 1000000000) {

        return (
            "R$ " +
            (
                valor /
                1000000000
            )
            .toLocaleString(
                "pt-BR",
                {
                    maximumFractionDigits:2
                }
            )
            +
            " bi"
        );

    }

    if (valor >= 1000000) {

        return (
            "R$ " +
            (
                valor /
                1000000
            )
            .toLocaleString(
                "pt-BR",
                {
                    maximumFractionDigits:2
                }
            )
            +
            " mi"
        );

    }

    if (valor >= 1000) {

        return (
            "R$ " +
            (
                valor /
                1000
            )
            .toLocaleString(
                "pt-BR",
                {
                    maximumFractionDigits:2
                }
            )
            +
            " mil"
        );

    }

    return moeda(valor);

}


function corCFEM(valor) {

    valor =
        Number(valor || 0);

    if (valor <= 0)
        return "#eeeeee";

    if (valor <= 10000)
        return "#ffffcc";

    if (valor <= 100000)
        return "#ffeda0";

    if (valor <= 1000000)
        return "#fed976";

    if (valor <= 10000000)
        return "#feb24c";

    if (valor <= 100000000)
        return "#f03b20";

    return "#bd0026";

}


function aplicarEstiloNormal(
layer
) {

    const valor =
        Number(
            layer.feature
            .properties
            .CFEM_Total || 0
        );

    layer.setStyle({

        fillColor:
            corCFEM(valor),

        color:
            "#555555",

        weight:
            0.6,

        fillOpacity:
            0.80

    });

}


function aplicarDestaque() {

    if (
        !camadaMunicipioSelecionado
    )
        return;

    camadaMunicipioSelecionado
    .setStyle({

        color:"#000000",

        weight:4,

        fillOpacity:0.95

    });

    if (
        camadaMunicipioSelecionado
        .bringToFront
    ) {

        camadaMunicipioSelecionado
        .bringToFront();

    }

}


/* ==========================================================
   FUNÇÕES DE PERÍODO
   ========================================================== */

function obterMesesAtivos() {

    /*
       Ano completo.
    */

    if (
        mesesSelecionados === null
    ) {

        return [
            1,2,3,4,5,6,
            7,8,9,10,11,12
        ];

    }

    return mesesSelecionados
        .slice()
        .sort(
            (a,b) => a-b
        );

}


function textoPeriodo(
compacto=false
) {

    if (
        mesesSelecionados === null
    ) {

        return "Ano completo";

    }

    if (
        mesesSelecionados.length === 0
    ) {

        return "Nenhum mês";

    }


    const meses =
        mesesSelecionados
        .slice()
        .sort(
            (a,b) => a-b
        );


    if (meses.length === 12) {

        return "Ano completo";

    }


    if (meses.length === 1) {

        return compacto
        ?
        abreviacoesMeses[
            meses[0]
        ]
        :
        nomesMeses[
            meses[0]
        ];

    }


    /*
       Se forem meses consecutivos:
       Jan–Mar, Abr–Jul etc.
    */

    let consecutivos = true;

    for (
        let i = 1;
        i < meses.length;
        i++
    ) {

        if (
            meses[i] !==
            meses[i-1] + 1
        ) {

            consecutivos = false;

            break;

        }

    }


    if (consecutivos) {

        return (
            abreviacoesMeses[
                meses[0]
            ]
            +
            "–"
            +
            abreviacoesMeses[
                meses[
                    meses.length - 1
                ]
            ]
        );

    }


    return meses
    .map(
        m =>
        abreviacoesMeses[m]
    )
    .join(" + ");

}


function atualizarResumoMeses() {

    resumoMeses.textContent =
        textoPeriodo(false);

}


function ativarAnoCompleto() {

    mesesSelecionados = null;

    checkboxesMeses.forEach(
        function(check) {

            check.checked = false;

        }
    );

    botaoAnoCompleto
    .classList.add(
        "ativo"
    );

    botaoSelecionarMeses
    .classList.remove(
        "ativo"
    );

    painelMeses
    .classList.remove(
        "aberto"
    );

    atualizarResumoMeses();

    if (dadosCFEM) {
        atualizarMapa();
    }

}


function ativarSelecaoMeses() {

    botaoAnoCompleto
    .classList.remove(
        "ativo"
    );

    botaoSelecionarMeses
    .classList.add(
        "ativo"
    );

    painelMeses
    .classList.add(
        "aberto"
    );


    /*
       Ao entrar pela primeira vez
       na seleção mensal, começa
       com todos os meses marcados.
    */

    if (
        mesesSelecionados === null
    ) {

        mesesSelecionados =
            [
                1,2,3,4,5,6,
                7,8,9,10,11,12
            ];

        checkboxesMeses
        .forEach(
            function(check) {

                check.checked = true;

            }
        );

    }

    atualizarResumoMeses();

    if (dadosCFEM) {
        atualizarMapa();
    }

}


botaoAnoCompleto.onclick =
function() {

    ativarAnoCompleto();

};


botaoSelecionarMeses.onclick =
function() {

    ativarSelecaoMeses();

};


checkboxesMeses.forEach(
function(check) {

    check.addEventListener(
        "change",
        function() {

            mesesSelecionados =
                checkboxesMeses
                .filter(
                    c => c.checked
                )
                .map(
                    c =>
                    Number(c.value)
                )
                .sort(
                    (a,b) => a-b
                );


            botaoAnoCompleto
            .classList.remove(
                "ativo"
            );

            botaoSelecionarMeses
            .classList.add(
                "ativo"
            );


            atualizarResumoMeses();


            if (dadosCFEM) {
                atualizarMapa();
            }

        }
    );

});


selecionarTodosMeses.onclick =
function() {

    mesesSelecionados =
        [
            1,2,3,4,5,6,
            7,8,9,10,11,12
        ];

    checkboxesMeses
    .forEach(
        function(check) {

            check.checked = true;

        }
    );

    atualizarResumoMeses();

    if (dadosCFEM) {
        atualizarMapa();
    }

};


limparMeses.onclick =
function() {

    mesesSelecionados = [];

    checkboxesMeses
    .forEach(
        function(check) {

            check.checked = false;

        }
    );

    atualizarResumoMeses();

    if (dadosCFEM) {
        atualizarMapa();
    }

};


/* ==========================================================
   ANOS
   ========================================================== */

anos
.slice()
.sort(
    (a,b) => b-a
)
.forEach(
function(ano) {

    const op =
        document.createElement(
            "option"
        );

    op.value =
        ano;

    op.textContent =
        ano;

    if (
        Number(ano) ===
        Number(anoPadrao)
    ) {

        op.selected =
            true;

    }

    filtroAno
    .appendChild(op);

});


/* ==========================================================
   SUBSTÂNCIAS
   ========================================================== */

function mostrarSubstancias(
texto
) {

    listaSubstancias
    .innerHTML = "";


    const todas =
        document.createElement(
            "div"
        );

    todas.className =
        "item-substancia item-principal";

    todas.textContent =
        "Todas as substâncias";


    todas.onclick =
    function() {

        substanciaSelecionada =
            "TODAS";

        buscaSubstancia.value =
            "Todas as substâncias";

        listaSubstancias
        .style.display =
            "none";

        atualizarMapa();

    };


    listaSubstancias
    .appendChild(todas);


    const busca =
        normalizar(texto);


    let resultados =
        substancias.filter(
            function(s) {

                return (
                    !busca ||
                    normalizar(s)
                    .includes(busca)
                );

            }
        );


    if (!busca) {

        resultados.sort(
        function(a,b) {

            const ia =
                principais.indexOf(a);

            const ib =
                principais.indexOf(b);

            if (
                ia !== -1 &&
                ib === -1
            )
                return -1;

            if (
                ia === -1 &&
                ib !== -1
            )
                return 1;

            if (
                ia !== -1 &&
                ib !== -1
            )
                return ia - ib;

            return a.localeCompare(
                b,
                "pt-BR"
            );

        });

    }


    resultados
    .slice(0,60)
    .forEach(
    function(s) {

        const item =
            document.createElement(
                "div"
            );

        item.className =
            "item-substancia";


        if (
            principais.includes(s)
        ) {

            item.classList.add(
                "item-principal"
            );

        }


        item.textContent = s;


        item.onclick =
        function() {

            substanciaSelecionada =
                s;

            buscaSubstancia.value =
                s;

            listaSubstancias
            .style.display =
                "none";

            atualizarMapa();

        };


        listaSubstancias
        .appendChild(item);

    });


    listaSubstancias
    .style.display =
        "block";

}


buscaSubstancia
.addEventListener(
"focus",
function() {

    if (
        substanciaSelecionada ===
        "TODAS"
    ) {

        buscaSubstancia.value =
            "";

    }

    mostrarSubstancias(
        buscaSubstancia.value
    );

});


buscaSubstancia
.addEventListener(
"input",
function() {

    mostrarSubstancias(
        buscaSubstancia.value
    );

});


/* ==========================================================
   MUNICÍPIOS
   ========================================================== */

function mostrarMunicipios(
texto
) {

    listaMunicipios
    .innerHTML = "";

    const busca =
        normalizar(texto);


    if (!busca) {

        listaMunicipios
        .style.display =
            "none";

        return;

    }


    const resultados =
        municipiosBusca.filter(
        function(m) {

            return normalizar(
                m.NM_MUN
            ).includes(busca);

        });


    resultados
    .slice(0,30)
    .forEach(
    function(m) {

        const item =
            document.createElement(
                "div"
            );

        item.className =
            "item-municipio";

        item.textContent =
            m.NM_MUN;


        item.onclick =
        function() {

            selecionarMunicipio(
                m.CD_MUN,
                m.NM_MUN,
                true
            );

        };


        listaMunicipios
        .appendChild(item);

    });


    listaMunicipios
    .style.display =
        "block";

}


buscaMunicipio
.addEventListener(
"input",
function() {

    mostrarMunicipios(
        buscaMunicipio.value
    );

});


/* ==========================================================
   SELEÇÃO MUNICIPAL
   ========================================================== */

function selecionarMunicipio(
codigo,
nome,
fazerZoom
) {

    codigo =
        String(codigo);

    codigoMunicipioSelecionado =
        codigo;

    nomeMunicipioSelecionado =
        nome;

    buscaMunicipio.value =
        nome;

    listaMunicipios
    .style.display =
        "none";


    camadaMunicipios
    .eachLayer(
        aplicarEstiloNormal
    );


    camadaMunicipioSelecionado =
        layerPorCodigo.get(
            codigo
        );


    aplicarDestaque();


    if (
        fazerZoom === true &&
        camadaMunicipioSelecionado
    ) {

        mapa.fitBounds(

            camadaMunicipioSelecionado
            .getBounds(),

            {
                padding:[30,30],
                maxZoom:11
            }

        );

    }


    atualizarPainelMunicipio();

    destacarRanking();

}


/* ==========================================================
   CLIQUE NO MAPA
   ========================================================== */

camadaMunicipios
.eachLayer(
function(layer) {

    const p =
        layer.feature
        .properties;


    layer.on(
        "click",
        function() {

            selecionarMunicipio(
                p.CD_MUN,
                p.NM_MUN,
                false
            );

        }
    );

});


/* ==========================================================
   VOLTAR MG
   ========================================================== */

botaoVoltarMG.onclick =
function() {

    codigoMunicipioSelecionado =
        null;

    nomeMunicipioSelecionado =
        null;

    camadaMunicipioSelecionado =
        null;

    buscaMunicipio.value =
        "";

    painelMunicipio
    .style.display =
        "none";

    camadaMunicipios
    .eachLayer(
        aplicarEstiloNormal
    );

    destacarRanking();

    mapa.fitBounds(
        limitesMG
    );

};


/* ==========================================================
   CARREGAR JSON
   ========================================================== */

try {

    const resposta =
        await fetch(
            "dados_cfem.json?v="
            +
            Date.now()
        );


    if (!resposta.ok) {

        throw new Error(
            "HTTP "
            +
            resposta.status
        );

    }


    dadosCFEM =
        await resposta.json();

}

catch(erro) {

    console.error(
        "Erro ao carregar dados:",
        erro
    );

    return;

}


/* ==========================================================
   OBTER VALORES DA CONSULTA
   ========================================================== */

function obterValoresConsulta(
ano
) {

    const valores =
        new Map();

    const mesesAtivos =
        new Set(
            obterMesesAtivos()
        );


    /*
       Nenhum mês marcado.
    */

    if (
        mesesAtivos.size === 0
    ) {

        return valores;

    }


    const fonte =
        substanciaSelecionada ===
        "TODAS"
        ?
        dadosCFEM.totais
        :
        dadosCFEM.substancias;


    fonte.forEach(
    function(item) {

        if (
            Number(item.Ano) !==
            Number(ano)
        )
            return;


        if (
            !mesesAtivos.has(
                Number(item.Mes)
            )
        )
            return;


        if (
            substanciaSelecionada !==
            "TODAS"
            &&
            item["Substância"] !==
            substanciaSelecionada
        )
            return;


        const codigo =
            String(
                item.CodigoMunicipio
            );


        const anterior =
            Number(
                valores.get(
                    codigo
                ) || 0
            );


        valores.set(
            codigo,
            anterior +
            Number(
                item.CFEM_Total || 0
            )
        );

    });


    return valores;

}


/* ==========================================================
   RANKING
   ========================================================== */

function gerarRanking(
valores
) {

    const ranking = [];


    valores.forEach(
    function(valor,codigo) {

        valor =
            Number(valor || 0);

        if (valor <= 0)
            return;


        const m =
            municipioPorCodigo.get(
                String(codigo)
            );

        if (!m)
            return;


        ranking.push({

            codigo:
                String(codigo),

            nome:
                m.NM_MUN,

            valor:
                valor

        });

    });


    ranking.sort(
        (a,b) =>
            b.valor -
            a.valor
            ||
            a.nome.localeCompare(
                b.nome,
                "pt-BR"
            )
    );


    return ranking;

}


/* ==========================================================
   INDICADORES
   ========================================================== */

function atualizarIndicadores() {

    let total = 0;

    let quantidade = 0;


    valoresConsultaAtual
    .forEach(
    function(v) {

        total +=
            Number(v || 0);

        if (
            Number(v) > 0
        ) {

            quantidade++;

        }

    });


    indicadorTotal
    .textContent =
        moeda(total);


    indicadorMunicipios
    .textContent =
        quantidade
        .toLocaleString(
            "pt-BR"
        );


    if (
        rankingConsultaAtual.length
    ) {

        indicadorMaiorValor
        .textContent =
            moeda(
                rankingConsultaAtual[
                    0
                ].valor
            );


        indicadorMaiorMunicipio
        .textContent =
            rankingConsultaAtual[
                0
            ].nome;

    }

    else {

        indicadorMaiorValor
        .textContent =
            moeda(0);

        indicadorMaiorMunicipio
        .textContent =
            "—";

    }

}


/* ==========================================================
   RANKING VISUAL
   ========================================================== */

function atualizarRanking() {

    listaRanking
    .innerHTML = "";


    rankingConsultaAtual
    .slice(0,10)
    .forEach(
    function(item,i) {

        const linha =
            document.createElement(
                "div"
            );

        linha.className =
            "item-ranking";

        linha.dataset.codigo =
            item.codigo;


        linha.innerHTML =

            '<div class="ranking-posicao">'
            +
            (i + 1)
            +
            'º</div>'

            +

            '<div class="ranking-municipio">'
            +
            item.nome
            +
            '</div>'

            +

            '<div class="ranking-valor">'
            +
            moedaCompacta(
                item.valor
            )
            +
            '</div>';


        linha.onclick =
        function() {

            selecionarMunicipio(
                item.codigo,
                item.nome,
                true
            );


            if (ehMobile()) {

                fecharPainelMobile();

            }

        };


        listaRanking
        .appendChild(linha);

    });


    destacarRanking();

}


function destacarRanking() {

    document
    .querySelectorAll(
        ".item-ranking"
    )
    .forEach(
    function(item) {

        item.classList.toggle(

            "selecionado",

            codigoMunicipioSelecionado
            &&
            String(
                item.dataset.codigo
            )
            ===
            String(
                codigoMunicipioSelecionado
            )

        );

    });

}


/* ==========================================================
   SÉRIE HISTÓRICA
   ========================================================== */

function obterSerie(
codigo
) {

    const serie =
        new Map();


    anos.forEach(
        ano =>
        serie.set(
            Number(ano),
            0
        )
    );


    const mesesAtivos =
        new Set(
            obterMesesAtivos()
        );


    const fonte =
        substanciaSelecionada ===
        "TODAS"
        ?
        dadosCFEM.totais
        :
        dadosCFEM.substancias;


    fonte.forEach(
    function(item) {

        if (
            String(
                item.CodigoMunicipio
            )
            !==
            String(codigo)
        )
            return;


        if (
            !mesesAtivos.has(
                Number(item.Mes)
            )
        )
            return;


        if (
            substanciaSelecionada !==
            "TODAS"
            &&
            item["Substância"] !==
            substanciaSelecionada
        )
            return;


        const ano =
            Number(item.Ano);


        const anterior =
            Number(
                serie.get(
                    ano
                ) || 0
            );


        serie.set(

            ano,

            anterior +
            Number(
                item.CFEM_Total || 0
            )

        );

    });


    return serie;

}


function desenharSerie(
serie
) {

    serieBarras
    .innerHTML = "";


    let maximo = 0;


    serie.forEach(
        v =>
        maximo =
            Math.max(
                maximo,
                Number(v)
            )
    );


    const anoAtual =
        Number(
            filtroAno.value
        );


    anos
    .slice()
    .sort(
        (a,b) => a-b
    )
    .forEach(
    function(ano) {

        const valor =
            Number(
                serie.get(
                    Number(ano)
                ) || 0
            );


        const largura =
            maximo > 0
            ?
            valor /
            maximo *
            100
            :
            0;


        const linha =
            document.createElement(
                "div"
            );


        linha.className =
            "serie-linha"
            +
            (
                Number(ano) ===
                anoAtual
                ?
                " ativa"
                :
                ""
            );


        linha.innerHTML =

            '<div class="serie-ano">'
            +
            ano
            +
            (
                Number(ano) ===
                Number(anoPadrao)
                ?
                "*"
                :
                ""
            )
            +
            '</div>'

            +

            '<div class="serie-barra-fundo">'
            +
            '<div class="serie-barra" style="width:'
            +
            largura
            +
            '%"></div>'
            +
            '</div>'

            +

            '<div class="serie-valor">'
            +
            moedaCompacta(
                valor
            )
            +
            '</div>';


        serieBarras
        .appendChild(
            linha
        );

    });


    serieNota.textContent =

        "Período comparado: "
        +
        textoPeriodo(false)
        +
        " em todos os anos. "
        +
        "* "
        +
        anoPadrao
        +
        " corresponde aos dados disponíveis "
        +
        "na base da ANM, atualizada em "
        +
        dataAtualizacaoANM
        +
        ".";

}


/* ==========================================================
   PAINEL MUNICIPAL
   ========================================================== */

function atualizarPainelMunicipio() {

    if (
        !codigoMunicipioSelecionado
    )
        return;


    painelMunicipio
    .style.display =
        "block";


    const ano =
        Number(
            filtroAno.value
        );


    const valor =
        Number(
            valoresConsultaAtual
            .get(
                String(
                    codigoMunicipioSelecionado
                )
            ) || 0
        );


    let totalMG = 0;


    valoresConsultaAtual
    .forEach(
        v =>
        totalMG +=
            Number(v)
    );


    const participacao =
        totalMG > 0
        ?
        valor /
        totalMG *
        100
        :
        0;


    const posicao =
        rankingConsultaAtual
        .findIndex(
            x =>
            String(x.codigo)
            ===
            String(
                codigoMunicipioSelecionado
            )
        );


    municipioNome
    .textContent =
        nomeMunicipioSelecionado;


    municipioValorRotulo
    .textContent =

        "CFEM — "
        +
        ano
        +
        " — "
        +
        textoPeriodo(true);


    municipioValor
    .textContent =
        moeda(valor);


    municipioParticipacao
    .textContent =

        participacao
        .toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits:2,
                maximumFractionDigits:2
            }
        )
        +
        "%";


    municipioPosicao
    .textContent =

        posicao >= 0
        ?
        (posicao + 1)
        +
        "º"
        :
        "Sem arrecadação";


    serieSubstancia
    .textContent =

        substanciaSelecionada ===
        "TODAS"
        ?
        "Todas as substâncias"
        :
        substanciaSelecionada;


    seriePeriodo
    .textContent =

        "Período comparado: "
        +
        textoPeriodo(false);


    desenharSerie(

        obterSerie(
            codigoMunicipioSelecionado
        )

    );

}


/* ==========================================================
   DOWNLOAD CSV
   ========================================================== */

document
.getElementById(
    "botao-download-csv"
)
.onclick =
function() {

    const ano =
        Number(
            filtroAno.value
        );


    const periodo =
        textoPeriodo(false);


    const linhas = [

        [
            "Ano",
            "Meses_selecionados",
            "CodigoMunicipio",
            "Municipio",
            "Substancia",
            "CFEM_Total_R$",
            "Atualizacao_dados_ANM"
        ]
        .join(";")

    ];


    municipiosBusca
    .forEach(
    function(m) {

        const valor =
            Number(
                valoresConsultaAtual
                .get(
                    String(
                        m.CD_MUN
                    )
                ) || 0
            );


        const substancia =
            substanciaSelecionada ===
            "TODAS"
            ?
            "Todas as substâncias"
            :
            substanciaSelecionada;


        linhas.push(

            [

                ano,

                '"' +
                String(periodo)
                .replace(
                    /"/g,
                    '""'
                )
                + '"',

                m.CD_MUN,

                '"' +
                String(m.NM_MUN)
                .replace(
                    /"/g,
                    '""'
                )
                + '"',

                '"' +
                String(substancia)
                .replace(
                    /"/g,
                    '""'
                )
                + '"',

                valor
                .toFixed(2)
                .replace(
                    ".",
                    ","
                ),

                dataAtualizacaoANM

            ]
            .join(";")

        );

    });


    const blob =
        new Blob(

            [
                "\uFEFF"
                +
                linhas.join(
                    "\r\n"
                )
            ],

            {
                type:
                    "text/csv;charset=utf-8"
            }

        );


    const url =
        URL.createObjectURL(
            blob
        );


    const link =
        document.createElement(
            "a"
        );


    link.href = url;


    const periodoArquivo =
        textoPeriodo(true)
        .replace(
            /\s+/g,
            "_"
        )
        .replace(
            /\+/g,
            "-"
        )
        .replace(
            /–/g,
            "-"
        );


    link.download =

        "cfem_mg_"
        +
        ano
        +
        "_"
        +
        periodoArquivo
        +
        ".csv";


    link.click();


    URL.revokeObjectURL(
        url
    );

};


/* ==========================================================
   MODAL
   ========================================================== */

document
.getElementById(
    "botao-sobre"
)
.onclick =
function() {

    modal.classList.add(
        "aberto"
    );

};


document
.getElementById(
    "fechar-modal"
)
.onclick =
function() {

    modal.classList.remove(
        "aberto"
    );

};


modal.onclick =
function(event) {

    if (
        event.target === modal
    ) {

        modal.classList.remove(
            "aberto"
        );

    }

};


/* ==========================================================
   ATUALIZAR MAPA
   ========================================================== */

function atualizarMapa() {

    const ano =
        Number(
            filtroAno.value
        );


    valoresConsultaAtual =
        obterValoresConsulta(
            ano
        );


    rankingConsultaAtual =
        gerarRanking(
            valoresConsultaAtual
        );


    camadaMunicipios
    .eachLayer(
    function(layer) {

        const p =
            layer.feature
            .properties;


        const codigo =
            String(
                p.CD_MUN
            );


        const valor =
            Number(
                valoresConsultaAtual
                .get(
                    codigo
                ) || 0
            );


        p.CFEM_Total =
            valor;

        p.Ano =
            ano;


        aplicarEstiloNormal(
            layer
        );


        const substancia =
            substanciaSelecionada ===
            "TODAS"
            ?
            "Todas as substâncias"
            :
            substanciaSelecionada;


        const tooltip =

            "<b>Município:</b> "
            +
            p.NM_MUN

            +
            "<br>"

            +
            "<b>Ano:</b> "
            +
            ano

            +
            "<br>"

            +
            "<b>Período:</b> "
            +
            textoPeriodo(false)

            +
            "<br>"

            +
            "<b>Substância:</b> "
            +
            substancia

            +
            "<br>"

            +
            "<b>CFEM:</b> "
            +
            moeda(valor)

            +
            "<br>"

            +
            "<span style='color:#666'>"
            +
            "Toque/clique para consultar"
            +
            "</span>";


        if (
            layer.getTooltip()
        ) {

            layer
            .setTooltipContent(
                tooltip
            );

        }

        else {

            layer.bindTooltip(

                tooltip,

                {
                    sticky:true
                }

            );

        }

    });


    atualizarIndicadores();

    atualizarRanking();


    if (
        codigoMunicipioSelecionado
    ) {

        camadaMunicipioSelecionado =
            layerPorCodigo.get(
                String(
                    codigoMunicipioSelecionado
                )
            );

        aplicarDestaque();

        atualizarPainelMunicipio();

    }


    statusAno
    .textContent =
        ano;


    statusPeriodo
    .textContent =
        textoPeriodo(false);


    statusSubstancia
    .textContent =

        substanciaSelecionada ===
        "TODAS"
        ?
        "Todas as substâncias"
        :
        substanciaSelecionada;

}


/* ==========================================================
   ALTERAÇÃO DE ANO
   ========================================================== */

filtroAno.onchange =
function() {

    atualizarMapa();

};


/* ==========================================================
   FECHAR LISTAS
   ========================================================== */

document.addEventListener(
"click",
function(event) {

    if (
        event.target !==
        buscaSubstancia
        &&
        !listaSubstancias
        .contains(
            event.target
        )
    ) {

        listaSubstancias
        .style.display =
            "none";

    }


    if (
        event.target !==
        buscaMunicipio
        &&
        !listaMunicipios
        .contains(
            event.target
        )
    ) {

        listaMunicipios
        .style.display =
            "none";

    }

});


/* ==========================================================
   RESIZE
   ========================================================== */

window.addEventListener(
"resize",
function() {

    if (!ehMobile()) {

        painel.classList.remove(
            "aberto"
        );

        document.body
        .classList.remove(
            "painel-mobile-aberto"
        );

        legenda.classList.remove(
            "aberta"
        );

        botaoLegenda
        .textContent =
            "Legenda";

    }


    setTimeout(
        function() {

            mapa.invalidateSize();

        },
        100
    );

});


/* ==========================================================
   INICIALIZAÇÃO
   ========================================================== */

atualizarResumoMeses();

atualizarMapa();

});
</script>
"""


# ============================================================
# 25. PLACEHOLDERS
# ============================================================

interface_html = interface_html.replace(
    "__MAPA_JS__",
    nome_mapa_js
)

interface_html = interface_html.replace(
    "__CAMADA_MUNICIPIOS__",
    nome_camada_js
)

interface_html = interface_html.replace(
    "__ANOS_JSON__",
    anos_json
)

interface_html = interface_html.replace(
    "__SUBSTANCIAS_JSON__",
    substancias_json
)

interface_html = interface_html.replace(
    "__PRINCIPAIS_JSON__",
    principais_json
)

interface_html = interface_html.replace(
    "__MUNICIPIOS_JSON__",
    municipios_json
)

interface_html = interface_html.replace(
    "__LIMITES_MG__",
    limites_mg_json
)

interface_html = interface_html.replace(
    "__ANO_PADRAO__",
    str(int(ano_padrao))
)

interface_html = interface_html.replace(
    "__DATA_ATUALIZACAO_ANM_JSON__",
    data_atualizacao_anm_json
)

interface_html = interface_html.replace(
    "__DATA_ATUALIZACAO_ANM__",
    data_atualizacao_anm
)

interface_html = interface_html.replace(
    "__DATA_GERACAO_WEBGIS__",
    data_geracao_webgis
)


# ============================================================
# 26. INTERFACE
# ============================================================

mapa_cfem.get_root().html.add_child(
    folium.Element(
        interface_html
    )
)


# ============================================================
# 27. LAYER CONTROL
# ============================================================

folium.LayerControl(
    collapsed=True
).add_to(
    mapa_cfem
)


# ============================================================
# 28. ENQUADRAR MG
# ============================================================

mapa_cfem.fit_bounds(
    limites_mg
)


# ============================================================
# 29. SALVAR
# ============================================================

print("\nSalvando WebGIS...")

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 30. FINAL
# ============================================================

print("\n" + "=" * 70)

print(
    "WEBGIS ATUALIZADO COM SUCESSO"
)

print("=" * 70)

print(
    "Mapa:",
    ARQUIVO_SAIDA
)

print(
    "JSON:",
    ARQUIVO_DADOS
)

print(
    "Atualização ANM:",
    data_atualizacao_anm
)

print(
    "WebGIS gerado em:",
    data_geracao_webgis
)

print(
    "Anos:",
    anos
)

print(
    "Municípios:",
    len(municipios)
)

print(
    "Substâncias:",
    len(todas_substancias)
)

print(
    "Filtro mensal:",
    "habilitado"
)

print("=" * 70)
