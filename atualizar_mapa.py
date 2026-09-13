import pandas as pd
import geopandas as gpd
import folium
import requests

from io import BytesIO
from datetime import datetime
from branca.element import Template, MacroElement


# ============================================================
# WEBGIS CFEM - MINAS GERAIS
# Atualização automática dos dados da ANM
# ============================================================

URL_CFEM = (
    "https://dadosabertos.anm.gov.br/CFEM/"
    "CFEM_Arrecadacao_2022_2026.csv"
)

ARQUIVO_MUNICIPIOS = "municipios_mg.geojson"
ARQUIVO_SAIDA = "index.html"


print("=" * 60)
print("WEBGIS CFEM - MINAS GERAIS")
print("Iniciando atualização...")
print("=" * 60)


# ============================================================
# 1. BAIXAR DADOS DA ANM
# ============================================================

print("\nBaixando dados da ANM...")

headers = {
    "User-Agent": "Mozilla/5.0"
}

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
# 2. LER CSV
# ============================================================

print("\nLendo arquivo CSV...")

cfem = pd.read_csv(
    BytesIO(response.content),
    sep=None,
    engine="python",
    encoding="latin1"
)

print(f"Registros encontrados: {len(cfem):,}")
print(f"Colunas encontradas: {len(cfem.columns)}")


# ============================================================
# 3. FILTRAR MINAS GERAIS
# ============================================================

cfem_mg = cfem[
    cfem["UF"]
    .astype(str)
    .str.strip()
    .str.upper() == "MG"
].copy()

print(
    f"Registros de Minas Gerais: "
    f"{len(cfem_mg):,}"
)


# ============================================================
# 4. CONVERTER VALOR RECOLHIDO
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
# 5. SOMAR CFEM POR MUNICÍPIO E ANO
# ============================================================

cfem_total = (
    cfem_mg
    .groupby(
        ["Ano", "CodigoMunicipio"],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido": "CFEM_Total"
        }
    )
)


# Padronizar código IBGE

cfem_total["CodigoMunicipio"] = (
    cfem_total["CodigoMunicipio"]
    .astype(str)
    .str.replace(
        r"\.0$",
        "",
        regex=True
    )
    .str.zfill(7)
)


# Padronizar ano

cfem_total["Ano"] = pd.to_numeric(
    cfem_total["Ano"],
    errors="coerce"
)


anos = sorted(
    cfem_total["Ano"]
    .dropna()
    .astype(int)
    .unique()
)


print("\nAnos encontrados:")
print(anos)


# ============================================================
# 6. CARREGAR MUNICÍPIOS DE MINAS GERAIS
# ============================================================

print("\nCarregando municípios...")

municipios = gpd.read_file(
    ARQUIVO_MUNICIPIOS
)


# Garantir sistema de coordenadas WGS84

municipios = municipios.to_crs(
    epsg=4326
)


# Padronizar código IBGE municipal

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


print(
    f"Municípios carregados: "
    f"{len(municipios)}"
)


# ============================================================
# 7. FUNÇÃO DE CORES DA CFEM
# ============================================================

def cor_cfem(valor):

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

    else:
        return "#bd0026"


# ============================================================
# 8. CRIAR MAPA
# ============================================================

print("\nCriando mapa...")

mapa_cfem = folium.Map(
    location=[
        -18.5,
        -44.5
    ],
    zoom_start=6,
    tiles=None,
    control_scale=True
)


# ============================================================
# 9. MAPAS BASE
# ============================================================

# CyclOSM

folium.TileLayer(
    tiles=(
        "https://{s}.tile-cyclosm.openstreetmap.fr/"
        "cyclosm/{z}/{x}/{y}.png"
    ),
    name="CyclOSM",
    attr=(
        "CyclOSM | "
        "© OpenStreetMap contributors"
    ),
    overlay=False,
    control=True,
    show=True
).add_to(mapa_cfem)


# Esri World Topographic Map

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
# 10. TÍTULO DO MAPA
# ============================================================

titulo_html = """
<div style="
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 9999;

    background-color:
        rgba(255,255,255,0.95);

    border: 2px solid #777;
    border-radius: 6px;

    padding: 12px 18px;

    box-shadow:
        0 1px 5px rgba(0,0,0,0.4);

    text-align: left;

    font-family:
        Arial, sans-serif;

    max-width: 480px;
">

    <div style="
        font-size: 20px;
        font-weight: bold;
        line-height: 1.2;
    ">
        Mapa de Arrecadação da CFEM — Minas Gerais
    </div>

    <div style="
        font-size: 13px;
        margin-top: 5px;
        line-height: 1.3;
    ">
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
# 11. CRIAR CAMADAS DE CFEM POR ANO
# ============================================================

for ano in anos:

    print(
        f"Criando camada {ano}..."
    )


    # --------------------------------------------------------
    # Dados do ano
    # --------------------------------------------------------

    dados_ano = cfem_total[
        cfem_total["Ano"] == ano
    ].copy()


    # --------------------------------------------------------
    # Juntar CFEM com municípios
    # --------------------------------------------------------

    geo_ano = municipios.merge(

        dados_ano[
            [
                "CodigoMunicipio",
                "CFEM_Total"
            ]
        ],

        left_on="CD_MUN",

        right_on="CodigoMunicipio",

        how="left"
    )


    # Municípios sem arrecadação recebem zero

    geo_ano["CFEM_Total"] = (
        geo_ano["CFEM_Total"]
        .fillna(0)
        .astype(float)
    )


    geo_ano["Ano"] = int(
        ano
    )


    # --------------------------------------------------------
    # Formatação monetária brasileira
    # --------------------------------------------------------

    geo_ano["CFEM_R$"] = (
        geo_ano["CFEM_Total"]
        .apply(
            lambda x:
            f"R$ {x:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    )


    # --------------------------------------------------------
    # Grupo da camada
    # --------------------------------------------------------

    camada = folium.FeatureGroup(

        name=f"CFEM {ano}",

        show=(
            ano == anos[-1]
        )
    )


    # --------------------------------------------------------
    # Estilo dos municípios
    # --------------------------------------------------------

    def estilo(feature):

        valor = feature[
            "properties"
        ]["CFEM_Total"]

        return {

            "fillColor":
                cor_cfem(valor),

            "color":
                "#555555",

            "weight":
                0.5,

            "fillOpacity":
                0.80
        }


    # --------------------------------------------------------
    # GeoJSON
    # --------------------------------------------------------

    folium.GeoJson(

        geo_ano[
            [
                "CD_MUN",
                "NM_MUN",
                "Ano",
                "CFEM_Total",
                "CFEM_R$",
                "geometry"
            ]
        ],

        style_function=estilo,

        highlight_function=lambda feature: {

            "weight": 3,

            "color": "black",

            "fillOpacity": 0.9
        },

        tooltip=folium.GeoJsonTooltip(

            fields=[
                "NM_MUN",
                "Ano",
                "CFEM_R$"
            ],

            aliases=[
                "Município:",
                "Ano:",
                "CFEM total:"
            ],

            sticky=True
        )

    ).add_to(
        camada
    )


    camada.add_to(
        mapa_cfem
    )


# ============================================================
# 12. LEGENDA + CRÉDITOS
# ============================================================

template_legenda = """
{% macro html(this, kwargs) %}

<div style="
    position: fixed;
    bottom: 30px;
    left: 30px;

    width: 270px;

    background-color:
        rgba(255,255,255,0.95);

    border:
        2px solid #777;

    border-radius:
        6px;

    z-index:
        9999;

    padding:
        12px;

    font-size:
        13px;

    font-family:
        Arial, sans-serif;

    line-height:
        1.4;

    box-shadow:
        0 1px 5px rgba(0,0,0,0.4);
">


<!-- TÍTULO DA LEGENDA -->

<div style="
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 8px;
">
    CFEM arrecadada
</div>


<!-- SEM ARRECADAÇÃO -->

<div style="margin-bottom:3px;">

<span style="
    background:#eeeeee;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; Sem arrecadação

</div>


<!-- ATÉ 10 MIL -->

<div style="margin-bottom:3px;">

<span style="
    background:#ffffcc;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; Até R$ 10 mil

</div>


<!-- 10 MIL A 100 MIL -->

<div style="margin-bottom:3px;">

<span style="
    background:#ffeda0;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; R$ 10 mil – R$ 100 mil

</div>


<!-- 100 MIL A 1 MILHÃO -->

<div style="margin-bottom:3px;">

<span style="
    background:#fed976;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; R$ 100 mil – R$ 1 milhão

</div>


<!-- 1 A 10 MILHÕES -->

<div style="margin-bottom:3px;">

<span style="
    background:#feb24c;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; R$ 1 mi – R$ 10 milhões

</div>


<!-- 10 A 100 MILHÕES -->

<div style="margin-bottom:3px;">

<span style="
    background:#f03b20;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; R$ 10 mi – R$ 100 milhões

</div>


<!-- ACIMA DE 100 MILHÕES -->

<div>

<span style="
    background:#bd0026;
    width:18px;
    height:18px;
    display:inline-block;
    border:1px solid #999;
    vertical-align:middle;
"></span>

&nbsp; Acima de R$ 100 milhões

</div>


<!-- CRÉDITOS -->

<div style="
    border-top:
        1px solid #bbb;

    margin-top:
        10px;

    padding-top:
        8px;

    font-size:
        11px;

    line-height:
        1.45;
">

<b>Autoria:</b>
Melissa Carvalho

<br>

<b>Elaboração:</b>
13/09/2026

<br>

<b>Fontes:</b>
Malha Municipal de Minas Gerais — IBGE;

<br>

Arrecadação da CFEM (2022–2026) — ANM.

</div>


</div>

{% endmacro %}
"""


macro_legenda = MacroElement()

macro_legenda._template = Template(
    template_legenda
)

mapa_cfem.get_root().add_child(
    macro_legenda
)


# ============================================================
# 13. CONTROLE DE CAMADAS
# ============================================================

folium.LayerControl(
    collapsed=False
).add_to(
    mapa_cfem
)


# ============================================================
# 14. ENQUADRAR MINAS GERAIS
# ============================================================

minx, miny, maxx, maxy = (
    municipios.total_bounds
)


mapa_cfem.fit_bounds(
    [
        [
            miny,
            minx
        ],
        [
            maxy,
            maxx
        ]
    ]
)


# ============================================================
# 15. SALVAR INDEX.HTML
# ============================================================

print(
    "\nSalvando mapa..."
)

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 16. FINALIZAÇÃO
# ============================================================

data_execucao = (
    datetime.now()
    .strftime(
        "%d/%m/%Y %H:%M"
    )
)


print(
    "\n" + "=" * 60
)

print(
    "MAPA ATUALIZADO COM SUCESSO"
)

print(
    f"Arquivo: {ARQUIVO_SAIDA}"
)

print(
    f"Execução: {data_execucao}"
)

print(
    f"Anos: {anos}"
)

print(
    "=" * 60
)
