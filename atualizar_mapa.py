import pandas as pd
import geopandas as gpd
import folium
import requests
import json

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

# Novo arquivo que será utilizado pela interface dinâmica
ARQUIVO_DADOS = "dados_cfem.json"


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
# 4. PADRONIZAR DADOS
# ============================================================

# ------------------------------------------------------------
# 4.1 Valor recolhido
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# 4.2 Código do município
# ------------------------------------------------------------

cfem_mg["CodigoMunicipio"] = (
    cfem_mg["CodigoMunicipio"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(7)
)


# ------------------------------------------------------------
# 4.3 Ano
# ------------------------------------------------------------

cfem_mg["Ano"] = pd.to_numeric(
    cfem_mg["Ano"],
    errors="coerce"
)


# ------------------------------------------------------------
# 4.4 Nome do município
# ------------------------------------------------------------

cfem_mg["Município"] = (
    cfem_mg["Município"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ------------------------------------------------------------
# 4.5 Substância mineral
# ------------------------------------------------------------

cfem_mg["Substância"] = (
    cfem_mg["Substância"]
    .fillna("Não informada")
    .astype(str)
    .str.strip()
)

cfem_mg.loc[
    cfem_mg["Substância"] == "",
    "Substância"
] = "Não informada"


# ============================================================
# 5. CFEM TOTAL POR MUNICÍPIO E ANO
# ============================================================

cfem_total = (
    cfem_mg
    .groupby(
        [
            "Ano",
            "CodigoMunicipio"
        ],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido": "CFEM_Total"
        }
    )
)


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
# 6. PREPARAR DADOS POR SUBSTÂNCIA
# ============================================================

print(
    "\nPreparando dados por município, ano e substância..."
)


cfem_substancias = (
    cfem_mg
    .groupby(
        [
            "Ano",
            "CodigoMunicipio",
            "Município",
            "Substância"
        ],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido": "CFEM_Total"
        }
    )
)


# Remover registros sem ano válido

cfem_substancias = (
    cfem_substancias[
        cfem_substancias["Ano"].notna()
    ]
    .copy()
)


cfem_substancias["Ano"] = (
    cfem_substancias["Ano"]
    .astype(int)
)


cfem_substancias["CodigoMunicipio"] = (
    cfem_substancias["CodigoMunicipio"]
    .astype(str)
    .str.replace(
        r"\.0$",
        "",
        regex=True
    )
    .str.zfill(7)
)


cfem_substancias["CFEM_Total"] = (
    cfem_substancias["CFEM_Total"]
    .astype(float)
)


print(
    f"Registros agregados por substância: "
    f"{len(cfem_substancias):,}"
)


# ============================================================
# 7. IDENTIFICAR PRINCIPAIS SUBSTÂNCIAS
# ============================================================

print(
    "\nIdentificando principais substâncias..."
)


ranking_substancias = (
    cfem_substancias
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


# Quantidade de substâncias principais exibidas no futuro menu.
# Podemos alterar esse número depois, se necessário.

QUANTIDADE_PRINCIPAIS_SUBSTANCIAS = 10


principais_substancias = (
    ranking_substancias
    .head(
        QUANTIDADE_PRINCIPAIS_SUBSTANCIAS
    )["Substância"]
    .tolist()
)


print(
    "\nPrincipais substâncias encontradas:"
)

for posicao, substancia in enumerate(
    principais_substancias,
    start=1
):
    print(
        f"{posicao}. {substancia}"
    )


# ============================================================
# 8. GERAR dados_cfem.json
# ============================================================

print(
    f"\nGerando {ARQUIVO_DADOS}..."
)


# ------------------------------------------------------------
# 8.1 Dados totais por município e ano
# ------------------------------------------------------------

dados_totais_json = (
    cfem_mg
    .groupby(
        [
            "Ano",
            "CodigoMunicipio",
            "Município"
        ],
        as_index=False
    )["ValorRecolhido"]
    .sum()
    .rename(
        columns={
            "ValorRecolhido": "CFEM_Total"
        }
    )
)


dados_totais_json = (
    dados_totais_json[
        dados_totais_json["Ano"].notna()
    ]
    .copy()
)


dados_totais_json["Ano"] = (
    dados_totais_json["Ano"]
    .astype(int)
)


dados_totais_json["CodigoMunicipio"] = (
    dados_totais_json["CodigoMunicipio"]
    .astype(str)
    .str.replace(
        r"\.0$",
        "",
        regex=True
    )
    .str.zfill(7)
)


dados_totais_json["CFEM_Total"] = (
    dados_totais_json["CFEM_Total"]
    .astype(float)
)


# ------------------------------------------------------------
# 8.2 Montar estrutura JSON
# ------------------------------------------------------------

dados_webgis = {

    "metadata": {

        "titulo":
            "Mapa de Arrecadação da CFEM — Minas Gerais",

        "descricao":
            "Compensação Financeira pela Exploração "
            "de Recursos Minerais",

        "autoria":
            "Melissa Carvalho",

        "fonte_cfem":
            "Agência Nacional de Mineração — ANM",

        "fonte_malha":
            "Instituto Brasileiro de Geografia "
            "e Estatística — IBGE",

        "anos":
            [int(ano) for ano in anos],

        "principais_substancias":
            principais_substancias,

        "quantidade_principais_substancias":
            QUANTIDADE_PRINCIPAIS_SUBSTANCIAS,

        "gerado_em":
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
    },


    # Dados usados quando o usuário selecionar
    # "Todas as substâncias"

    "totais": (
        dados_totais_json
        .to_dict(
            orient="records"
        )
    ),


    # Dados utilizados quando uma substância
    # específica for selecionada

    "substancias": (
        cfem_substancias
        .to_dict(
            orient="records"
        )
    )
}


# ------------------------------------------------------------
# 8.3 Salvar JSON
# ------------------------------------------------------------

with open(
    ARQUIVO_DADOS,
    "w",
    encoding="utf-8"
) as arquivo_json:

    json.dump(
        dados_webgis,
        arquivo_json,
        ensure_ascii=False,
        separators=(",", ":")
    )


print(
    f"{ARQUIVO_DADOS} gerado com sucesso."
)


# ============================================================
# 9. CARREGAR MUNICÍPIOS DE MINAS GERAIS
# ============================================================

print(
    "\nCarregando municípios..."
)


municipios = gpd.read_file(
    ARQUIVO_MUNICIPIOS
)


# Garantir WGS84

municipios = municipios.to_crs(
    epsg=4326
)


# Padronizar código IBGE

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
# 10. FUNÇÃO DE CORES
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
# 11. CRIAR MAPA
# ============================================================

print(
    "\nCriando mapa..."
)


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
# 12. MAPAS BASE
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

).add_to(
    mapa_cfem
)


# Esri World Topo

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

).add_to(
    mapa_cfem
)


# ============================================================
# 13. TÍTULO DO MAPA
# ============================================================

titulo_html = """
<div style="
    position: fixed;
    top: 10px;
    left: 70px;
    z-index: 9999;

    background-color: rgba(255,255,255,0.95);

    border: 2px solid #777;
    border-radius: 6px;

    padding: 10px 18px;

    box-shadow: 0 1px 5px rgba(0,0,0,0.4);

    text-align: left;

    font-family: Arial, sans-serif;

    white-space: nowrap;
">

    <div style="
        font-size: 20px;
        font-weight: bold;
        line-height: 1.2;
        white-space: nowrap;
    ">
        Mapa de Arrecadação da CFEM — Minas Gerais
    </div>

    <div style="
        font-size: 13px;
        margin-top: 5px;
        line-height: 1.3;
        white-space: nowrap;
    ">
        Compensação Financeira pela Exploração de Recursos Minerais
    </div>

</div>
"""


mapa_cfem.get_root().html.add_child(
    folium.Element(
        titulo_html
    )
)

# ============================================================
# 13.1 PAINEL DE FILTROS - ANO E SUBSTÂNCIA
# ============================================================

# Ano mais recente disponível
ano_padrao = max(anos)


# ------------------------------------------------------------
# Criar opções do seletor de ano
# ------------------------------------------------------------

opcoes_anos = ""

for ano in sorted(anos, reverse=True):

    selecionado = (
        "selected"
        if ano == ano_padrao
        else ""
    )

    texto_ano = str(ano)

    # Ano mais recente ainda pode representar dados parciais
    if ano == ano_padrao:
        texto_ano = f"{ano}"

    opcoes_anos += (
        f'<option value="{ano}" {selecionado}>'
        f'{texto_ano}'
        f'</option>'
    )


# ------------------------------------------------------------
# Criar opções do seletor de substâncias
# ------------------------------------------------------------

opcoes_substancias = (
    '<option value="TODAS" selected>'
    'Todas as substâncias'
    '</option>'
)

for substancia in principais_substancias:

    # Escapar caracteres que poderiam interferir no HTML
    substancia_html = (
        str(substancia)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    opcoes_substancias += (
        f'<option value="{substancia_html}">'
        f'{substancia_html}'
        f'</option>'
    )


# ------------------------------------------------------------
# HTML + CSS do painel
# ------------------------------------------------------------

painel_filtros_html = f"""
<style>

/* ==========================================================
   PAINEL DE FILTROS
   ========================================================== */

#painel-filtros-cfem {{

    position: fixed;

    top: 95px;
    right: 20px;

    width: 290px;

    z-index: 9998;

    background: rgba(255,255,255,0.96);

    border: 1px solid #999;

    border-radius: 8px;

    padding: 14px;

    box-sizing: border-box;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.25);

    font-family:
        Arial,
        sans-serif;
}}


#painel-filtros-cfem .titulo-painel {{

    font-size: 16px;

    font-weight: bold;

    margin-bottom: 12px;

    color: #333;
}}


#painel-filtros-cfem label {{

    display: block;

    margin-top: 8px;

    margin-bottom: 5px;

    font-size: 12px;

    font-weight: bold;

    color: #444;
}}


#painel-filtros-cfem select {{

    width: 100%;

    padding: 8px 10px;

    border: 1px solid #aaa;

    border-radius: 5px;

    background-color: white;

    font-size: 13px;

    font-family:
        Arial,
        sans-serif;

    box-sizing: border-box;

    cursor: pointer;
}}


#painel-filtros-cfem select:focus {{

    outline: 2px solid #777;

    outline-offset: 1px;
}}


#status-filtro-cfem {{

    margin-top: 11px;

    padding-top: 9px;

    border-top: 1px solid #ddd;

    font-size: 11px;

    line-height: 1.4;

    color: #666;
}}


/* ==========================================================
   RESPONSIVIDADE
   ========================================================== */

@media screen and (max-width: 768px) {{

    /*
    Título adaptado para telas menores.
    */

    #painel-filtros-cfem {{

        top: auto;

        bottom: 15px;
        left: 10px;
        right: 10px;

        width: auto;

        max-height: 42vh;

        overflow-y: auto;

        padding: 10px;

        z-index: 10000;
    }}


    #painel-filtros-cfem .titulo-painel {{

        font-size: 14px;

        margin-bottom: 7px;
    }}


    #painel-filtros-cfem label {{

        margin-top: 5px;

        font-size: 11px;
    }}


    #painel-filtros-cfem select {{

        padding: 7px;

        font-size: 12px;
    }}


    #status-filtro-cfem {{

        font-size: 10px;

        margin-top: 7px;

        padding-top: 6px;
    }}

}}

</style>


<div id="painel-filtros-cfem">

    <div class="titulo-painel">
        Consulta CFEM
    </div>


    <label for="filtro-ano-cfem">
        Ano
    </label>

    <select id="filtro-ano-cfem">

        {opcoes_anos}

    </select>


    <label for="filtro-substancia-cfem">
        Substância mineral
    </label>

    <select id="filtro-substancia-cfem">

        {opcoes_substancias}

    </select>


    <div id="status-filtro-cfem">

        Exibindo:

        <b id="status-ano-cfem">
            {ano_padrao}
        </b>

        ·

        <b id="status-substancia-cfem">
            Todas as substâncias
        </b>

    </div>

</div>


<script>

document.addEventListener(
    "DOMContentLoaded",
    function() {{

        const filtroAno =
            document.getElementById(
                "filtro-ano-cfem"
            );

        const filtroSubstancia =
            document.getElementById(
                "filtro-substancia-cfem"
            );

        const statusAno =
            document.getElementById(
                "status-ano-cfem"
            );

        const statusSubstancia =
            document.getElementById(
                "status-substancia-cfem"
            );


        function atualizarStatusFiltros() {{

            statusAno.textContent =
                filtroAno.options[
                    filtroAno.selectedIndex
                ].text;


            statusSubstancia.textContent =
                filtroSubstancia.options[
                    filtroSubstancia.selectedIndex
                ].text;

        }}


        filtroAno.addEventListener(
            "change",
            atualizarStatusFiltros
        );


        filtroSubstancia.addEventListener(
            "change",
            atualizarStatusFiltros
        );

    }}
);

</script>
"""


mapa_cfem.get_root().html.add_child(
    folium.Element(
        painel_filtros_html
    )
)

# ============================================================
# 14. CRIAR CAMADAS DE CFEM POR ANO
# ============================================================

for ano in anos:

    print(
        f"Criando camada {ano}..."
    )


    dados_ano = cfem_total[
        cfem_total["Ano"] == ano
    ].copy()


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
    # Camada do ano
    # --------------------------------------------------------

    camada = folium.FeatureGroup(

        name=f"CFEM {ano}",

        show=(
            ano == anos[-1]
        )
    )


    # --------------------------------------------------------
    # Estilo
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
# 15. LEGENDA + CRÉDITOS
# ============================================================

template_legenda = """
{% macro html(this, kwargs) %}

<div style="
    position: fixed;
    bottom: 30px;
    left: 30px;

    width: 270px;

    background-color: rgba(255,255,255,0.95);

    border: 2px solid #777;
    border-radius: 6px;

    z-index: 9999;

    padding: 12px;

    font-size: 13px;

    font-family: Arial, sans-serif;

    line-height: 1.4;

    box-shadow: 0 1px 5px rgba(0,0,0,0.4);
">


<div style="
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 8px;
">
    CFEM arrecadada
</div>


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
    border-top: 1px solid #bbb;

    margin-top: 10px;

    padding-top: 8px;

    font-size: 11px;

    line-height: 1.45;
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
# 16. CONTROLE DE CAMADAS
# ============================================================

folium.LayerControl(
    collapsed=False
).add_to(
    mapa_cfem
)


# ============================================================
# 17. ENQUADRAR MINAS GERAIS
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
# 18. SALVAR INDEX.HTML
# ============================================================

print(
    "\nSalvando mapa..."
)

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 19. FINALIZAÇÃO
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
    f"Mapa: {ARQUIVO_SAIDA}"
)

print(
    f"Dados: {ARQUIVO_DADOS}"
)

print(
    f"Execução: {data_execucao}"
)

print(
    f"Anos: {anos}"
)

print(
    f"Principais substâncias: "
    f"{principais_substancias}"
)

print(
    "=" * 60
)
