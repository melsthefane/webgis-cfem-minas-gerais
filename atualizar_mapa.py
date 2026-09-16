import json
from datetime import datetime
from io import BytesIO

import folium
import geopandas as gpd
import pandas as pd
import requests


# ============================================================
# WEBGIS CFEM - MINAS GERAIS
# ETAPA 7
#
# Recursos:
# - atualização automática dos dados da ANM
# - filtro por ano
# - filtro inteligente por substância
# - busca inteligente por município
# - zoom automático no município
# - indicadores dinâmicos
# - ranking municipal dinâmico Top 10
# - ranking clicável com zoom no município
# ============================================================


URL_CFEM = (
    "https://dadosabertos.anm.gov.br/CFEM/"
    "CFEM_Arrecadacao_2022_2026.csv"
)

ARQUIVO_MUNICIPIOS = "municipios_mg.geojson"
ARQUIVO_SAIDA = "index.html"
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

print(
    f"Registros encontrados: "
    f"{len(cfem):,}"
)

print(
    f"Colunas encontradas: "
    f"{len(cfem.columns)}"
)


# ============================================================
# 3. FILTRAR MINAS GERAIS
# ============================================================

cfem_mg = cfem[
    cfem["UF"]
    .astype(str)
    .str.strip()
    .str.upper()
    .eq("MG")
].copy()

print(
    f"Registros de Minas Gerais: "
    f"{len(cfem_mg):,}"
)


# ============================================================
# 4. TRATAR VALOR RECOLHIDO
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
# 5. TRATAR CÓDIGO MUNICIPAL
# ============================================================

cfem_mg["CodigoMunicipio"] = (
    cfem_mg["CodigoMunicipio"]
    .astype(str)
    .str.replace(
        r"\.0$",
        "",
        regex=True
    )
    .str.strip()
    .str.zfill(7)
)


# ============================================================
# 6. TRATAR ANO
# ============================================================

cfem_mg["Ano"] = pd.to_numeric(
    cfem_mg["Ano"],
    errors="coerce"
)

cfem_mg = cfem_mg[
    cfem_mg["Ano"].notna()
].copy()

cfem_mg["Ano"] = (
    cfem_mg["Ano"]
    .astype(int)
)


# ============================================================
# 7. TRATAR MUNICÍPIO
# ============================================================

cfem_mg["Município"] = (
    cfem_mg["Município"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ============================================================
# 8. TRATAR SUBSTÂNCIA
# ============================================================

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
# 9. ANOS DISPONÍVEIS
# ============================================================

anos = sorted(
    cfem_mg["Ano"]
    .unique()
    .tolist()
)

if not anos:
    raise ValueError(
        "Nenhum ano foi encontrado na base da ANM."
    )

ano_padrao = max(anos)

print("\nAnos encontrados:")
print(anos)


# ============================================================
# 10. TOTAL POR MUNICÍPIO / ANO
# ============================================================

print(
    "\nCalculando CFEM total por município..."
)

cfem_total = (
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
            "ValorRecolhido":
                "CFEM_Total"
        }
    )
)

cfem_total["CFEM_Total"] = (
    cfem_total["CFEM_Total"]
    .astype(float)
)


# ============================================================
# 11. TOTAL POR MUNICÍPIO / ANO / SUBSTÂNCIA
# ============================================================

print(
    "\nCalculando CFEM por substância..."
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
            "ValorRecolhido":
                "CFEM_Total"
        }
    )
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
# 12. LISTA DE SUBSTÂNCIAS
# ============================================================

todas_substancias = sorted(
    cfem_substancias[
        "Substância"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist(),
    key=lambda x: x.upper()
)

print(
    f"Substâncias encontradas: "
    f"{len(todas_substancias)}"
)


# ============================================================
# 13. PRINCIPAIS SUBSTÂNCIAS
# ============================================================

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

principais_substancias = (
    ranking_substancias
    .head(10)["Substância"]
    .tolist()
)

print("\nPrincipais substâncias:")

for numero, substancia in enumerate(
    principais_substancias,
    start=1
):
    print(
        f"{numero}. {substancia}"
    )


# ============================================================
# 14. GERAR dados_cfem.json
# ============================================================

print(
    f"\nGerando {ARQUIVO_DADOS}..."
)

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

        "substancias":
            todas_substancias,

        "principais_substancias":
            principais_substancias,

        "gerado_em":
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )
    },

    "totais":
        cfem_total.to_dict(
            orient="records"
        ),

    "substancias":
        cfem_substancias.to_dict(
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
    f"{ARQUIVO_DADOS} criado com sucesso."
)


# ============================================================
# 15. CARREGAR MUNICÍPIOS
# ============================================================

print(
    "\nCarregando municípios..."
)

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

print(
    f"Municípios carregados: "
    f"{len(municipios)}"
)


# ============================================================
# 16. PREPARAR ANO INICIAL
# ============================================================

dados_iniciais = cfem_total[
    cfem_total["Ano"].eq(
        ano_padrao
    )
][
    [
        "CodigoMunicipio",
        "CFEM_Total"
    ]
].copy()

geo_inicial = municipios.merge(
    dados_iniciais,
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
# 17. FUNÇÃO DE COR
# ============================================================

def cor_cfem(valor):

    valor = float(
        valor or 0
    )

    if valor <= 0:
        return "#eeeeee"

    if valor <= 10_000:
        return "#ffffcc"

    if valor <= 100_000:
        return "#ffeda0"

    if valor <= 1_000_000:
        return "#fed976"

    if valor <= 10_000_000:
        return "#feb24c"

    if valor <= 100_000_000:
        return "#f03b20"

    return "#bd0026"


# ============================================================
# 18. CRIAR MAPA
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

    control_scale=True,

    prefer_canvas=True
)


# ============================================================
# 19. CYCLOSM
# ============================================================

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


# ============================================================
# 20. ESRI WORLD TOPO
# ============================================================

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
# 21. CAMADA MUNICIPAL
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

).add_to(
    mapa_cfem
)


# ============================================================
# 22. NOMES JAVASCRIPT
# ============================================================

nome_camada_js = (
    camada_municipios.get_name()
)

nome_mapa_js = (
    mapa_cfem.get_name()
)


# ============================================================
# 23. LIMITES DE MINAS GERAIS
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
# 24. TÍTULO
# ============================================================

titulo_html = """
<div id="titulo-webgis">

    <div class="titulo-principal">
        Mapa de Arrecadação da CFEM — Minas Gerais
    </div>

    <div class="titulo-secundario">
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
# 25. DADOS PARA JAVASCRIPT
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
    .sort_values(
        "NM_MUN"
    )
    .to_dict(
        orient="records"
    ),

    ensure_ascii=False
)


# ============================================================
# 26. INTERFACE
#
# IMPORTANTE:
# NÃO USAR f-string NESTE BLOCO.
# ============================================================

interface_html = r"""
<style>

/* ==========================================================
   TÍTULO
   ========================================================== */

#titulo-webgis {
    position: fixed;
    top: 10px;
    left: 70px;
    z-index: 9998;

    background:
        rgba(255,255,255,0.96);

    border:
        1px solid #888;

    border-radius:
        7px;

    padding:
        9px 16px;

    box-shadow:
        0 2px 7px rgba(0,0,0,0.25);

    font-family:
        Arial,
        sans-serif;
}


#titulo-webgis .titulo-principal {
    font-size:
        19px;

    font-weight:
        bold;

    white-space:
        nowrap;
}


#titulo-webgis .titulo-secundario {
    font-size:
        12px;

    margin-top:
        4px;

    white-space:
        nowrap;
}


/* ==========================================================
   PAINEL
   ========================================================== */

#painel-cfem {

    position:
        fixed;

    top:
        95px;

    right:
        20px;

    width:
        350px;

    max-height:
        calc(100vh - 120px);

    overflow-y:
        auto;

    z-index:
        9999;

    background:
        rgba(255,255,255,0.97);

    border:
        1px solid #999;

    border-radius:
        8px;

    padding:
        14px;

    box-sizing:
        border-box;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.28);

    font-family:
        Arial,
        sans-serif;
}


#painel-cfem h3 {

    margin:
        0 0 12px 0;

    font-size:
        16px;
}


.rotulo-cfem {

    display:
        block;

    font-size:
        12px;

    font-weight:
        bold;

    margin:
        10px 0 5px 0;

    color:
        #444;
}


/* ==========================================================
   CAMPOS
   ========================================================== */

#filtro-ano,
#busca-substancia,
#busca-municipio {

    width:
        100%;

    padding:
        8px;

    border:
        1px solid #aaa;

    border-radius:
        5px;

    background:
        white;

    box-sizing:
        border-box;

    font-size:
        13px;
}


#busca-substancia:focus,
#busca-municipio:focus {

    outline:
        2px solid #777;

    outline-offset:
        1px;
}


/* ==========================================================
   RESULTADOS DAS BUSCAS
   ========================================================== */

#lista-substancias,
#lista-municipios {

    display:
        none;

    max-height:
        220px;

    overflow-y:
        auto;

    margin-top:
        3px;

    border:
        1px solid #bbb;

    border-radius:
        5px;

    background:
        white;

    box-shadow:
        0 2px 5px rgba(0,0,0,0.15);
}


.item-substancia,
.item-municipio {

    padding:
        8px 9px;

    font-size:
        12px;

    cursor:
        pointer;

    border-bottom:
        1px solid #eee;
}


.item-substancia:hover,
.item-municipio:hover {

    background:
        #eeeeee;
}


.item-principal {

    font-weight:
        bold;
}


.sem-resultado {

    padding:
        9px;

    font-size:
        11px;

    color:
        #777;
}


/* ==========================================================
   BOTÃO VOLTAR
   ========================================================== */

#botao-voltar-mg {

    width:
        100%;

    margin-top:
        8px;

    padding:
        8px;

    border:
        1px solid #999;

    border-radius:
        5px;

    background:
        #f5f5f5;

    box-sizing:
        border-box;

    font-size:
        11px;

    cursor:
        pointer;
}


#botao-voltar-mg:hover {

    background:
        #e9e9e9;
}


/* ==========================================================
   INDICADORES
   ========================================================== */

#indicadores-cfem {

    margin-top:
        13px;

    padding-top:
        10px;

    border-top:
        1px solid #ddd;
}


.indicadores-titulo {

    font-size:
        12px;

    font-weight:
        bold;

    color:
        #444;

    margin-bottom:
        7px;
}


.grade-indicadores {

    display:
        grid;

    grid-template-columns:
        1fr 1fr;

    gap:
        7px;
}


.cartao-indicador {

    border:
        1px solid #ddd;

    border-radius:
        6px;

    background:
        #fafafa;

    padding:
        8px;

    min-height:
        55px;

    box-sizing:
        border-box;
}


.cartao-indicador.total {

    grid-column:
        1 / -1;
}


.indicador-rotulo {

    font-size:
        10px;

    color:
        #666;

    margin-bottom:
        4px;
}


.indicador-valor {

    font-size:
        14px;

    font-weight:
        bold;

    line-height:
        1.2;

    word-break:
        break-word;
}


.indicador-detalhe {

    font-size:
        10px;

    color:
        #666;

    margin-top:
        3px;

    line-height:
        1.25;
}


/* ==========================================================
   ETAPA 7
   RANKING
   ========================================================== */

#ranking-cfem {

    margin-top:
        13px;

    padding-top:
        10px;

    border-top:
        1px solid #ddd;
}


.ranking-cabecalho {

    display:
        flex;

    align-items:
        center;

    justify-content:
        space-between;

    margin-bottom:
        7px;
}


.ranking-titulo {

    font-size:
        12px;

    font-weight:
        bold;

    color:
        #444;
}


.ranking-top {

    font-size:
        9px;

    color:
        #777;

    text-transform:
        uppercase;

    letter-spacing:
        0.3px;
}


#lista-ranking {

    border:
        1px solid #ddd;

    border-radius:
        6px;

    overflow:
        hidden;

    background:
        white;
}


.item-ranking {

    display:
        grid;

    grid-template-columns:
        28px 1fr auto;

    align-items:
        center;

    gap:
        6px;

    padding:
        7px 8px;

    border-bottom:
        1px solid #eee;

    cursor:
        pointer;

    transition:
        background 0.15s ease;
}


.item-ranking:last-child {

    border-bottom:
        none;
}


.item-ranking:hover {

    background:
        #f1f1f1;
}


.ranking-posicao {

    font-size:
        11px;

    font-weight:
        bold;

    color:
        #777;

    text-align:
        center;
}


.ranking-municipio {

    font-size:
        11px;

    font-weight:
        600;

    color:
        #333;

    overflow:
        hidden;

    text-overflow:
        ellipsis;

    white-space:
        nowrap;
}


.ranking-valor {

    font-size:
        10px;

    font-weight:
        bold;

    color:
        #333;

    white-space:
        nowrap;

    text-align:
        right;
}


.ranking-vazio {

    padding:
        10px;

    font-size:
        11px;

    color:
        #777;

    text-align:
        center;
}


/* ==========================================================
   STATUS
   ========================================================== */

#status-consulta {

    margin-top:
        12px;

    padding-top:
        9px;

    border-top:
        1px solid #ddd;

    font-size:
        11px;

    line-height:
        1.5;

    color:
        #555;
}


#carregando-cfem {

    display:
        none;

    margin-top:
        8px;

    font-size:
        11px;

    font-weight:
        bold;
}


/* ==========================================================
   LEGENDA
   ========================================================== */

#legenda-cfem {

    position:
        fixed;

    bottom:
        30px;

    left:
        30px;

    width:
        275px;

    z-index:
        9997;

    background:
        rgba(255,255,255,0.96);

    border:
        1px solid #888;

    border-radius:
        7px;

    padding:
        12px;

    box-sizing:
        border-box;

    box-shadow:
        0 2px 7px rgba(0,0,0,0.25);

    font-family:
        Arial,
        sans-serif;

    font-size:
        12px;
}


.legenda-titulo {

    font-size:
        14px;

    font-weight:
        bold;

    margin-bottom:
        8px;
}


.legenda-item {

    margin-bottom:
        4px;
}


.caixa-cor {

    display:
        inline-block;

    width:
        16px;

    height:
        16px;

    margin-right:
        6px;

    vertical-align:
        middle;

    border:
        1px solid #999;
}


.creditos-cfem {

    border-top:
        1px solid #bbb;

    margin-top:
        9px;

    padding-top:
        7px;

    font-size:
        10px;

    line-height:
        1.45;
}


.tooltip-cfem {

    font-family:
        Arial,
        sans-serif;

    font-size:
        12px;

    line-height:
        1.5;
}


/* ==========================================================
   RESPONSIVIDADE
   ========================================================== */

@media screen and (max-width: 768px) {

    #titulo-webgis {

        top:
            8px;

        left:
            50px;

        right:
            8px;

        padding:
            7px 9px;
    }


    #titulo-webgis .titulo-principal {

        font-size:
            14px;

        white-space:
            normal;
    }


    #titulo-webgis .titulo-secundario {

        display:
            none;
    }


    #painel-cfem {

        top:
            auto;

        bottom:
            10px;

        left:
            8px;

        right:
            8px;

        width:
            auto;

        max-height:
            52vh;

        padding:
            10px;
    }


    #painel-cfem h3 {

        font-size:
            14px;

        margin-bottom:
            5px;
    }


    .rotulo-cfem {

        margin:
            6px 0 4px 0;

        font-size:
            11px;
    }


    #filtro-ano,
    #busca-substancia,
    #busca-municipio {

        padding:
            7px;

        font-size:
            12px;
    }


    #lista-substancias,
    #lista-municipios {

        max-height:
            150px;
    }


    .indicador-valor {

        font-size:
            12px;
    }


    .item-ranking {

        grid-template-columns:
            24px 1fr auto;

        padding:
            6px;
    }


    .ranking-municipio {

        font-size:
            10px;
    }


    .ranking-valor {

        font-size:
            9px;
    }


    #legenda-cfem {

        top:
            65px;

        bottom:
            auto;

        left:
            8px;

        width:
            190px;

        padding:
            8px;

        font-size:
            10px;
    }


    .legenda-titulo {

        font-size:
            11px;
    }


    .caixa-cor {

        width:
            12px;

        height:
            12px;
    }


    .creditos-cfem {

        display:
            none;
    }


    .leaflet-control-layers {

        font-size:
            10px;
    }

}

</style>


<!-- ========================================================
     PAINEL
     ======================================================== -->

<div id="painel-cfem">

    <h3>
        Consulta CFEM
    </h3>


    <label
        class="rotulo-cfem"
        for="filtro-ano"
    >
        Ano
    </label>


    <select id="filtro-ano">
    </select>


    <label
        class="rotulo-cfem"
        for="busca-substancia"
    >
        Substância mineral
    </label>


    <input
        id="busca-substancia"
        type="text"
        value="Todas as substâncias"
        autocomplete="off"
        placeholder="Digite o nome da substância..."
    >


    <div id="lista-substancias">
    </div>


    <label
        class="rotulo-cfem"
        for="busca-municipio"
    >
        Município
    </label>


    <input
        id="busca-municipio"
        type="text"
        autocomplete="off"
        placeholder="Digite o nome do município..."
    >


    <div id="lista-municipios">
    </div>


    <button
        id="botao-voltar-mg"
        type="button"
    >
        Visualizar todo o estado
    </button>


    <!-- ====================================================
         INDICADORES
         ==================================================== -->

    <div id="indicadores-cfem">

        <div class="indicadores-titulo">
            Indicadores da consulta
        </div>


        <div class="grade-indicadores">


            <div class="cartao-indicador total">

                <div class="indicador-rotulo">
                    CFEM total
                </div>

                <div
                    class="indicador-valor"
                    id="indicador-total"
                >
                    R$ 0,00
                </div>

            </div>


            <div class="cartao-indicador">

                <div class="indicador-rotulo">
                    Municípios com arrecadação
                </div>

                <div
                    class="indicador-valor"
                    id="indicador-municipios"
                >
                    0
                </div>

            </div>


            <div class="cartao-indicador">

                <div class="indicador-rotulo">
                    Maior arrecadação municipal
                </div>

                <div
                    class="indicador-valor"
                    id="indicador-maior-valor"
                >
                    R$ 0,00
                </div>

                <div
                    class="indicador-detalhe"
                    id="indicador-maior-municipio"
                >
                    —
                </div>

            </div>


        </div>

    </div>


    <!-- ====================================================
         ETAPA 7 - RANKING
         ==================================================== -->

    <div id="ranking-cfem">

        <div class="ranking-cabecalho">

            <div class="ranking-titulo">
                Ranking municipal
            </div>

            <div class="ranking-top">
                Top 10
            </div>

        </div>


        <div id="lista-ranking">

            <div class="ranking-vazio">
                Carregando ranking...
            </div>

        </div>

    </div>


    <!-- ====================================================
         STATUS
         ==================================================== -->

    <div id="status-consulta">

        <b>
            Exibindo:
        </b>

        <span id="status-ano">
            __ANO_PADRAO__
        </span>

        ·

        <span id="status-substancia">
            Todas as substâncias
        </span>

    </div>


    <div id="carregando-cfem">
        Atualizando mapa...
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
            style="background:#eeeeee;"
        ></span>
        Sem arrecadação
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#ffffcc;"
        ></span>
        Até R$ 10 mil
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#ffeda0;"
        ></span>
        R$ 10 mil – R$ 100 mil
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#fed976;"
        ></span>
        R$ 100 mil – R$ 1 milhão
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#feb24c;"
        ></span>
        R$ 1 mi – R$ 10 milhões
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#f03b20;"
        ></span>
        R$ 10 mi – R$ 100 milhões
    </div>


    <div class="legenda-item">
        <span
            class="caixa-cor"
            style="background:#bd0026;"
        ></span>
        Acima de R$ 100 milhões
    </div>


    <div class="creditos-cfem">

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


<script>

document.addEventListener(
    "DOMContentLoaded",
    async function() {


        /* ==================================================
           CONFIGURAÇÕES
           ================================================== */

        const mapa =
            __MAPA_JS__;


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


        let substanciaSelecionada =
            "TODAS";


        let dadosCFEM =
            null;


        let camadaMunicipioSelecionado =
            null;


        /* ==================================================
           ELEMENTOS
           ================================================== */

        const filtroAno =
            document.getElementById(
                "filtro-ano"
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


        const statusAno =
            document.getElementById(
                "status-ano"
            );


        const statusSubstancia =
            document.getElementById(
                "status-substancia"
            );


        const carregando =
            document.getElementById(
                "carregando-cfem"
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


        /* ETAPA 7 */

        const listaRanking =
            document.getElementById(
                "lista-ranking"
            );


        /* ==================================================
           NORMALIZAR TEXTO
           ================================================== */

        function normalizar(texto) {

            return String(
                texto || ""
            )
            .normalize("NFD")
            .replace(
                /[\u0300-\u036f]/g,
                ""
            )
            .toLowerCase()
            .trim();

        }


        /* ==================================================
           MOEDA COMPLETA
           ================================================== */

        function moeda(valor) {

            return Number(
                valor || 0
            ).toLocaleString(
                "pt-BR",
                {

                    style:
                        "currency",

                    currency:
                        "BRL"

                }
            );

        }


        /* ==================================================
           MOEDA COMPACTA
           USADA NO RANKING
           ================================================== */

        function moedaCompacta(valor) {

            valor =
                Number(
                    valor || 0
                );


            if (
                valor >= 1000000000
            ) {

                return (
                    "R$ " +
                    (
                        valor /
                        1000000000
                    )
                    .toLocaleString(
                        "pt-BR",
                        {
                            maximumFractionDigits:
                                2
                        }
                    )
                    +
                    " bi"
                );

            }


            if (
                valor >= 1000000
            ) {

                return (
                    "R$ " +
                    (
                        valor /
                        1000000
                    )
                    .toLocaleString(
                        "pt-BR",
                        {
                            maximumFractionDigits:
                                2
                        }
                    )
                    +
                    " mi"
                );

            }


            if (
                valor >= 1000
            ) {

                return (
                    "R$ " +
                    (
                        valor /
                        1000
                    )
                    .toLocaleString(
                        "pt-BR",
                        {
                            maximumFractionDigits:
                                2
                        }
                    )
                    +
                    " mil"
                );

            }


            return moeda(
                valor
            );

        }


        /* ==================================================
           COR
           ================================================== */

        function corCFEM(valor) {

            valor =
                Number(
                    valor || 0
                );


            if (valor <= 0) {
                return "#eeeeee";
            }


            if (valor <= 10000) {
                return "#ffffcc";
            }


            if (valor <= 100000) {
                return "#ffeda0";
            }


            if (valor <= 1000000) {
                return "#fed976";
            }


            if (valor <= 10000000) {
                return "#feb24c";
            }


            if (valor <= 100000000) {
                return "#f03b20";
            }


            return "#bd0026";

        }


        /* ==================================================
           ESTILO NORMAL
           ================================================== */

        function aplicarEstiloNormal(
            layer
        ) {

            if (
                !layer.feature ||
                !layer.feature.properties
            ) {

                return;

            }


            const valor =
                Number(
                    layer.feature
                    .properties
                    .CFEM_Total || 0
                );


            layer.setStyle(
                {

                    fillColor:
                        corCFEM(
                            valor
                        ),

                    color:
                        "#555555",

                    weight:
                        0.6,

                    fillOpacity:
                        0.80

                }
            );

        }


        /* ==================================================
           DESTAQUE
           ================================================== */

        function aplicarDestaqueMunicipio() {

            if (
                !camadaMunicipioSelecionado
            ) {

                return;

            }


            camadaMunicipioSelecionado
            .setStyle(
                {

                    color:
                        "#000000",

                    weight:
                        4,

                    fillOpacity:
                        0.95

                }
            );


            if (
                camadaMunicipioSelecionado
                .bringToFront
            ) {

                camadaMunicipioSelecionado
                .bringToFront();

            }

        }


        /* ==================================================
           ANOS
           ================================================== */

        anos
        .slice()
        .sort(
            function(a, b) {

                return b - a;

            }
        )
        .forEach(
            function(ano) {

                const option =
                    document.createElement(
                        "option"
                    );


                option.value =
                    ano;


                option.textContent =
                    ano;


                if (
                    Number(ano) ===
                    Number(anoPadrao)
                ) {

                    option.selected =
                        true;

                }


                filtroAno.appendChild(
                    option
                );

            }
        );


        /* ==================================================
           SUBSTÂNCIAS
           ================================================== */

        function mostrarListaSubstancias(
            textoBusca
        ) {

            const busca =
                normalizar(
                    textoBusca || ""
                );


            listaSubstancias.innerHTML =
                "";


            const itemTodas =
                document.createElement(
                    "div"
                );


            itemTodas.className =
                "item-substancia item-principal";


            itemTodas.textContent =
                "Todas as substâncias";


            itemTodas.addEventListener(
                "click",
                function() {

                    substanciaSelecionada =
                        "TODAS";


                    buscaSubstancia.value =
                        "Todas as substâncias";


                    listaSubstancias.style.display =
                        "none";


                    atualizarMapa();

                }
            );


            listaSubstancias.appendChild(
                itemTodas
            );


            const termos =
                busca
                .split(/\s+/)
                .filter(Boolean);


            let resultados =
                substancias.filter(
                    function(substancia) {

                        if (!busca) {
                            return true;
                        }


                        const nome =
                            normalizar(
                                substancia
                            );


                        return termos.every(
                            function(termo) {

                                return nome.includes(
                                    termo
                                );

                            }
                        );

                    }
                );


            if (!busca) {

                resultados.sort(
                    function(a, b) {

                        const posicaoA =
                            principais.indexOf(a);


                        const posicaoB =
                            principais.indexOf(b);


                        if (
                            posicaoA !== -1 &&
                            posicaoB === -1
                        ) {
                            return -1;
                        }


                        if (
                            posicaoA === -1 &&
                            posicaoB !== -1
                        ) {
                            return 1;
                        }


                        if (
                            posicaoA !== -1 &&
                            posicaoB !== -1
                        ) {

                            return (
                                posicaoA -
                                posicaoB
                            );

                        }


                        return a.localeCompare(
                            b,
                            "pt-BR"
                        );

                    }
                );

            }


            if (
                resultados.length === 0
            ) {

                const vazio =
                    document.createElement(
                        "div"
                    );


                vazio.className =
                    "sem-resultado";


                vazio.textContent =
                    "Nenhuma substância encontrada.";


                listaSubstancias.appendChild(
                    vazio
                );

            }


            resultados
            .slice(
                0,
                60
            )
            .forEach(
                function(substancia) {

                    const item =
                        document.createElement(
                            "div"
                        );


                    item.className =
                        "item-substancia";


                    if (
                        principais.includes(
                            substancia
                        )
                    ) {

                        item.classList.add(
                            "item-principal"
                        );

                    }


                    item.textContent =
                        substancia;


                    item.addEventListener(
                        "click",
                        function() {

                            substanciaSelecionada =
                                substancia;


                            buscaSubstancia.value =
                                substancia;


                            listaSubstancias.style.display =
                                "none";


                            atualizarMapa();

                        }
                    );


                    listaSubstancias.appendChild(
                        item
                    );

                }
            );


            listaSubstancias.style.display =
                "block";

        }


        buscaSubstancia.addEventListener(
            "focus",
            function() {

                if (
                    substanciaSelecionada ===
                    "TODAS"
                ) {

                    buscaSubstancia.value =
                        "";

                }

                else {

                    buscaSubstancia.select();

                }


                mostrarListaSubstancias(
                    ""
                );

            }
        );


        buscaSubstancia.addEventListener(
            "input",
            function() {

                mostrarListaSubstancias(
                    buscaSubstancia.value
                );

            }
        );


        /* ==================================================
           MUNICÍPIOS
           ================================================== */

        function mostrarListaMunicipios(
            textoBusca
        ) {

            const busca =
                normalizar(
                    textoBusca || ""
                );


            listaMunicipios.innerHTML =
                "";


            if (!busca) {

                listaMunicipios.style.display =
                    "none";

                return;

            }


            const termos =
                busca
                .split(/\s+/)
                .filter(Boolean);


            const resultados =
                municipiosBusca.filter(
                    function(municipio) {

                        const nome =
                            normalizar(
                                municipio.NM_MUN
                            );


                        return termos.every(
                            function(termo) {

                                return nome.includes(
                                    termo
                                );

                            }
                        );

                    }
                );


            if (
                resultados.length === 0
            ) {

                const vazio =
                    document.createElement(
                        "div"
                    );


                vazio.className =
                    "sem-resultado";


                vazio.textContent =
                    "Nenhum município encontrado.";


                listaMunicipios.appendChild(
                    vazio
                );

            }


            resultados
            .slice(
                0,
                30
            )
            .forEach(
                function(municipio) {

                    const item =
                        document.createElement(
                            "div"
                        );


                    item.className =
                        "item-municipio";


                    item.textContent =
                        municipio.NM_MUN;


                    item.addEventListener(
                        "click",
                        function() {

                            selecionarMunicipio(
                                municipio.CD_MUN,
                                municipio.NM_MUN
                            );

                        }
                    );


                    listaMunicipios.appendChild(
                        item
                    );

                }
            );


            listaMunicipios.style.display =
                "block";

        }


        /* ==================================================
           SELECIONAR MUNICÍPIO
           Usado pela busca E pelo ranking.
           ================================================== */

        function selecionarMunicipio(
            codigo,
            nome
        ) {

            buscaMunicipio.value =
                nome;


            listaMunicipios.style.display =
                "none";


            camadaMunicipioSelecionado =
                null;


            camadaMunicipios.eachLayer(
                function(layer) {

                    if (
                        !layer.feature ||
                        !layer.feature.properties
                    ) {

                        return;

                    }


                    aplicarEstiloNormal(
                        layer
                    );


                    const codigoLayer =
                        String(
                            layer.feature
                            .properties
                            .CD_MUN
                        );


                    if (
                        codigoLayer ===
                        String(codigo)
                    ) {

                        camadaMunicipioSelecionado =
                            layer;

                    }

                }
            );


            if (
                !camadaMunicipioSelecionado
            ) {

                return;

            }


            aplicarDestaqueMunicipio();


            const limites =
                camadaMunicipioSelecionado
                .getBounds();


            if (
                limites &&
                limites.isValid()
            ) {

                mapa.fitBounds(
                    limites,
                    {

                        padding:
                            [30, 30],

                        maxZoom:
                            11

                    }
                );

            }


            if (
                camadaMunicipioSelecionado
                .getTooltip()
            ) {

                camadaMunicipioSelecionado
                .openTooltip();

            }

        }


        buscaMunicipio.addEventListener(
            "input",
            function() {

                mostrarListaMunicipios(
                    buscaMunicipio.value
                );

            }
        );


        buscaMunicipio.addEventListener(
            "focus",
            function() {

                if (
                    buscaMunicipio.value
                ) {

                    buscaMunicipio.select();


                    mostrarListaMunicipios(
                        buscaMunicipio.value
                    );

                }

            }
        );


        /* ==================================================
           FECHAR LISTAS
           ================================================== */

        document.addEventListener(
            "click",
            function(event) {

                if (
                    !listaSubstancias.contains(
                        event.target
                    )
                    &&
                    event.target !==
                    buscaSubstancia
                ) {

                    listaSubstancias.style.display =
                        "none";

                }


                if (
                    !listaMunicipios.contains(
                        event.target
                    )
                    &&
                    event.target !==
                    buscaMunicipio
                ) {

                    listaMunicipios.style.display =
                        "none";

                }

            }
        );


        /* ==================================================
           VOLTAR PARA MG
           ================================================== */

        botaoVoltarMG.addEventListener(
            "click",
            function() {

                buscaMunicipio.value =
                    "";


                listaMunicipios.style.display =
                    "none";


                camadaMunicipioSelecionado =
                    null;


                camadaMunicipios.eachLayer(
                    function(layer) {

                        aplicarEstiloNormal(
                            layer
                        );

                    }
                );


                mapa.fitBounds(
                    limitesMG
                );

            }
        );


        /* ==================================================
           CARREGAR JSON
           ================================================== */

        try {

            carregando.textContent =
                "Carregando dados...";


            carregando.style.display =
                "block";


            const resposta =
                await fetch(
                    "dados_cfem.json?v=" +
                    Date.now()
                );


            if (
                !resposta.ok
            ) {

                throw new Error(
                    "Erro HTTP " +
                    resposta.status
                );

            }


            dadosCFEM =
                await resposta.json();


            carregando.style.display =
                "none";

        }

        catch (erro) {

            console.error(
                "Erro ao carregar dados_cfem.json:",
                erro
            );


            carregando.textContent =
                "Erro ao carregar os dados da CFEM.";


            carregando.style.display =
                "block";


            return;

        }


        /* ==================================================
           INDICADORES
           ================================================== */

        function atualizarIndicadores(
            valoresMunicipios
        ) {

            let total =
                0;


            let quantidadeMunicipios =
                0;


            let maiorValor =
                0;


            let maiorCodigo =
                null;


            valoresMunicipios.forEach(
                function(valor, codigo) {

                    const numero =
                        Number(
                            valor || 0
                        );


                    total +=
                        numero;


                    if (
                        numero > 0
                    ) {

                        quantidadeMunicipios +=
                            1;


                        if (
                            numero >
                            maiorValor
                        ) {

                            maiorValor =
                                numero;


                            maiorCodigo =
                                String(
                                    codigo
                                );

                        }

                    }

                }
            );


            let maiorMunicipio =
                "—";


            if (
                maiorCodigo !== null
            ) {

                const encontrado =
                    municipiosBusca.find(
                        function(municipio) {

                            return (
                                String(
                                    municipio.CD_MUN
                                )
                                ===
                                maiorCodigo
                            );

                        }
                    );


                if (
                    encontrado
                ) {

                    maiorMunicipio =
                        encontrado.NM_MUN;

                }

            }


            indicadorTotal.textContent =
                moeda(
                    total
                );


            indicadorMunicipios.textContent =
                quantidadeMunicipios
                .toLocaleString(
                    "pt-BR"
                );


            indicadorMaiorValor.textContent =
                moeda(
                    maiorValor
                );


            indicadorMaiorMunicipio.textContent =
                maiorMunicipio;

        }


        /* ==================================================
           ETAPA 7
           ATUALIZAR RANKING MUNICIPAL
           ================================================== */

        function atualizarRanking(
            valoresMunicipios
        ) {

            listaRanking.innerHTML =
                "";


            const ranking =
                [];


            /* ----------------------------------------------
               Transformar Map em lista
               ---------------------------------------------- */

            valoresMunicipios.forEach(
                function(valor, codigo) {

                    const numero =
                        Number(
                            valor || 0
                        );


                    if (
                        numero <= 0
                    ) {

                        return;

                    }


                    const municipio =
                        municipiosBusca.find(
                            function(item) {

                                return (
                                    String(
                                        item.CD_MUN
                                    )
                                    ===
                                    String(
                                        codigo
                                    )
                                );

                            }
                        );


                    if (
                        !municipio
                    ) {

                        return;

                    }


                    ranking.push(
                        {

                            codigo:
                                String(
                                    codigo
                                ),

                            nome:
                                municipio.NM_MUN,

                            valor:
                                numero

                        }
                    );

                }
            );


            /* ----------------------------------------------
               Ordenar do maior para o menor
               ---------------------------------------------- */

            ranking.sort(
                function(a, b) {

                    return (
                        b.valor -
                        a.valor
                    );

                }
            );


            /* ----------------------------------------------
               Sem arrecadação
               ---------------------------------------------- */

            if (
                ranking.length === 0
            ) {

                const vazio =
                    document.createElement(
                        "div"
                    );


                vazio.className =
                    "ranking-vazio";


                vazio.textContent =
                    "Nenhum município com arrecadação "
                    + "para esta consulta.";


                listaRanking.appendChild(
                    vazio
                );


                return;

            }


            /* ----------------------------------------------
               Top 10
               ---------------------------------------------- */

            ranking
            .slice(
                0,
                10
            )
            .forEach(
                function(item, indice) {

                    const linha =
                        document.createElement(
                            "div"
                        );


                    linha.className =
                        "item-ranking";


                    linha.title =
                        "Clique para localizar "
                        + item.nome
                        + " no mapa";


                    /* POSIÇÃO */

                    const posicao =
                        document.createElement(
                            "div"
                        );


                    posicao.className =
                        "ranking-posicao";


                    posicao.textContent =
                        (indice + 1) + "º";


                    /* MUNICÍPIO */

                    const municipio =
                        document.createElement(
                            "div"
                        );


                    municipio.className =
                        "ranking-municipio";


                    municipio.textContent =
                        item.nome;


                    /* VALOR */

                    const valor =
                        document.createElement(
                            "div"
                        );


                    valor.className =
                        "ranking-valor";


                    valor.textContent =
                        moedaCompacta(
                            item.valor
                        );


                    /* CLIQUE */

                    linha.addEventListener(
                        "click",
                        function() {

                            selecionarMunicipio(
                                item.codigo,
                                item.nome
                            );

                        }
                    );


                    linha.appendChild(
                        posicao
                    );


                    linha.appendChild(
                        municipio
                    );


                    linha.appendChild(
                        valor
                    );


                    listaRanking.appendChild(
                        linha
                    );

                }
            );

        }


        /* ==================================================
           ATUALIZAR MAPA
           ================================================== */

        function atualizarMapa() {

            if (
                !dadosCFEM
            ) {

                return;

            }


            carregando.textContent =
                "Atualizando mapa...";


            carregando.style.display =
                "block";


            const ano =
                Number(
                    filtroAno.value
                );


            const valoresMunicipios =
                new Map();


            /* ----------------------------------------------
               TODAS AS SUBSTÂNCIAS
               ---------------------------------------------- */

            if (
                substanciaSelecionada ===
                "TODAS"
            ) {

                dadosCFEM.totais
                .forEach(
                    function(item) {

                        if (
                            Number(
                                item.Ano
                            ) ===
                            ano
                        ) {

                            valoresMunicipios.set(
                                String(
                                    item.CodigoMunicipio
                                ),

                                Number(
                                    item.CFEM_Total
                                )
                            );

                        }

                    }
                );

            }


            /* ----------------------------------------------
               SUBSTÂNCIA ESPECÍFICA
               ---------------------------------------------- */

            else {

                dadosCFEM.substancias
                .forEach(
                    function(item) {

                        if (
                            Number(
                                item.Ano
                            ) ===
                            ano
                            &&
                            item["Substância"] ===
                            substanciaSelecionada
                        ) {

                            valoresMunicipios.set(
                                String(
                                    item.CodigoMunicipio
                                ),

                                Number(
                                    item.CFEM_Total
                                )
                            );

                        }

                    }
                );

            }


            /* ----------------------------------------------
               POLÍGONOS
               ---------------------------------------------- */

            camadaMunicipios.eachLayer(
                function(layer) {

                    if (
                        !layer.feature ||
                        !layer.feature.properties
                    ) {

                        return;

                    }


                    const props =
                        layer.feature.properties;


                    const codigo =
                        String(
                            props.CD_MUN
                        );


                    const valor =
                        valoresMunicipios.get(
                            codigo
                        ) || 0;


                    props.CFEM_Total =
                        valor;


                    props.Ano =
                        ano;


                    aplicarEstiloNormal(
                        layer
                    );


                    let substanciaTexto =
                        substanciaSelecionada;


                    if (
                        substanciaSelecionada ===
                        "TODAS"
                    ) {

                        substanciaTexto =
                            "Todas as substâncias";

                    }


                    const conteudo =
                        '<div class="tooltip-cfem">' +

                        '<b>Município:</b> ' +
                        props.NM_MUN +

                        '<br>' +

                        '<b>Ano:</b> ' +
                        ano +

                        '<br>' +

                        '<b>Substância:</b> ' +
                        substanciaTexto +

                        '<br>' +

                        '<b>CFEM:</b> ' +
                        moeda(
                            valor
                        ) +

                        '</div>';


                    if (
                        layer.getTooltip()
                    ) {

                        layer.setTooltipContent(
                            conteudo
                        );

                    }

                    else {

                        layer.bindTooltip(
                            conteudo,
                            {

                                sticky:
                                    true

                            }
                        );

                    }

                }
            );


            /* ----------------------------------------------
               INDICADORES
               ---------------------------------------------- */

            atualizarIndicadores(
                valoresMunicipios
            );


            /* ----------------------------------------------
               ETAPA 7 - RANKING
               ---------------------------------------------- */

            atualizarRanking(
                valoresMunicipios
            );


            /* ----------------------------------------------
               MANTER MUNICÍPIO DESTACADO
               ---------------------------------------------- */

            aplicarDestaqueMunicipio();


            /* ----------------------------------------------
               STATUS
               ---------------------------------------------- */

            statusAno.textContent =
                ano;


            if (
                substanciaSelecionada ===
                "TODAS"
            ) {

                statusSubstancia.textContent =
                    "Todas as substâncias";

            }

            else {

                statusSubstancia.textContent =
                    substanciaSelecionada;

            }


            carregando.style.display =
                "none";

        }


        /* ==================================================
           ALTERAR ANO
           ================================================== */

        filtroAno.addEventListener(
            "change",
            function() {

                atualizarMapa();

            }
        );


        /* ==================================================
           PRIMEIRA ATUALIZAÇÃO
           ================================================== */

        atualizarMapa();

    }
);

</script>
"""


# ============================================================
# 27. SUBSTITUIR MARCADORES
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
    str(
        int(
            ano_padrao
        )
    )
)


# ============================================================
# 28. ADICIONAR INTERFACE
# ============================================================

mapa_cfem.get_root().html.add_child(
    folium.Element(
        interface_html
    )
)


# ============================================================
# 29. CONTROLE DE MAPAS BASE
# ============================================================

folium.LayerControl(
    collapsed=True
).add_to(
    mapa_cfem
)


# ============================================================
# 30. ENQUADRAR MINAS GERAIS
# ============================================================

mapa_cfem.fit_bounds(
    limites_mg
)


# ============================================================
# 31. SALVAR MAPA
# ============================================================

print(
    "\nSalvando mapa..."
)

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 32. FINALIZAÇÃO
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
    "WEBGIS ATUALIZADO COM SUCESSO"
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
    f"Quantidade de municípios: "
    f"{len(municipios)}"
)

print(
    f"Quantidade de substâncias: "
    f"{len(todas_substancias)}"
)

print(
    "=" * 60
)
