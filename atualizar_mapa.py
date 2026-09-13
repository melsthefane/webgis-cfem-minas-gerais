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
    cfem["UF"].astype(str).str.strip().str.upper() == "MG"
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
        columns={"ValorRecolhido": "CFEM_Total"}
    )
)


# Padronizar código IBGE

cfem_total["CodigoMunicipio"] = (
    cfem_total["CodigoMunicipio"]
    .astype(str)
    .str.replace(".0", "", regex=False)
    .str.zfill(7)
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

municipios = municipios.to_crs(
    epsg=4326
)

municipios["CD_MUN"] = (
    municipios["CD_MUN"]
    .astype(str)
    .str.replace(".0", "", regex=False)
    .str.zfill(7)
)

print(
    f"Municípios carregados: "
    f"{len(municipios)}"
)


# ============================================================
# 7. FUNÇÃO DE CORES
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
    location=[-18.5, -44.5],
    zoom_start=6,
    tiles=None
)


# ============================================================
# 9. MAPAS BASE
# ============================================================

folium.TileLayer(
    tiles=(
        "https://{s}.tile-cyclosm.openstreetmap.fr/"
        "cyclosm/{z}/{x}/{y}.png"
    ),
    name="CyclOSM",
    attr="CyclOSM | © OpenStreetMap contributors",
    overlay=False,
    control=True,
    show=True
).add_to(mapa_cfem)


folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/ArcGIS/rest/"
        "services/World_Topo_Map/MapServer/"
        "tile/{z}/{y}/{x}"
    ),
    name="Esri World Topo",
    attr="Tiles © Esri",
    overlay=False,
    control=True,
    show=False
).add_to(mapa_cfem)


# ============================================================
# 10. CRIAR CAMADAS POR ANO
# ============================================================

for ano in anos:

    print(f"Criando camada {ano}...")

    dados_ano = cfem_total[
        cfem_total["Ano"] == ano
    ].copy()


    geo_ano = municipios.merge(
        dados_ano[
            ["CodigoMunicipio", "CFEM_Total"]
        ],
        left_on="CD_MUN",
        right_on="CodigoMunicipio",
        how="left"
    )


    geo_ano["CFEM_Total"] = (
        geo_ano["CFEM_Total"]
        .fillna(0)
    )

    geo_ano["Ano"] = ano


    # Formatação monetária brasileira

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


    camada = folium.FeatureGroup(
        name=f"CFEM {ano}",
        show=(ano == anos[-1])
    )


    def estilo(feature):

        valor = feature[
            "properties"
        ]["CFEM_Total"]

        return {
            "fillColor": cor_cfem(valor),
            "color": "#555555",
            "weight": 0.5,
            "fillOpacity": 0.80
        }


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

    ).add_to(camada)


    camada.add_to(mapa_cfem)


# ============================================================
# 11. LEGENDA
# ============================================================

template_legenda = """
{% macro html(this, kwargs) %}

<div style="
position: fixed;
bottom: 30px;
left: 30px;
width: 245px;
background-color: white;
border: 2px solid #777;
border-radius: 6px;
z-index: 9999;
padding: 12px;
font-size: 13px;
box-shadow: 0 1px 5px rgba(0,0,0,0.4);
">

<div style="
font-size:15px;
font-weight:bold;
margin-bottom:8px;">
CFEM arrecadada
</div>

<div>
<span style="background:#eeeeee;width:18px;height:18px;display:inline-block;"></span>
&nbsp; Sem arrecadação
</div>

<div>
<span style="background:#ffffcc;width:18px;height:18px;display:inline-block;"></span>
&nbsp; Até R$ 10 mil
</div>

<div>
<span style="background:#ffeda0;width:18px;height:18px;display:inline-block;"></span>
&nbsp; R$ 10 mil – R$ 100 mil
</div>

<div>
<span style="background:#fed976;width:18px;height:18px;display:inline-block;"></span>
&nbsp; R$ 100 mil – R$ 1 milhão
</div>

<div>
<span style="background:#feb24c;width:18px;height:18px;display:inline-block;"></span>
&nbsp; R$ 1 mi – R$ 10 milhões
</div>

<div>
<span style="background:#f03b20;width:18px;height:18px;display:inline-block;"></span>
&nbsp; R$ 10 mi – R$ 100 milhões
</div>

<div>
<span style="background:#bd0026;width:18px;height:18px;display:inline-block;"></span>
&nbsp; Acima de R$ 100 milhões
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
# 12. CONTROLE DE CAMADAS
# ============================================================

folium.LayerControl(
    collapsed=False
).add_to(mapa_cfem)


# ============================================================
# 13. ENQUADRAR MINAS GERAIS
# ============================================================

minx, miny, maxx, maxy = (
    municipios.total_bounds
)

mapa_cfem.fit_bounds(
    [
        [miny, minx],
        [maxy, maxx]
    ]
)


# ============================================================
# 14. SALVAR INDEX.HTML
# ============================================================

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 15. FINALIZAÇÃO
# ============================================================

data_execucao = datetime.now().strftime(
    "%d/%m/%Y %H:%M"
)

print("\n" + "=" * 60)
print("MAPA ATUALIZADO COM SUCESSO")
print(f"Arquivo: {ARQUIVO_SAIDA}")
print(f"Execução: {data_execucao}")
print(f"Anos: {anos}")
print("=" * 60)
