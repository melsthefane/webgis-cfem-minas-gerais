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
# ETAPA 9
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
print("Iniciando atualização...")
print("=" * 70)


# ============================================================
# 1. BAIXAR CSV DA ANM
# ============================================================

print("\nBaixando dados da ANM...")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
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
# 2. DATA DE ATUALIZAÇÃO DO ARQUIVO DA ANM
#
# IMPORTANTE:
# Esta data NÃO vem de DataCriacao.
#
# Ela representa a última modificação do próprio arquivo:
#
# CFEM_Arrecadacao_2022_2026.csv
#
# disponibilizado no servidor oficial da ANM.
# ============================================================

print(
    "\nIdentificando data de atualização "
    "do arquivo CSV da ANM..."
)

ultima_modificacao = response.headers.get(
    "Last-Modified"
)

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

        print(
            "Last-Modified:",
            ultima_modificacao
        )

    except Exception as erro:

        print(
            "Erro ao interpretar Last-Modified:",
            erro
        )

else:

    print(
        "O servidor não retornou "
        "o cabeçalho Last-Modified."
    )


print(
    "Atualização dos dados ANM:",
    data_atualizacao_anm
)


# ============================================================
# 3. DATA DE GERAÇÃO DO WEBGIS
# ============================================================

agora = datetime.now()

data_geracao_webgis = (
    agora.strftime("%d/%m/%Y %H:%M")
)


# ============================================================
# 4. LER CSV
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
# 5. FILTRAR MINAS GERAIS
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
# 6. VALOR RECOLHIDO
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
# 7. CÓDIGO MUNICIPAL
# ============================================================

cfem_mg["CodigoMunicipio"] = (
    cfem_mg["CodigoMunicipio"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(7)
)


# ============================================================
# 8. ANO
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
# 9. MUNICÍPIO
# ============================================================

cfem_mg["Município"] = (
    cfem_mg["Município"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ============================================================
# 10. SUBSTÂNCIA
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
# 11. ANOS
# ============================================================

anos = sorted(
    cfem_mg["Ano"]
    .unique()
    .tolist()
)

if not anos:

    raise ValueError(
        "Nenhum ano encontrado."
    )

ano_padrao = max(anos)

print(
    "Anos disponíveis:",
    anos
)


# ============================================================
# 12. TOTAL MUNICÍPIO / ANO
# ============================================================

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
# 13. MUNICÍPIO / ANO / SUBSTÂNCIA
# ============================================================

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


# ============================================================
# 14. SUBSTÂNCIAS
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


# ============================================================
# 15. JSON
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


# ============================================================
# 16. MUNICÍPIOS
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
# 17. DADOS INICIAIS
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
]

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
# 18. CORES
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
# 19. MAPA
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
# 20. MAPAS BASE
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
# 21. MUNICÍPIOS
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
                feature["properties"][
                    "CFEM_Total"
                ]
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
# 22. LIMITES DE MG
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
# 23. TÍTULO
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
# 24. VARIÁVEIS JAVASCRIPT
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

data_atualizacao_anm_json = (
    json.dumps(
        data_atualizacao_anm,
        ensure_ascii=False
    )
)

data_geracao_webgis_json = (
    json.dumps(
        data_geracao_webgis,
        ensure_ascii=False
    )
)


# ============================================================
# 25. INTERFACE
#
# NÃO transformar em f-string.
# ============================================================

interface_html = r"""
<style>

html, body {
    margin:0;
    padding:0;
}

#titulo-webgis,
#painel-cfem,
#legenda-cfem,
#modal-sobre-cfem {
    font-family:Arial, Helvetica, sans-serif;
}

/* TÍTULO */

#titulo-webgis {
    position:fixed;
    top:10px;
    left:70px;
    z-index:9997;
    max-width:calc(100vw - 500px);
    background:rgba(255,255,255,.96);
    border:1px solid #888;
    border-radius:7px;
    padding:9px 16px;
    box-shadow:0 2px 7px rgba(0,0,0,.25);
    pointer-events:none;
}

.titulo-principal {
    font-size:19px;
    font-weight:bold;
    white-space:nowrap;
}

.titulo-secundario {
    font-size:12px;
    margin-top:4px;
}

/* PAINEL */

#painel-cfem {
    position:fixed;
    top:90px;
    right:20px;
    width:365px;
    max-height:calc(100vh - 115px);
    overflow-y:auto;
    overflow-x:hidden;
    z-index:9999;
    background:rgba(255,255,255,.97);
    border:1px solid #999;
    border-radius:8px;
    padding:14px;
    box-sizing:border-box;
    box-shadow:0 2px 8px rgba(0,0,0,.28);
}

#painel-cfem h3 {
    margin:0 0 12px;
    font-size:16px;
}

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
    padding:8px;
    border:1px solid #aaa;
    border-radius:5px;
    background:#fff;
    box-sizing:border-box;
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
    background:white;
    box-shadow:0 2px 5px rgba(0,0,0,.15);
}

.item-substancia,
.item-municipio {
    padding:8px 9px;
    font-size:12px;
    cursor:pointer;
    border-bottom:1px solid #eee;
}

.item-substancia:hover,
.item-municipio:hover {
    background:#eee;
}

.item-principal {
    font-weight:bold;
}

.sem-resultado {
    padding:9px;
    font-size:11px;
    color:#777;
}

#botao-voltar-mg {
    width:100%;
    margin-top:8px;
    padding:8px;
    border:1px solid #999;
    border-radius:5px;
    background:#f5f5f5;
    cursor:pointer;
    font-size:11px;
}

.secao {
    margin-top:13px;
    padding-top:10px;
    border-top:1px solid #ddd;
}

.secao-titulo {
    font-size:12px;
    font-weight:bold;
    color:#444;
    margin-bottom:7px;
}

/* INDICADORES */

.grade-indicadores {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:7px;
}

.cartao-indicador {
    border:1px solid #ddd;
    border-radius:6px;
    background:#fafafa;
    padding:8px;
    min-height:55px;
    box-sizing:border-box;
}

.cartao-indicador.total {
    grid-column:1/-1;
}

.indicador-rotulo {
    font-size:10px;
    color:#666;
    margin-bottom:4px;
}

.indicador-valor {
    font-size:14px;
    font-weight:bold;
}

.indicador-detalhe {
    font-size:10px;
    color:#666;
    margin-top:3px;
}

/* RANKING */

#lista-ranking {
    border:1px solid #ddd;
    border-radius:6px;
    overflow:hidden;
}

.item-ranking {
    display:grid;
    grid-template-columns:28px 1fr auto;
    gap:6px;
    align-items:center;
    padding:7px 8px;
    border-bottom:1px solid #eee;
    cursor:pointer;
}

.item-ranking:hover {
    background:#f1f1f1;
}

.item-ranking.selecionado {
    background:#e8e8e8;
    box-shadow:inset 3px 0 0 #222;
}

.ranking-posicao {
    font-size:11px;
    font-weight:bold;
    color:#777;
}

.ranking-municipio {
    font-size:11px;
    font-weight:600;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}

.ranking-valor {
    font-size:10px;
    font-weight:bold;
    white-space:nowrap;
}

.ranking-vazio {
    padding:10px;
    font-size:11px;
    color:#777;
}

/* MUNICÍPIO */

#painel-municipio {
    display:none;
    margin-top:13px;
    padding-top:10px;
    border-top:2px solid #777;
}

#municipio-nome {
    font-size:17px;
    font-weight:bold;
    margin-bottom:8px;
}

.municipio-grade {
    display:grid;
    grid-template-columns:1fr 1fr;
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
    margin-bottom:4px;
}

.municipio-valor {
    font-size:13px;
    font-weight:bold;
}

/* SÉRIE */

#serie-barras {
    border:1px solid #ddd;
    border-radius:6px;
    padding:8px;
}

.serie-linha {
    display:grid;
    grid-template-columns:42px 1fr 82px;
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

.serie-linha.ativa .serie-barra {
    background:#222;
}

.serie-valor {
    font-size:9px;
    text-align:right;
}

.serie-nota {
    margin-top:7px;
    font-size:9px;
    line-height:1.35;
    color:#777;
}

/* ETAPA 9 */

.botoes-etapa9 {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:7px;
}

.botao-etapa9 {
    padding:9px;
    border:1px solid #888;
    border-radius:5px;
    background:#f5f5f5;
    font-size:11px;
    font-weight:600;
    cursor:pointer;
}

.botao-etapa9:hover {
    background:#e7e7e7;
}

#info-atualizacao-painel {
    margin-top:8px;
    padding:8px;
    background:#fafafa;
    border:1px solid #ddd;
    border-radius:5px;
    font-size:10px;
    line-height:1.5;
}

#status-consulta {
    margin-top:12px;
    padding-top:9px;
    border-top:1px solid #ddd;
    font-size:11px;
    color:#555;
}

#carregando-cfem {
    display:none;
    margin-top:8px;
    font-size:11px;
    font-weight:bold;
}

/* LEGENDA */

#legenda-cfem {
    position:fixed;
    bottom:30px;
    left:30px;
    width:285px;
    max-height:calc(100vh - 120px);
    overflow-y:auto;
    z-index:9996;
    background:rgba(255,255,255,.96);
    border:1px solid #888;
    border-radius:7px;
    padding:12px;
    box-sizing:border-box;
    box-shadow:0 2px 7px rgba(0,0,0,.25);
    font-size:12px;
}

.legenda-titulo {
    font-size:14px;
    font-weight:bold;
    margin-bottom:8px;
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
    border-top:1px solid #bbb;
    margin-top:9px;
    padding-top:7px;
    font-size:10px;
    line-height:1.45;
}

/* MODAL */

#modal-sobre-cfem {
    display:none;
    position:fixed;
    inset:0;
    z-index:20000;
    background:rgba(0,0,0,.48);
    padding:25px;
    box-sizing:border-box;
    align-items:center;
    justify-content:center;
}

#modal-sobre-cfem.aberto {
    display:flex;
}

#conteudo-modal {
    width:min(680px, calc(100vw - 40px));
    max-height:calc(100vh - 50px);
    overflow-y:auto;
    background:#fff;
    border-radius:9px;
    padding:20px;
    box-sizing:border-box;
    position:relative;
}

#fechar-modal {
    position:absolute;
    right:12px;
    top:10px;
    border:none;
    border-radius:50%;
    width:32px;
    height:32px;
    cursor:pointer;
    font-size:20px;
}

#conteudo-modal h2 {
    margin-top:0;
}

.bloco-sobre {
    margin-top:15px;
    font-size:12px;
    line-height:1.55;
}

.tabela-metadados {
    width:100%;
    border-collapse:collapse;
    font-size:11px;
}

.tabela-metadados td {
    padding:7px 5px;
    border-bottom:1px solid #eee;
}

.tabela-metadados td:first-child {
    font-weight:bold;
    width:180px;
}

/* RESPONSIVO */

@media(max-width:768px) {

    #titulo-webgis {
        left:50px;
        right:55px;
        max-width:none;
    }

    .titulo-principal {
        font-size:14px;
        white-space:normal;
    }

    .titulo-secundario {
        display:none;
    }

    #painel-cfem {
        top:auto;
        bottom:8px;
        left:8px;
        right:8px;
        width:auto;
        max-height:52vh;
        padding:10px;
    }

    #legenda-cfem {
        top:65px;
        bottom:auto;
        left:8px;
        width:190px;
        max-height:calc(42vh - 70px);
        padding:8px;
        font-size:10px;
    }

    .creditos-cfem {
        display:none;
    }

    .botoes-etapa9 {
        grid-template-columns:1fr;
    }

}

</style>


<div id="painel-cfem">

<h3>Consulta CFEM</h3>

<label class="rotulo-cfem">Ano</label>
<select id="filtro-ano"></select>

<label class="rotulo-cfem">
Substância mineral
</label>

<input
    id="busca-substancia"
    value="Todas as substâncias"
    autocomplete="off"
>

<div id="lista-substancias"></div>

<label class="rotulo-cfem">
Município
</label>

<input
    id="busca-municipio"
    placeholder="Digite o nome do município..."
    autocomplete="off"
>

<div id="lista-municipios"></div>

<button id="botao-voltar-mg">
Visualizar todo o estado
</button>


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


<div class="secao">

<div class="secao-titulo">
Ranking municipal — TOP 10
</div>

<div id="lista-ranking"></div>

</div>


<div id="painel-municipio">

<div style="
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


<div class="secao">

<div class="secao-titulo">
Série histórica da CFEM
</div>

<div
    id="serie-substancia"
    style="
        font-size:9px;
        color:#777;
        margin-bottom:7px;
    ">
</div>

<div id="serie-barras"></div>

<div
    id="serie-nota"
    class="serie-nota">
</div>

</div>

</div>


<div class="secao">

<div class="secao-titulo">
Dados e informações
</div>

<div class="botoes-etapa9">

<button
    id="botao-download-csv"
    class="botao-etapa9">
Baixar consulta CSV
</button>

<button
    id="botao-sobre"
    class="botao-etapa9">
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

<span id="status-substancia">
Todas as substâncias
</span>

</div>

<div id="carregando-cfem">
Atualizando mapa...
</div>

</div>


<!-- LEGENDA -->

<div id="legenda-cfem">

<div class="legenda-titulo">
CFEM arrecadada
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#eeeeee"></span>
Sem arrecadação
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#ffffcc"></span>
Até R$ 10 mil
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#ffeda0"></span>
R$ 10 mil – R$ 100 mil
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#fed976"></span>
R$ 100 mil – R$ 1 milhão
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#feb24c"></span>
R$ 1 mi – R$ 10 milhões
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#f03b20"></span>
R$ 10 mi – R$ 100 milhões
</div>

<div class="legenda-item">
<span class="caixa-cor"
style="background:#bd0026"></span>
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


<!-- MODAL -->

<div id="modal-sobre-cfem">

<div id="conteudo-modal">

<button id="fechar-modal">
×
</button>

<h2>
Sobre o WebGIS CFEM
</h2>

<div class="bloco-sobre">

<p>
Este WebGIS apresenta a distribuição espacial
da arrecadação da Compensação Financeira pela
Exploração de Recursos Minerais (CFEM) nos
municípios de Minas Gerais.
</p>

<p>
A aplicação permite consultar valores por ano,
substância mineral e município, além de apresentar
indicadores, ranking municipal e série histórica.
</p>

</div>


<div class="bloco-sobre">

<h4>Fontes de dados</h4>

<p>
Os dados de arrecadação são provenientes da
Agência Nacional de Mineração — ANM.
</p>

<p>
A malha municipal é proveniente do Instituto
Brasileiro de Geografia e Estatística — IBGE.
</p>

</div>


<div class="bloco-sobre">

<h4>Ano mais recente</h4>

<p>
O ano mais recente pode representar valores
acumulados disponíveis até a data de atualização
do arquivo da ANM e não necessariamente um
exercício anual encerrado.
</p>

</div>


<div class="bloco-sobre">

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
</div>


<script>

document.addEventListener(
"DOMContentLoaded",
async function() {

const mapa = __MAPA_JS__;
const camadaMunicipios = __CAMADA_MUNICIPIOS__;

const anos = __ANOS_JSON__;
const substancias = __SUBSTANCIAS_JSON__;
const principais = __PRINCIPAIS_JSON__;
const municipiosBusca = __MUNICIPIOS_JSON__;
const limitesMG = __LIMITES_MG__;
const anoPadrao = __ANO_PADRAO__;

const dataAtualizacaoANM =
    __DATA_ATUALIZACAO_ANM_JSON__;

let dadosCFEM = null;

let substanciaSelecionada = "TODAS";

let codigoMunicipioSelecionado = null;
let nomeMunicipioSelecionado = null;
let camadaMunicipioSelecionado = null;

let valoresConsultaAtual = new Map();
let rankingConsultaAtual = [];


/* ELEMENTOS */

const filtroAno =
document.getElementById("filtro-ano");

const buscaSubstancia =
document.getElementById("busca-substancia");

const listaSubstancias =
document.getElementById("lista-substancias");

const buscaMunicipio =
document.getElementById("busca-municipio");

const listaMunicipios =
document.getElementById("lista-municipios");

const botaoVoltarMG =
document.getElementById("botao-voltar-mg");

const indicadorTotal =
document.getElementById("indicador-total");

const indicadorMunicipios =
document.getElementById("indicador-municipios");

const indicadorMaiorValor =
document.getElementById("indicador-maior-valor");

const indicadorMaiorMunicipio =
document.getElementById("indicador-maior-municipio");

const listaRanking =
document.getElementById("lista-ranking");

const painelMunicipio =
document.getElementById("painel-municipio");

const municipioNome =
document.getElementById("municipio-nome");

const municipioValor =
document.getElementById("municipio-valor");

const municipioValorRotulo =
document.getElementById("municipio-valor-rotulo");

const municipioParticipacao =
document.getElementById("municipio-participacao");

const municipioPosicao =
document.getElementById("municipio-posicao");

const serieSubstancia =
document.getElementById("serie-substancia");

const serieBarras =
document.getElementById("serie-barras");

const serieNota =
document.getElementById("serie-nota");

const statusAno =
document.getElementById("status-ano");

const statusSubstancia =
document.getElementById("status-substancia");

const carregando =
document.getElementById("carregando-cfem");

const modal =
document.getElementById("modal-sobre-cfem");


/* MAPAS AUXILIARES */

const municipioPorCodigo = new Map();
const layerPorCodigo = new Map();

municipiosBusca.forEach(function(m) {

    municipioPorCodigo.set(
        String(m.CD_MUN),
        m
    );

});

camadaMunicipios.eachLayer(function(layer) {

    if (!layer.feature) return;

    const codigo =
        String(
            layer.feature.properties.CD_MUN
        );

    layerPorCodigo.set(
        codigo,
        layer
    );

});


/* FUNÇÕES */

function normalizar(texto) {

    return String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
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

    valor = Number(valor || 0);

    if (valor >= 1000000000)
        return "R$ " +
        (valor / 1000000000)
        .toLocaleString(
            "pt-BR",
            {maximumFractionDigits:2}
        ) + " bi";

    if (valor >= 1000000)
        return "R$ " +
        (valor / 1000000)
        .toLocaleString(
            "pt-BR",
            {maximumFractionDigits:2}
        ) + " mi";

    if (valor >= 1000)
        return "R$ " +
        (valor / 1000)
        .toLocaleString(
            "pt-BR",
            {maximumFractionDigits:2}
        ) + " mil";

    return moeda(valor);

}


function corCFEM(valor) {

    valor = Number(valor || 0);

    if (valor <= 0) return "#eeeeee";
    if (valor <= 10000) return "#ffffcc";
    if (valor <= 100000) return "#ffeda0";
    if (valor <= 1000000) return "#fed976";
    if (valor <= 10000000) return "#feb24c";
    if (valor <= 100000000) return "#f03b20";

    return "#bd0026";

}


function aplicarEstiloNormal(layer) {

    const valor =
        Number(
            layer.feature.properties
            .CFEM_Total || 0
        );

    layer.setStyle({
        fillColor:corCFEM(valor),
        color:"#555555",
        weight:0.6,
        fillOpacity:0.80
    });

}


function aplicarDestaque() {

    if (!camadaMunicipioSelecionado)
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
    )
        camadaMunicipioSelecionado
        .bringToFront();

}


/* ANOS */

anos.slice()
.sort((a,b) => b-a)
.forEach(function(ano) {

    const op =
        document.createElement("option");

    op.value = ano;
    op.textContent = ano;

    if (
        Number(ano) ===
        Number(anoPadrao)
    )
        op.selected = true;

    filtroAno.appendChild(op);

});


/* SUBSTÂNCIAS */

function mostrarSubstancias(texto) {

    listaSubstancias.innerHTML = "";

    const todas =
        document.createElement("div");

    todas.className =
        "item-substancia item-principal";

    todas.textContent =
        "Todas as substâncias";

    todas.onclick = function() {

        substanciaSelecionada =
            "TODAS";

        buscaSubstancia.value =
            "Todas as substâncias";

        listaSubstancias.style.display =
            "none";

        atualizarMapa();

    };

    listaSubstancias.appendChild(todas);

    const busca = normalizar(texto);

    let resultados =
        substancias.filter(function(s) {

            return !busca ||
            normalizar(s).includes(busca);

        });

    if (!busca) {

        resultados.sort(function(a,b) {

            const ia = principais.indexOf(a);
            const ib = principais.indexOf(b);

            if (ia !== -1 && ib === -1)
                return -1;

            if (ia === -1 && ib !== -1)
                return 1;

            if (ia !== -1 && ib !== -1)
                return ia - ib;

            return a.localeCompare(
                b,
                "pt-BR"
            );

        });

    }

    resultados
    .slice(0,60)
    .forEach(function(s) {

        const item =
            document.createElement("div");

        item.className =
            "item-substancia";

        if (principais.includes(s))
            item.classList.add(
                "item-principal"
            );

        item.textContent = s;

        item.onclick = function() {

            substanciaSelecionada = s;

            buscaSubstancia.value = s;

            listaSubstancias.style.display =
                "none";

            atualizarMapa();

        };

        listaSubstancias.appendChild(item);

    });

    listaSubstancias.style.display =
        "block";

}


buscaSubstancia.addEventListener(
"focus",
function() {

    if (
        substanciaSelecionada ===
        "TODAS"
    )
        buscaSubstancia.value = "";

    mostrarSubstancias(
        buscaSubstancia.value
    );

});


buscaSubstancia.addEventListener(
"input",
function() {

    mostrarSubstancias(
        buscaSubstancia.value
    );

});


/* MUNICÍPIOS */

function mostrarMunicipios(texto) {

    listaMunicipios.innerHTML = "";

    const busca = normalizar(texto);

    if (!busca) {

        listaMunicipios.style.display =
            "none";

        return;

    }

    const resultados =
        municipiosBusca.filter(
            function(m) {

                return normalizar(
                    m.NM_MUN
                ).includes(busca);

            }
        );

    resultados
    .slice(0,30)
    .forEach(function(m) {

        const item =
            document.createElement("div");

        item.className =
            "item-municipio";

        item.textContent =
            m.NM_MUN;

        item.onclick = function() {

            selecionarMunicipio(
                m.CD_MUN,
                m.NM_MUN,
                true
            );

        };

        listaMunicipios.appendChild(item);

    });

    listaMunicipios.style.display =
        "block";

}


buscaMunicipio.addEventListener(
"input",
function() {

    mostrarMunicipios(
        buscaMunicipio.value
    );

});


/* SELEÇÃO MUNICIPAL */

function selecionarMunicipio(
codigo,
nome,
fazerZoom
) {

    codigo = String(codigo);

    codigoMunicipioSelecionado =
        codigo;

    nomeMunicipioSelecionado =
        nome;

    buscaMunicipio.value =
        nome;

    listaMunicipios.style.display =
        "none";

    camadaMunicipios.eachLayer(
        aplicarEstiloNormal
    );

    camadaMunicipioSelecionado =
        layerPorCodigo.get(codigo);

    aplicarDestaque();

    /*
     * Busca e ranking fazem zoom.
     * Clique direto NÃO faz zoom.
     */
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


/* CLIQUE DIRETO NO POLÍGONO */

camadaMunicipios.eachLayer(
function(layer) {

    const p =
        layer.feature.properties;

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


/* VOLTAR MG */

botaoVoltarMG.onclick =
function() {

    codigoMunicipioSelecionado = null;
    nomeMunicipioSelecionado = null;
    camadaMunicipioSelecionado = null;

    buscaMunicipio.value = "";

    painelMunicipio.style.display =
        "none";

    camadaMunicipios.eachLayer(
        aplicarEstiloNormal
    );

    destacarRanking();

    mapa.fitBounds(
        limitesMG
    );

};


/* CARREGAR JSON */

try {

    carregando.style.display =
        "block";

    const resposta =
        await fetch(
            "dados_cfem.json?v=" +
            Date.now()
        );

    if (!resposta.ok)
        throw new Error(
            "HTTP " + resposta.status
        );

    dadosCFEM =
        await resposta.json();

    carregando.style.display =
        "none";

}

catch(erro) {

    console.error(erro);

    carregando.textContent =
        "Erro ao carregar dados da CFEM.";

    return;

}


/* CONSULTA */

function obterValoresConsulta(ano) {

    const valores =
        new Map();

    const fonte =
        substanciaSelecionada ===
        "TODAS"
        ?
        dadosCFEM.totais
        :
        dadosCFEM.substancias;

    fonte.forEach(function(item) {

        if (
            Number(item.Ano) !==
            Number(ano)
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

        valores.set(
            String(
                item.CodigoMunicipio
            ),
            Number(
                item.CFEM_Total
            )
        );

    });

    return valores;

}


/* RANKING */

function gerarRanking(valores) {

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
                codigo:String(codigo),
                nome:m.NM_MUN,
                valor:valor
            });

        }
    );

    ranking.sort(
        (a,b) =>
            b.valor - a.valor ||
            a.nome.localeCompare(
                b.nome,
                "pt-BR"
            )
    );

    return ranking;

}


/* INDICADORES */

function atualizarIndicadores() {

    let total = 0;
    let quantidade = 0;

    valoresConsultaAtual.forEach(
        function(v) {

            total += Number(v || 0);

            if (Number(v) > 0)
                quantidade++;

        }
    );

    indicadorTotal.textContent =
        moeda(total);

    indicadorMunicipios.textContent =
        quantidade.toLocaleString(
            "pt-BR"
        );

    if (
        rankingConsultaAtual.length
    ) {

        indicadorMaiorValor.textContent =
            moeda(
                rankingConsultaAtual[0]
                .valor
            );

        indicadorMaiorMunicipio
        .textContent =
            rankingConsultaAtual[0]
            .nome;

    }

    else {

        indicadorMaiorValor.textContent =
            moeda(0);

        indicadorMaiorMunicipio
        .textContent = "—";

    }

}


/* RANKING VISUAL */

function atualizarRanking() {

    listaRanking.innerHTML = "";

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
                + (i+1) + 'º</div>'
                +
                '<div class="ranking-municipio">'
                + item.nome + '</div>'
                +
                '<div class="ranking-valor">'
                + moedaCompacta(item.valor)
                + '</div>';

            linha.onclick =
                function() {

                    selecionarMunicipio(
                        item.codigo,
                        item.nome,
                        true
                    );

                };

            listaRanking.appendChild(
                linha
            );

        }
    );

    destacarRanking();

}


function destacarRanking() {

    document
    .querySelectorAll(
        ".item-ranking"
    )
    .forEach(function(item) {

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


/* SÉRIE HISTÓRICA */

function obterSerie(codigo) {

    const serie = new Map();

    anos.forEach(
        ano => serie.set(
            Number(ano),
            0
        )
    );

    const fonte =
        substanciaSelecionada ===
        "TODAS"
        ?
        dadosCFEM.totais
        :
        dadosCFEM.substancias;

    fonte.forEach(function(item) {

        if (
            String(
                item.CodigoMunicipio
            )
            !==
            String(codigo)
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

        serie.set(
            Number(item.Ano),
            Number(item.CFEM_Total)
        );

    });

    return serie;

}


function desenharSerie(serie) {

    serieBarras.innerHTML = "";

    let maximo = 0;

    serie.forEach(
        v => maximo =
            Math.max(
                maximo,
                Number(v)
            )
    );

    const anoAtual =
        Number(
            filtroAno.value
        );

    anos.slice()
    .sort((a,b) => a-b)
    .forEach(function(ano) {

        const valor =
            Number(
                serie.get(
                    Number(ano)
                ) || 0
            );

        const largura =
            maximo > 0
            ?
            valor / maximo * 100
            :
            0;

        const linha =
            document.createElement(
                "div"
            );

        linha.className =
            "serie-linha" +
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
            '<div class="serie-barra" '
            +
            'style="width:'
            + largura
            + '%"></div>'
            +
            '</div>'
            +
            '<div class="serie-valor">'
            +
            moedaCompacta(valor)
            +
            '</div>';

        serieBarras.appendChild(
            linha
        );

    });

    serieNota.textContent =
        "* "
        + anoPadrao
        + ": valor acumulado disponível "
        + "na base da ANM. "
        + "Arquivo atualizado em "
        + dataAtualizacaoANM
        + ".";

}


/* PAINEL MUNICIPAL */

function atualizarPainelMunicipio() {

    if (
        !codigoMunicipioSelecionado
    ) {
        return;
    }

    painelMunicipio.style.display =
        "block";

    const ano =
        Number(
            filtroAno.value
        );

    const valor =
        Number(
            valoresConsultaAtual.get(
                String(
                    codigoMunicipioSelecionado
                )
            ) || 0
        );

    let totalMG = 0;

    valoresConsultaAtual.forEach(
        v => totalMG += Number(v)
    );

    const participacao =
        totalMG > 0
        ?
        valor / totalMG * 100
        :
        0;

    const posicao =
        rankingConsultaAtual
        .findIndex(
            x =>
            String(x.codigo) ===
            String(
                codigoMunicipioSelecionado
            )
        );

    municipioNome.textContent =
        nomeMunicipioSelecionado;

    municipioValorRotulo.textContent =
        "CFEM — " + ano;

    municipioValor.textContent =
        moeda(valor);

    municipioParticipacao.textContent =
        participacao
        .toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits:2,
                maximumFractionDigits:2
            }
        ) + "%";

    municipioPosicao.textContent =
        posicao >= 0
        ?
        (posicao + 1) + "º"
        :
        "Sem arrecadação";

    serieSubstancia.textContent =
        substanciaSelecionada ===
        "TODAS"
        ?
        "Todas as substâncias"
        :
        substanciaSelecionada;

    desenharSerie(
        obterSerie(
            codigoMunicipioSelecionado
        )
    );

}


/* DOWNLOAD CSV */

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

    const linhas = [
        [
            "Ano",
            "CodigoMunicipio",
            "Municipio",
            "Substancia",
            "CFEM_Total_R$",
            "Atualizacao_dados_ANM"
        ].join(";")
    ];

    municipiosBusca.forEach(
        function(m) {

            const valor =
                Number(
                    valoresConsultaAtual
                    .get(
                        String(m.CD_MUN)
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
                    m.CD_MUN,
                    '"' +
                    String(m.NM_MUN)
                    .replace(/"/g,'""')
                    + '"',
                    '"' +
                    String(substancia)
                    .replace(/"/g,'""')
                    + '"',
                    valor
                    .toFixed(2)
                    .replace(".",","),
                    dataAtualizacaoANM
                ].join(";")
            );

        }
    );

    const blob =
        new Blob(
            [
                "\uFEFF" +
                linhas.join("\r\n")
            ],
            {
                type:
                "text/csv;charset=utf-8"
            }
        );

    const url =
        URL.createObjectURL(blob);

    const link =
        document.createElement("a");

    link.href = url;

    link.download =
        "cfem_mg_"
        + ano
        + ".csv";

    link.click();

    URL.revokeObjectURL(url);

};


/* MODAL */

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
    )
        modal.classList.remove(
            "aberto"
        );

};


/* ATUALIZAÇÃO PRINCIPAL */

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

    camadaMunicipios.eachLayer(
        function(layer) {

            const p =
                layer.feature.properties;

            const codigo =
                String(p.CD_MUN);

            const valor =
                Number(
                    valoresConsultaAtual
                    .get(codigo) || 0
                );

            p.CFEM_Total = valor;
            p.Ano = ano;

            aplicarEstiloNormal(layer);

            const substancia =
                substanciaSelecionada ===
                "TODAS"
                ?
                "Todas as substâncias"
                :
                substanciaSelecionada;

            const tooltip =
                "<b>Município:</b> "
                + p.NM_MUN
                + "<br>"
                + "<b>Ano:</b> "
                + ano
                + "<br>"
                + "<b>Substância:</b> "
                + substancia
                + "<br>"
                + "<b>CFEM:</b> "
                + moeda(valor)
                + "<br>"
                + "<span style='color:#666'>"
                + "Clique para consultar o município"
                + "</span>";

            if (layer.getTooltip())
                layer.setTooltipContent(
                    tooltip
                );
            else
                layer.bindTooltip(
                    tooltip,
                    {sticky:true}
                );

        }
    );

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

    statusAno.textContent =
        ano;

    statusSubstancia.textContent =
        substanciaSelecionada ===
        "TODAS"
        ?
        "Todas as substâncias"
        :
        substanciaSelecionada;

}


/* ANO */

filtroAno.onchange =
function() {

    atualizarMapa();

};


/* FECHAR LISTAS */

document.addEventListener(
"click",
function(event) {

    if (
        event.target !==
        buscaSubstancia
        &&
        !listaSubstancias.contains(
            event.target
        )
    )
        listaSubstancias.style.display =
            "none";

    if (
        event.target !==
        buscaMunicipio
        &&
        !listaMunicipios.contains(
            event.target
        )
    )
        listaMunicipios.style.display =
            "none";

});


/* INICIALIZAÇÃO */

atualizarMapa();

});
</script>
"""


# ============================================================
# 26. SUBSTITUIR PLACEHOLDERS
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
    "__DATA_GERACAO_WEBGIS_JSON__",
    data_geracao_webgis_json
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
# 27. ADICIONAR INTERFACE
# ============================================================

mapa_cfem.get_root().html.add_child(
    folium.Element(
        interface_html
    )
)


# ============================================================
# 28. CONTROLE DE CAMADAS
# ============================================================

folium.LayerControl(
    collapsed=True
).add_to(
    mapa_cfem
)


# ============================================================
# 29. ENQUADRAR MINAS GERAIS
# ============================================================

mapa_cfem.fit_bounds(
    limites_mg
)


# ============================================================
# 30. SALVAR
# ============================================================

print("\nSalvando WebGIS...")

mapa_cfem.save(
    ARQUIVO_SAIDA
)


# ============================================================
# 31. RESULTADO
# ============================================================

print("\n" + "=" * 70)
print("WEBGIS ATUALIZADO COM SUCESSO")
print("=" * 70)

print(
    f"Mapa: {ARQUIVO_SAIDA}"
)

print(
    f"JSON: {ARQUIVO_DADOS}"
)

print(
    "Atualização dos dados ANM:",
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

print("=" * 70)
