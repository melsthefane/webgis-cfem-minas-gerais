import pandas as pd
import geopandas as gpd
import folium
import requests
import json

from io import BytesIO
from datetime import datetime


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
# 5. TRATAR CÓDIGO DO MUNICÍPIO
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
# 9. IDENTIFICAR ANOS
# ============================================================

anos = sorted(
    cfem_mg["Ano"]
    .unique()
    .tolist()
)

if not anos:
    raise ValueError(
        "Nenhum ano foi encontrado nos dados da ANM."
    )

ano_padrao = max(anos)

print("\nAnos encontrados:")
print(anos)


# ============================================================
# 10. CFEM TOTAL POR MUNICÍPIO E ANO
# ============================================================

print(
    "\nCalculando totais por município e ano..."
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
# 11. CFEM POR MUNICÍPIO / ANO / SUBSTÂNCIA
# ============================================================

print(
    "\nCalculando arrecadação por substância..."
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
# 12. TODAS AS SUBSTÂNCIAS
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

print(
    "\nPrincipais substâncias:"
)

for posicao, substancia in enumerate(
    principais_substancias,
    start=1
):
    print(
        f"{posicao}. {substancia}"
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

        "fonte_cfem":
            "Agência Nacional de Mineração — ANM",

        "fonte_malha":
            "Instituto Brasileiro de Geografia "
            "e Estatística — IBGE",

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
) as arquivo_json:

    json.dump(
        dados_webgis,
        arquivo_json,
        ensure_ascii=False,
        separators=(",", ":")
    )

print(
    f"{ARQUIVO_DADOS} criado com sucesso."
)


# ============================================================
# 15. CARREGAR MUNICÍPIOS DE MINAS GERAIS
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
# 16. DADOS DO ANO INICIAL
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

geo_inicial["Ano"] = int(
    ano_padrao
)


# ============================================================
# 17. FUNÇÃO DE CORES
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
# 19. MAPAS BASE
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
# 20. UMA ÚNICA CAMADA MUNICIPAL
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
    },

    highlight_function=lambda feature: {

        "weight":
            3,

        "color":
            "#111111",

        "fillOpacity":
            0.92
    }
).add_to(
    mapa_cfem
)


nome_camada_js = (
    camada_municipios.get_name()
)


# ============================================================
# 21. TÍTULO
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
# 22. PREPARAR DADOS PARA JAVASCRIPT
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


# ============================================================
# 23. INTERFACE HTML + CSS + JAVASCRIPT
# ============================================================

interface_html = f"""
<style>

/* ==========================================================
   TÍTULO
   ========================================================== */

#titulo-webgis {{

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
}}


#titulo-webgis .titulo-principal {{

    font-size:
        19px;

    font-weight:
        bold;

    white-space:
        nowrap;
}}


#titulo-webgis .titulo-secundario {{

    font-size:
        12px;

    margin-top:
        4px;

    white-space:
        nowrap;
}}


/* ==========================================================
   PAINEL DE CONSULTA
   ========================================================== */

#painel-cfem {{

    position:
        fixed;

    top:
        105px;

    right:
        20px;

    width:
        310px;

    max-height:
        calc(100vh - 135px);

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
}}


#painel-cfem h3 {{

    margin:
        0 0 12px 0;

    font-size:
        16px;
}}


.rotulo-cfem {{

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
}}


/* ==========================================================
   ANO
   ========================================================== */

#filtro-ano {{

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
}}


/* ==========================================================
   BUSCA DE SUBSTÂNCIA
   ========================================================== */

#busca-substancia {{

    width:
        100%;

    padding:
        8px;

    border:
        1px solid #aaa;

    border-radius:
        5px;

    box-sizing:
        border-box;

    font-size:
        13px;

    background:
        white;
}}


#busca-substancia:focus {{

    outline:
        2px solid #777;

    outline-offset:
        1px;
}}


#lista-substancias {{

    display:
        none;

    max-height:
        230px;

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
}}


.item-substancia {{

    padding:
        8px 9px;

    font-size:
        12px;

    cursor:
        pointer;

    border-bottom:
        1px solid #eee;
}}


.item-substancia:last-child {{

    border-bottom:
        none;
}}


.item-substancia:hover {{

    background:
        #eeeeee;
}}


.item-principal {{

    font-weight:
        bold;
}}


.sem-resultado {{

    padding:
        9px;

    font-size:
        11px;

    color:
        #777;
}}


/* ==========================================================
   STATUS
   ========================================================== */

#status-consulta {{

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
}}


#carregando-cfem {{

    display:
        none;

    margin-top:
        8px;

    font-size:
        11px;

    font-weight:
        bold;
}}


/* ==========================================================
   LEGENDA
   ========================================================== */

#legenda-cfem {{

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
}}


.legenda-titulo {{

    font-size:
        14px;

    font-weight:
        bold;

    margin-bottom:
        8px;
}}


.legenda-item {{

    margin-bottom:
        4px;
}}


.caixa-cor {{

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
}}


.creditos-cfem {{

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
}}


/* ==========================================================
   TOOLTIP
   ========================================================== */

.tooltip-cfem {{

    font-family:
        Arial,
        sans-serif;

    font-size:
        12px;

    line-height:
        1.5;
}}


/* ==========================================================
   RESPONSIVIDADE
   ========================================================== */

@media screen and (max-width: 768px) {{

    #titulo-webgis {{

        top:
            8px;

        left:
            50px;

        right:
            8px;

        padding:
            7px 9px;
    }}


    #titulo-webgis .titulo-principal {{

        font-size:
            14px;

        white-space:
            normal;
    }}


    #titulo-webgis .titulo-secundario {{

        display:
            none;
    }}


    #painel-cfem {{

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
            38vh;

        padding:
            10px;
    }}


    #painel-cfem h3 {{

        font-size:
            14px;

        margin-bottom:
            5px;
    }}


    .rotulo-cfem {{

        margin:
            6px 0 4px 0;

        font-size:
            11px;
    }}


    #filtro-ano,
    #busca-substancia {{

        padding:
            7px;

        font-size:
            12px;
    }}


    #lista-substancias {{

        max-height:
            150px;
    }}


    #legenda-cfem {{

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
    }}


    .legenda-titulo {{

        font-size:
            11px;
    }}


    .caixa-cor {{

        width:
            12px;

        height:
            12px;
    }}


    .creditos-cfem {{

        display:
            none;
    }}


    .leaflet-control-layers {{

        font-size:
            10px;
    }}

}

</style>


<!-- ========================================================
     PAINEL DE CONSULTA
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


    <select
        id="filtro-ano"
    >
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


    <div
        id="lista-substancias"
    >
    </div>


    <div id="status-consulta">

        <b>
            Exibindo:
        </b>

        <span id="status-ano">
            {ano_padrao}
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
    async function() {{

        /* ==================================================
           REFERÊNCIAS
           ================================================== */

        const camadaMunicipios =
            {nome_camada_js};


        const anos =
            {anos_json};


        const substancias =
            {substancias_json};


        const principais =
            {principais_json};


        const anoPadrao =
            {int(ano_padrao)};


        let substanciaSelecionada =
            "TODAS";


        let dadosCFEM =
            null;


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


        /* ==================================================
           NORMALIZAR TEXTO
           Ignora acentos e maiúsculas/minúsculas
           ================================================== */

        function normalizar(texto) {{

            return String(
                texto || ""
            )
            .normalize("NFD")
            .replace(
                /[\\u0300-\\u036f]/g,
                ""
            )
            .toLowerCase()
            .trim();

        }}


        /* ==================================================
           FORMATAÇÃO MONETÁRIA
           ================================================== */

        function moeda(valor) {{

            return Number(
                valor || 0
            ).toLocaleString(
                "pt-BR",
                {{
                    style:
                        "currency",

                    currency:
                        "BRL"
                }}
            );

        }}


        /* ==================================================
           CORES
           ================================================== */

        function corCFEM(valor) {{

            valor =
                Number(
                    valor || 0
                );


            if (
                valor <= 0
            )
                return "#eeeeee";


            if (
                valor <= 10000
            )
                return "#ffffcc";


            if (
                valor <= 100000
            )
                return "#ffeda0";


            if (
                valor <= 1000000
            )
                return "#fed976";


            if (
                valor <= 10000000
            )
                return "#feb24c";


            if (
                valor <= 100000000
            )
                return "#f03b20";


            return "#bd0026";

        }}


        /* ==================================================
           PREENCHER ANOS
           ================================================== */

        anos
        .slice()
        .sort(
            function(a, b) {{
                return b - a;
            }}
        )
        .forEach(
            function(ano) {{

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
                ) {{

                    option.selected =
                        true;

                }}


                filtroAno.appendChild(
                    option
                );

            }}
        );


        /* ==================================================
           RESULTADOS DA BUSCA DE SUBSTÂNCIA
           ================================================== */

        function mostrarLista(
            textoBusca = ""
        ) {{

            const busca =
                normalizar(
                    textoBusca
                );


            listaSubstancias.innerHTML =
                "";


            /* ----------------------------------------------
               TODAS AS SUBSTÂNCIAS
               ---------------------------------------------- */

            const itemTodas =
                document.createElement(
                    "div"
                );


            itemTodas.className =
                "item-substancia item-principal";


            itemTodas.textContent =
                "Todas as substâncias";


            itemTodas.onclick =
                function() {{

                    substanciaSelecionada =
                        "TODAS";


                    buscaSubstancia.value =
                        "Todas as substâncias";


                    listaSubstancias.style.display =
                        "none";


                    atualizarMapa();

                }};


            listaSubstancias.appendChild(
                itemTodas
            );


            /* ----------------------------------------------
               FILTRAR SUBSTÂNCIAS
               ---------------------------------------------- */

            let resultados =
                substancias.filter(
                    function(substancia) {{

                        if (!busca) {{

                            return true;

                        }}


                        return normalizar(
                            substancia
                        ).includes(
                            busca
                        );

                    }}
                );


            /* ----------------------------------------------
               PRINCIPAIS PRIMEIRO
               ---------------------------------------------- */

            if (!busca) {{

                resultados.sort(
                    function(a, b) {{

                        const pa =
                            principais.indexOf(
                                a
                            );


                        const pb =
                            principais.indexOf(
                                b
                            );


                        if (
                            pa !== -1 &&
                            pb === -1
                        ) {{

                            return -1;

                        }}


                        if (
                            pa === -1 &&
                            pb !== -1
                        ) {{

                            return 1;

                        }}


                        if (
                            pa !== -1 &&
                            pb !== -1
                        ) {{

                            return pa - pb;

                        }}


                        return a.localeCompare(
                            b,
                            "pt-BR"
                        );

                    }}
                );

            }}


            /* ----------------------------------------------
               NENHUM RESULTADO
               ---------------------------------------------- */

            if (
                resultados.length === 0
            ) {{

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

            }}


            /* ----------------------------------------------
               MOSTRAR ATÉ 60 RESULTADOS
               ---------------------------------------------- */

            resultados
            .slice(
                0,
                60
            )
            .forEach(
                function(substancia) {{

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
                    ) {{

                        item.classList.add(
                            "item-principal"
                        );

                    }}


                    item.textContent =
                        substancia;


                    item.onclick =
                        function() {{

                            substanciaSelecionada =
                                substancia;


                            buscaSubstancia.value =
                                substancia;


                            listaSubstancias.style.display =
                                "none";


                            atualizarMapa();

                        }};


                    listaSubstancias.appendChild(
                        item
                    );

                }}
            );


            listaSubstancias.style.display =
                "block";

        }}


        /* ==================================================
           FOCO NA BUSCA
           ================================================== */

        buscaSubstancia.addEventListener(
            "focus",
            function() {{

                if (
                    substanciaSelecionada ===
                    "TODAS"
                ) {{

                    buscaSubstancia.value =
                        "";

                }}


                mostrarLista(
                    buscaSubstancia.value
                );

            }}
        );


        /* ==================================================
           DIGITAÇÃO
           ================================================== */

        buscaSubstancia.addEventListener(
            "input",
            function() {{

                mostrarLista(
                    buscaSubstancia.value
                );

            }}
        );


        /* ==================================================
           FECHAR LISTA AO CLICAR FORA
           ================================================== */

        document.addEventListener(
            "click",
            function(event) {{

                if (
                    !listaSubstancias.contains(
                        event.target
                    )
                    &&
                    event.target !==
                        buscaSubstancia
                ) {{

                    listaSubstancias.style.display =
                        "none";

                }}

            }}
        );


        /* ==================================================
           CARREGAR dados_cfem.json
           ================================================== */

        try {{

            carregando.style.display =
                "block";


            const resposta =
                await fetch(
                    "dados_cfem.json?v=" +
                    Date.now()
                );


            if (
                !resposta.ok
            ) {{

                throw new Error(
                    "Não foi possível carregar dados_cfem.json"
                );

            }}


            dadosCFEM =
                await resposta.json();


            carregando.style.display =
                "none";

        }}

        catch (erro) {{

            console.error(
                erro
            );


            carregando.textContent =
                "Erro ao carregar os dados da CFEM.";


            carregando.style.display =
                "block";


            return;

        }}


        /* ==================================================
           ATUALIZAR MAPA
           ================================================== */

        function atualizarMapa() {{

            if (
                !dadosCFEM
            ) {{

                return;

            }}


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
            ) {{

                dadosCFEM.totais
                .filter(
                    function(item) {{

                        return Number(
                            item.Ano
                        ) === ano;

                    }}
                )
                .forEach(
                    function(item) {{

                        valoresMunicipios.set(
                            String(
                                item.CodigoMunicipio
                            ),

                            Number(
                                item.CFEM_Total
                            )
                        );

                    }}
                );

            }}


            /* ----------------------------------------------
               SUBSTÂNCIA ESPECÍFICA
               ---------------------------------------------- */

            else {{

                dadosCFEM.substancias
                .filter(
                    function(item) {{

                        return (
                            Number(
                                item.Ano
                            ) === ano
                            &&
                            item["Substância"] ===
                                substanciaSelecionada
                        );

                    }}
                )
                .forEach(
                    function(item) {{

                        valoresMunicipios.set(
                            String(
                                item.CodigoMunicipio
                            ),

                            Number(
                                item.CFEM_Total
                            )
                        );

                    }}
                );

            }}


            /* ----------------------------------------------
               RECOLORIR MUNICÍPIOS
               ---------------------------------------------- */

            camadaMunicipios.eachLayer(
                function(layer) {{

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


                    layer.setStyle({{

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

                    }});


                    /* --------------------------------------
                       TEXTO DA SUBSTÂNCIA
                       -------------------------------------- */

                    const substanciaTexto =

                        substanciaSelecionada ===
                        "TODAS"

                        ?

                        "Todas as substâncias"

                        :

                        substanciaSelecionada;


                    /* --------------------------------------
                       TOOLTIP
                       -------------------------------------- */

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


                    layer.bindTooltip(
                        conteudo,
                        {{
                            sticky:
                                true
                        }}
                    );

                }}
            );


            /* ----------------------------------------------
               ATUALIZAR STATUS
               ---------------------------------------------- */

            statusAno.textContent =
                ano;


            statusSubstancia.textContent =

                substanciaSelecionada ===
                "TODAS"

                ?

                "Todas as substâncias"

                :

                substanciaSelecionada;


            carregando.style.display =
                "none";

        }}


        /* ==================================================
           TROCAR ANO
           ================================================== */

        filtroAno.addEventListener(
            "change",
            atualizarMapa
        );


        /* ==================================================
           PRIMEIRA ATUALIZAÇÃO
           ================================================== */

        atualizarMapa();

    }}
);

</script>
"""


mapa_cfem.get_root().html.add_child(
    folium.Element(
        interface_html
    )
)


# ============================================================
# 24. CONTROLE DOS MAPAS BASE
# ============================================================

folium.LayerControl(
    collapsed=True
).add_to(
    mapa_cfem
)


# ============================================================
# 25. ENQUADRAR MINAS GERAIS
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
# 26. SALVAR INDEX.HTML
# ============================================================

print(
    "\nSalvando mapa..."
)

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 27. FINALIZAÇÃO
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
    f"Quantidade de substâncias: "
    f"{len(todas_substancias)}"
)

print(
    "=" * 60
)
