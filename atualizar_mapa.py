# ============================================================
# PAINEL DA MINERAÇÃO | MINAS GERAIS
# V5 - CFEM + SIGMINE + SCM + WEBGIS + EXPORTAÇÃO GIS
# ============================================================

import io
import re
import zipfile
import tempfile
import unicodedata
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import geopandas as gpd
import folium

from folium.plugins import Fullscreen
from streamlit_folium import st_folium


# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Painel da Mineração | Minas Gerais",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. FONTES OFICIAIS ANM
# ============================================================

CFEM_URL = (
    "https://dadosabertos.anm.gov.br/"
    "CFEM/CFEM_Arrecadacao_2022_2026.csv"
)

SIGMINE_MG_URL = (
    "https://dadosabertos.anm.gov.br/"
    "SIGMINE/PROCESSOS_MINERARIOS/MG.zip"
)

SCM_BASE = "https://dadosabertos.anm.gov.br/SCM/"

SCM_FILES = {
    "Alvará de Pesquisa": "Alvara_de_Pesquisa.csv",
    "Cessões de Direitos": "Cessoes_de_Direitos.csv",
    "Guia de Utilização": "Guia_de_Utilizacao_Autorizada.csv",
    "Licenciamento": "Licenciamento.csv",
    "PLG": "PLG.csv",
    "Portaria de Lavra": "Portaria_de_Lavra.csv",
    "Registro de Extração": "Registro_de_Extracao_Publicado.csv",
    "Relatório de Pesquisa Aprovado": "Relatorio_de_Pesquisa_Aprovado.csv",
    "Requerimento de Lavra": "Requerimento_de_Lavra.csv",
    "Requerimento de Licenciamento": "Requerimento_de_Licenciamento.csv",
    "Requerimento de Pesquisa": "Requerimento_de_Pesquisa.csv",
    "Requerimento de PLG": "Requerimento_de_PLG.csv",
    "Requerimento de Registro de Extração":
        "Requerimento_de_Registro_de_Extracao_Protocolizado.csv",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/153 Safari/537.36"
    ),
    "Accept": "*/*",
}


# ============================================================
# 3. PALETA VISUAL
# ============================================================

AZUL_ESCURO = "#073B4C"
AZUL = "#0B5D75"
AZUL_MEDIO = "#168AAD"
AZUL_CLARO = "#DDEFF4"

VERDE = "#2A9D78"
VERDE_CLARO = "#E7F5F0"

DOURADO = "#D9A441"
DOURADO_CLARO = "#FFF5DD"

VERMELHO = "#C94C4C"

TEXTO = "#263238"
TEXTO_SEC = "#667580"

FUNDO = "#F4F7F9"
BRANCO = "#FFFFFF"
BORDA = "#DFE6EB"


# ============================================================
# 4. CSS
# ============================================================

st.markdown(
    """
<style>

:root {
    --primary: #0B5D75;
    --primary2: #168AAD;
    --green: #2A9D78;
    --gold: #D9A441;
    --background: #F4F7F9;
    --border: #DFE6EB;
    --text: #263238;
    --muted: #667580;
}

.stApp {
    background-color: #F4F7F9;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.15rem;
    padding-bottom: 2rem;
}

[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #DFE6EB;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.3rem;
}

[data-testid="stSidebar"] h1 {
    font-size: 1.45rem;
}

h1 {
    color: #263238;
    font-weight: 750;
    letter-spacing: -0.6px;
}

h2, h3 {
    color: #263238;
    font-weight: 700;
}

p {
    color: #46545C;
}

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #DFE6EB;
    border-radius: 14px;
    padding: 15px 17px 13px 17px;
    min-height: 118px;
    box-shadow: 0px 2px 8px rgba(25, 45, 55, 0.035);
}

div[data-testid="stMetricLabel"] {
    color: #667580;
    font-weight: 600;
}

div[data-testid="stMetricValue"] {
    color: #0B5D75;
    font-size: 1.85rem;
    font-weight: 700;
}

div[data-testid="stPlotlyChart"] {
    background: #FFFFFF;
    border: 1px solid #DFE6EB;
    border-radius: 15px;
    padding: 8px;
    box-shadow: 0px 2px 8px rgba(25, 45, 55, 0.03);
}

div[data-testid="stDataFrame"] {
    background: white;
    border: 1px solid #DFE6EB;
    border-radius: 13px;
    overflow: hidden;
}

div[data-baseweb="select"] > div {
    border-radius: 9px;
}

div[data-testid="stTextInput"] input {
    border-radius: 9px;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 9px;
    font-weight: 600;
    min-height: 40px;
}

div[data-testid="stExpander"] {
    border: 1px solid #DFE6EB;
    border-radius: 12px;
    background: #FFFFFF;
}

hr {
    border-color: #DFE6EB;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# 5. FUNÇÕES DE NORMALIZAÇÃO
# ============================================================

def norm(valor):
    return (
        unicodedata.normalize("NFKD", str(valor))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def somente_digitos(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()
    texto = re.sub(r"\.0$", "", texto)

    return re.sub(r"\D", "", texto)


def encontrar_coluna(colunas, termos):
    """
    Procura uma coluna priorizando os termos informados.
    """

    for termo in termos:
        for coluna in colunas:
            if termo in norm(coluna):
                return coluna

    return None


# ============================================================
# 6. PROCESSO ANM
# ============================================================

def ano_processo_valido(valor):
    """Valida o bloco final de 4 dígitos usado como ano do processo ANM."""
    try:
        ano = int(valor)
        return 1900 <= ano <= 2100
    except Exception:
        return False


def criar_chave_processo(numero, ano=None):
    """
    Cria uma chave canônica somente com dígitos.

    Exemplos:
    43.306/1956  -> 433061956   (9 dígitos)
    43306/1956   -> 433061956
    433061956    -> 433061956
    830.195/2006 -> 8301952006  (10 dígitos)
    830195 + 2006 -> 8301952006

    Importante: processos ANM antigos podem ter apenas 5 dígitos antes
    do ano. Por isso a chave completa não é obrigatoriamente de 10 dígitos.
    """

    if pd.isna(numero):
        return ""

    texto = str(numero).strip()
    numero_digitos = somente_digitos(texto)
    ano_digitos = somente_digitos(ano)

    # Quando número e ano vêm em colunas separadas, esta é a fonte mais segura.
    if numero_digitos and len(ano_digitos) >= 4:
        ano_final = ano_digitos[-4:]
        if ano_processo_valido(ano_final):
            # Evita duplicar o ano caso o campo Processo já esteja completo.
            if (
                len(numero_digitos) >= 9
                and numero_digitos.endswith(ano_final)
            ):
                return numero_digitos
            return numero_digitos + ano_final

    # Entrada explicitamente no formato número/ano.
    if "/" in texto:
        partes = texto.rsplit("/", 1)
        numero_parte = somente_digitos(partes[0])
        ano_parte = somente_digitos(partes[1])[-4:]
        if numero_parte and ano_processo_valido(ano_parte):
            return numero_parte + ano_parte

    # Entrada compacta. Uma chave completa pode ter 9 ou mais dígitos:
    # 433061956 = 43306 + 1956; 8301952006 = 830195 + 2006.
    if len(numero_digitos) >= 9:
        ano_final = numero_digitos[-4:]
        if ano_processo_valido(ano_final):
            return numero_digitos

    # Número sem ano: preserva para não inventar informação.
    return numero_digitos


def formatar_processo(chave):
    """Formata a chave canônica como número/ano, inclusive processos antigos."""

    chave = somente_digitos(chave)

    # 5 dígitos de número + 4 do ano = 9 dígitos já é uma chave completa válida.
    if len(chave) < 9:
        return chave

    numero = chave[:-4]
    ano = chave[-4:]

    if not numero or not ano_processo_valido(ano):
        return chave

    try:
        numero = f"{int(numero):,}".replace(",", ".")
    except Exception:
        pass

    return f"{numero}/{ano}"


# ============================================================
# 7. FORMATAÇÃO BRASILEIRA
# ============================================================

def moeda(valor):

    try:
        valor = float(valor)
    except Exception:
        valor = 0

    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def moeda_resumida(valor):

    try:
        valor = float(valor)
    except Exception:
        valor = 0

    if abs(valor) >= 1_000_000_000:
        return (
            f"R$ {valor / 1_000_000_000:.2f} bi"
            .replace(".", ",")
        )

    if abs(valor) >= 1_000_000:
        return (
            f"R$ {valor / 1_000_000:.2f} mi"
            .replace(".", ",")
        )

    if abs(valor) >= 1_000:
        return (
            f"R$ {valor / 1_000:.2f} mil"
            .replace(".", ",")
        )

    return moeda(valor)


def numero_br(valor, casas=2):

    try:
        valor = float(valor)
    except Exception:
        return "-"

    return (
        f"{valor:,.{casas}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def inteiro_br(valor):

    try:
        return f"{int(valor):,}".replace(",", ".")
    except Exception:
        return "0"


def percentual_br(valor):

    try:
        return f"{float(valor):.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"


def area_br(valor):

    try:
        return f"{numero_br(valor, 2)} ha"
    except Exception:
        return "-"


# ============================================================
# 8. MESES
# ============================================================

MESES = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}

MESES_LONGOS = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


# ============================================================
# 9. LEITURA DE CSV
# ============================================================

def read_csv_bytes(content):

    if not content:
        raise ValueError("Arquivo vazio.")

    tentativas = [
        ("utf-8-sig", ","),
        ("utf-8", ","),
        ("latin1", ","),
        ("cp1252", ","),
        ("utf-8-sig", ";"),
        ("utf-8", ";"),
        ("latin1", ";"),
        ("cp1252", ";"),
    ]

    erros = []

    for encoding, separador in tentativas:

        try:

            df = pd.read_csv(
                io.BytesIO(content),
                encoding=encoding,
                sep=separador,
                low_memory=False,
                on_bad_lines="skip",
            )

            if len(df.columns) > 1:

                df.columns = [
                    str(c).strip()
                    for c in df.columns
                ]

                return df

        except Exception as erro:
            erros.append(str(erro))

    raise ValueError(
        "Não foi possível interpretar o CSV. "
        + " | ".join(erros[:3])
    )


def converter_numero(serie):

    serie = serie.astype(str).str.strip()

    possui_virgula = serie.str.contains(
        ",",
        regex=False
    )

    serie.loc[possui_virgula] = (
        serie.loc[possui_virgula]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(
        serie,
        errors="coerce"
    )


# ============================================================
# 10. CFEM
# ============================================================

@st.cache_data(ttl=21600, show_spinner=False)
def load_cfem():

    r = requests.get(
        CFEM_URL,
        headers=HEADERS,
        timeout=180
    )

    r.raise_for_status()

    df = read_csv_bytes(r.content)

    df["UF"] = (
        df["UF"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[
        df["UF"] == "MG"
    ].copy()

    df["Ano"] = pd.to_numeric(
        df["Ano"],
        errors="coerce"
    ).astype("Int64")

    df["Mês"] = pd.to_numeric(
        df["Mês"],
        errors="coerce"
    ).astype("Int64")

    for coluna in [
        "ValorRecolhido",
        "QuantidadeComercializada"
    ]:

        if coluna in df.columns:
            df[coluna] = converter_numero(
                df[coluna]
            )

    for coluna in [
        "Município",
        "Substância"
    ]:

        if coluna in df.columns:

            df[coluna] = (
                df[coluna]
                .astype(str)
                .str.strip()
                .str.upper()
            )

    if "AnoDoProcesso" in df.columns:

        df["Processo_key"] = [
            criar_chave_processo(p, a)
            for p, a in zip(
                df["Processo"],
                df["AnoDoProcesso"]
            )
        ]

    else:

        df["Processo_key"] = (
            df["Processo"]
            .map(criar_chave_processo)
        )

    df["Processo_fmt"] = (
        df["Processo_key"]
        .map(formatar_processo)
    )

    return df


# ============================================================
# 11. INFORMAÇÕES TEMPORAIS DA CFEM
# ============================================================

def info_periodo_cfem(df):

    if df.empty:
        return None, None, None

    ano_max = int(
        df["Ano"].dropna().max()
    )

    dados_ano = df[
        df["Ano"] == ano_max
    ]

    meses_validos = (
        dados_ano
        .groupby("Mês")["ValorRecolhido"]
        .sum()
    )

    # Consideramos publicado um mês com arrecadação > 0.
    meses_validos = meses_validos[
        meses_validos > 0
    ]

    if meses_validos.empty:
        mes_max = None
    else:
        mes_max = int(
            meses_validos.index.max()
        )

    ano_atual = datetime.now().year

    parcial = (
        ano_max >= ano_atual
        and mes_max is not None
        and mes_max < 12
    )

    return ano_max, mes_max, parcial


# ============================================================
# 12. SCM
# ============================================================

@st.cache_data(ttl=21600, show_spinner=False)
def load_scm_file(filename):

    r = requests.get(
        SCM_BASE + filename,
        headers=HEADERS,
        timeout=180
    )

    r.raise_for_status()

    df = read_csv_bytes(r.content)

    colunas = list(df.columns)

    coluna_processo = encontrar_coluna(
        colunas,
        [
            "processo",
            "numeroprocesso",
            "numprocesso",
        ]
    )

    if coluna_processo:

        # Tenta achar ano separado
        coluna_ano = encontrar_coluna(
            colunas,
            [
                "anoprocesso",
                "ano"
            ]
        )

        if coluna_ano:

            df["_processo_key"] = [
                criar_chave_processo(p, a)
                for p, a in zip(
                    df[coluna_processo],
                    df[coluna_ano]
                )
            ]

        else:

            df["_processo_key"] = (
                df[coluna_processo]
                .map(criar_chave_processo)
            )

    return df


# ============================================================
# 13. SIGMINE
# ============================================================

@st.cache_resource(ttl=21600, show_spinner=False)
def load_sigmine():

    r = requests.get(
        SIGMINE_MG_URL,
        headers=HEADERS,
        timeout=300
    )

    r.raise_for_status()

    if len(r.content) < 1000:
        raise ValueError(
            "Arquivo SIGMINE MG.zip inválido."
        )

    pasta = Path(
        tempfile.mkdtemp()
    )

    zip_path = pasta / "MG.zip"

    zip_path.write_bytes(
        r.content
    )

    destino = pasta / "sigmine"

    destino.mkdir(
        exist_ok=True
    )

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(destino)

    shapefiles = list(
        destino.rglob("*.shp")
    )

    if not shapefiles:
        raise FileNotFoundError(
            "Nenhum shapefile encontrado no MG.zip."
        )

    shp = max(
        shapefiles,
        key=lambda p: p.stat().st_size
    )

    gdf = gpd.read_file(shp)

    if gdf.crs is None:
        raise ValueError(
            "SIGMINE sem sistema de referência."
        )

    gdf = gdf.to_crs(4326)

    colunas = list(gdf.columns)

    coluna_processo = encontrar_coluna(
        colunas,
        [
            "processo",
            "numero"
        ]
    )

    coluna_ano = encontrar_coluna(
        colunas,
        [
            "ano"
        ]
    )

    if coluna_processo:

        if coluna_ano and coluna_ano != coluna_processo:

            gdf["Processo_key"] = [
                criar_chave_processo(p, a)
                for p, a in zip(
                    gdf[coluna_processo],
                    gdf[coluna_ano]
                )
            ]

        else:

            gdf["Processo_key"] = (
                gdf[coluna_processo]
                .map(criar_chave_processo)
            )

        gdf["Processo_fmt"] = (
            gdf["Processo_key"]
            .map(formatar_processo)
        )

    return gdf


# ============================================================
# 14. IDENTIFICAR CAMPOS SIGMINE
# ============================================================

def campos_sigmine(gdf):

    colunas = [
        c for c in gdf.columns
        if c != "geometry"
    ]

    return {
        "municipio": encontrar_coluna(
            colunas,
            [
                "municipio",
                "município",
                "munic"
            ]
        ),

        "substancia": encontrar_coluna(
            colunas,
            [
                "substancia",
                "substância",
                "subst"
            ]
        ),

        "fase": encontrar_coluna(
            colunas,
            [
                "fase"
            ]
        ),

        "titular": encontrar_coluna(
            colunas,
            [
                "titular",
                "razaosocial",
                "nomeempresa"
            ]
        ),

        "area": encontrar_coluna(
            colunas,
            [
                "areaha",
                "area_ha",
                "area"
            ]
        ),

        "evento": encontrar_coluna(
            colunas,
            [
                "ult_evento",
                "ultevento",
                "evento"
            ]
        ),
    }


# ============================================================
# 15. EXPORTAÇÃO GIS
# ============================================================

def preparar_geo_exportacao(gdf):

    geo = gdf.copy()

    # Mantém geometria válida
    geo = geo[
        geo.geometry.notna()
    ].copy()

    geo = geo[
        ~geo.geometry.is_empty
    ].copy()

    # WGS84 é prático para intercâmbio
    if geo.crs is None:
        geo = geo.set_crs(
            4326,
            allow_override=True
        )
    else:
        geo = geo.to_crs(4326)

    # Shapefile possui limitações com tipos complexos
    for coluna in geo.columns:

        if coluna == "geometry":
            continue

        if geo[coluna].dtype == "object":
            geo[coluna] = (
                geo[coluna]
                .astype(str)
                .replace("nan", "")
            )

    return geo


def exportar_geojson(gdf):

    geo = preparar_geo_exportacao(
        gdf
    )

    return geo.to_json().encode(
        "utf-8"
    )


def exportar_kml(gdf):

    geo = preparar_geo_exportacao(
        gdf
    )

    with tempfile.TemporaryDirectory() as pasta:

        caminho = (
            Path(pasta)
            / "processo.kml"
        )

        try:

            geo.to_file(
                caminho,
                driver="KML"
            )

            return caminho.read_bytes()

        except Exception:

            # Fallback simples para KML
            # usando apenas geometrias
            partes = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<kml xmlns="http://www.opengis.net/kml/2.2">',
                "<Document>",
            ]

            for idx, row in geo.iterrows():

                geom = row.geometry

                if geom is None:
                    continue

                nome = (
                    str(
                        row.get(
                            "Processo_fmt",
                            f"Feição {idx + 1}"
                        )
                    )
                )

                if geom.geom_type == "Polygon":

                    coords = " ".join(
                        f"{x},{y},0"
                        for x, y
                        in geom.exterior.coords
                    )

                    partes.extend([
                        "<Placemark>",
                        f"<name>{nome}</name>",
                        "<Polygon>",
                        "<outerBoundaryIs>",
                        "<LinearRing>",
                        f"<coordinates>{coords}</coordinates>",
                        "</LinearRing>",
                        "</outerBoundaryIs>",
                        "</Polygon>",
                        "</Placemark>",
                    ])

                elif geom.geom_type == "MultiPolygon":

                    partes.append(
                        "<Placemark>"
                    )

                    partes.append(
                        f"<name>{nome}</name>"
                    )

                    partes.append(
                        "<MultiGeometry>"
                    )

                    for poligono in geom.geoms:

                        coords = " ".join(
                            f"{x},{y},0"
                            for x, y
                            in poligono.exterior.coords
                        )

                        partes.extend([
                            "<Polygon>",
                            "<outerBoundaryIs>",
                            "<LinearRing>",
                            f"<coordinates>{coords}</coordinates>",
                            "</LinearRing>",
                            "</outerBoundaryIs>",
                            "</Polygon>",
                        ])

                    partes.extend([
                        "</MultiGeometry>",
                        "</Placemark>",
                    ])

            partes.extend([
                "</Document>",
                "</kml>",
            ])

            return "\n".join(
                partes
            ).encode("utf-8")


def exportar_shapefile_zip(gdf, nome_base):

    geo = preparar_geo_exportacao(
        gdf
    )

    with tempfile.TemporaryDirectory() as pasta:

        pasta = Path(pasta)

        shp = pasta / f"{nome_base}.shp"

        # Limpa nomes de campos para maior compatibilidade
        renomear = {}

        usados = set()

        for coluna in geo.columns:

            if coluna == "geometry":
                continue

            novo = (
                unicodedata.normalize(
                    "NFKD",
                    str(coluna)
                )
                .encode(
                    "ascii",
                    "ignore"
                )
                .decode()
                .replace(" ", "_")
            )

            novo = re.sub(
                r"[^A-Za-z0-9_]",
                "",
                novo
            )

            novo = novo[:10]

            original_novo = novo

            contador = 1

            while novo.lower() in usados:

                sufixo = str(contador)

                novo = (
                    original_novo[
                        :10 - len(sufixo)
                    ]
                    + sufixo
                )

                contador += 1

            usados.add(
                novo.lower()
            )

            renomear[coluna] = novo

        geo_shp = geo.rename(
            columns=renomear
        )

        geo_shp.to_file(
            shp,
            driver="ESRI Shapefile",
            encoding="UTF-8"
        )

        buffer = io.BytesIO()

        with zipfile.ZipFile(
            buffer,
            "w",
            zipfile.ZIP_DEFLATED
        ) as z:

            for arquivo in pasta.iterdir():

                if arquivo.is_file():

                    z.write(
                        arquivo,
                        arcname=arquivo.name
                    )

        buffer.seek(0)

        return buffer.getvalue()


# ============================================================
# 16. PLOTLY
# ============================================================

def layout_grafico(
    fig,
    altura=None,
    margem_esquerda=20,
    margem_direita=45
):

    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(
            family="Arial",
            color=TEXTO,
            size=12
        ),
        title=dict(
            font=dict(
                size=17,
                color=TEXTO
            ),
            x=0.02
        ),
        margin=dict(
            l=margem_esquerda,
            r=margem_direita,
            t=62,
            b=30
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor=BORDA,
            font_size=13,
            font_family="Arial"
        ),
        legend_title_text=""
    )

    if altura:
        fig.update_layout(
            height=altura
        )

    fig.update_xaxes(
        showgrid=False,
        linecolor=BORDA,
        zeroline=False
    )

    fig.update_yaxes(
        gridcolor="#EDF1F4",
        linecolor=BORDA,
        zeroline=False
    )

    return fig


def plotar(fig):

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "responsive": True,
        }
    )


# ============================================================
# 17. CARDS
# ============================================================

def mostrar_cards(df, cinco=False):

    total = (
        df["ValorRecolhido"]
        .fillna(0)
        .sum()
    )

    municipios = (
        df["Município"]
        .nunique()
    )

    processos = (
        df["Processo_key"]
        .nunique()
    )

    substancias = (
        df["Substância"]
        .nunique()
    )

    if cinco:

        colunas = st.columns(
            [1, 1, 1, 1, 1.25]
        )

    else:

        colunas = st.columns(4)

    colunas[0].metric(
        "💰 CFEM arrecadada",
        moeda_resumida(total)
    )

    colunas[0].caption(
        "Período selecionado"
    )

    colunas[1].metric(
        "🏙️ Municípios",
        inteiro_br(municipios)
    )

    colunas[1].caption(
        "Com arrecadação"
    )

    colunas[2].metric(
        "⛏️ Processos",
        inteiro_br(processos)
    )

    colunas[2].caption(
        "Com recolhimento de CFEM"
    )

    colunas[3].metric(
        "💎 Substâncias",
        inteiro_br(substancias)
    )

    colunas[3].caption(
        "Registradas na base"
    )

    if cinco:

        ranking = (
            df
            .groupby(
                "Município",
                as_index=False
            )
            ["ValorRecolhido"]
            .sum()
            .sort_values(
                "ValorRecolhido",
                ascending=False
            )
        )

        if not ranking.empty:

            maior = ranking.iloc[0]

            nome = str(
                maior["Município"]
            )

            if len(nome) > 24:
                nome = nome[:22] + "…"

            colunas[4].metric(
                "🏆 Maior arrecadador",
                nome
            )

            colunas[4].caption(
                moeda_resumida(
                    maior["ValorRecolhido"]
                )
            )


# ============================================================
# 18. FILTROS CFEM
# ============================================================

def filtros_cfem(df, prefixo):

    with st.expander(
        "⚙️ Filtros",
        expanded=True
    ):

        c1, c2, c3, c4 = st.columns(
            [1.15, 1.4, 2.1, 2.1]
        )

        anos = sorted(
            df["Ano"]
            .dropna()
            .astype(int)
            .unique()
        )

        anos_sel = c1.multiselect(
            "Ano",
            anos,
            default=anos,
            key=f"{prefixo}_ano"
        )

        meses_disponiveis = sorted(
            df["Mês"]
            .dropna()
            .astype(int)
            .unique()
        )

        nomes_meses = [
            MESES[m]
            for m in meses_disponiveis
        ]

        meses_sel_nome = c2.multiselect(
            "Mês",
            nomes_meses,
            default=nomes_meses,
            key=f"{prefixo}_mes"
        )

        meses_sel = [
            numero
            for numero, nome
            in MESES.items()
            if nome in meses_sel_nome
        ]

        municipios = sorted(
            df["Município"]
            .dropna()
            .unique()
        )

        mun_sel = c3.multiselect(
            "Município",
            municipios,
            placeholder="Todos os municípios",
            key=f"{prefixo}_mun"
        )

        substancias = sorted(
            df["Substância"]
            .dropna()
            .unique()
        )

        subst_sel = c4.multiselect(
            "Substância",
            substancias,
            placeholder="Todas as substâncias",
            key=f"{prefixo}_subst"
        )

    dados = df.copy()

    if anos_sel:
        dados = dados[
            dados["Ano"].isin(
                anos_sel
            )
        ]

    if meses_sel:
        dados = dados[
            dados["Mês"].isin(
                meses_sel
            )
        ]

    if mun_sel:
        dados = dados[
            dados["Município"].isin(
                mun_sel
            )
        ]

    if subst_sel:
        dados = dados[
            dados["Substância"].isin(
                subst_sel
            )
        ]

    return dados


# ============================================================
# 19. MAPA BASE
# ============================================================

def criar_mapa_base(
    centro=(-18.6, -44.2),
    zoom=6
):

    mapa = folium.Map(
        location=centro,
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True
    )

    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/"
            "ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/"
            "{z}/{y}/{x}"
        ),
        attr=(
            "Esri, Maxar, Earthstar Geographics, "
            "and the GIS User Community"
        ),
        name="Satélite — Esri",
        overlay=False,
        control=True,
        show=True,
        max_zoom=19
    ).add_to(mapa)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
        show=False
    ).add_to(mapa)

    return mapa


# ============================================================
# 20. CARREGAMENTO INICIAL
# ============================================================

try:

    with st.spinner(
        "Carregando dados oficiais da ANM..."
    ):

        cfem = load_cfem()

except Exception as erro:

    st.error(
        "Não foi possível carregar a base CFEM da ANM."
    )

    st.exception(erro)

    st.stop()


ANO_MAX_CFEM, MES_MAX_CFEM, ANO_PARCIAL = (
    info_periodo_cfem(cfem)
)


# ============================================================
# 21. SIDEBAR
# ============================================================

st.sidebar.title(
    "⛏️ Mineração MG"
)

st.sidebar.caption(
    "Inteligência mineral e territorial"
)

st.sidebar.divider()

pagina = st.sidebar.radio(
    "Navegação",
    [
        "📊 Visão Geral",
        "💰 CFEM",
        "🗺️ Mapa Minerário",
        "🏙️ Municípios",
        "🔎 Processos",
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "FONTES OFICIAIS"
)

st.sidebar.write(
    "ANM • CFEM • SIGMINE • SCM"
)

if (
    ANO_MAX_CFEM
    and MES_MAX_CFEM
):

    st.sidebar.caption(
        f"CFEM disponível até "
        f"{MESES_LONGOS[MES_MAX_CFEM]}/"
        f"{ANO_MAX_CFEM}"
    )

st.sidebar.caption(
    "Cache das bases: 6 horas"
)

if st.sidebar.button(
    "🔄 Recarregar bases ANM",
    use_container_width=True
):

    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()


# ============================================================
# 22. CABEÇALHO
# ============================================================

st.title(
    "⛏️ Painel da Mineração | Minas Gerais"
)

st.caption(
    "CFEM • Processos minerários • "
    "Inteligência territorial • "
    "Fontes oficiais da Agência Nacional de Mineração"
)

if (
    ANO_PARCIAL
    and ANO_MAX_CFEM
    and MES_MAX_CFEM
):

    st.info(
        f"📅 Os dados de {ANO_MAX_CFEM} são parciais. "
        f"A base possui arrecadação registrada até "
        f"{MESES_LONGOS[MES_MAX_CFEM]} de {ANO_MAX_CFEM}."
    )

st.divider()


# ============================================================
# 23. VISÃO GERAL
# ============================================================

if pagina == "📊 Visão Geral":

    st.header(
        "Visão Geral"
    )

    st.caption(
        "Panorama da arrecadação da CFEM "
        "e da atividade mineral em Minas Gerais."
    )

    dados = filtros_cfem(
        cfem,
        "geral"
    )

    mostrar_cards(
        dados,
        cinco=True
    )

    st.write("")

    # --------------------------------------------------------
    # EVOLUÇÃO ANUAL
    # --------------------------------------------------------

    esquerda, direita = st.columns(
        [1.05, 1]
    )

    anual = (
        dados
        .groupby(
            "Ano",
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .sort_values("Ano")
    )

    anual["AnoLabel"] = (
        anual["Ano"]
        .astype(int)
        .astype(str)
    )

    if (
        ANO_PARCIAL
        and ANO_MAX_CFEM in anual["Ano"].values
    ):

        anual.loc[
            anual["Ano"] == ANO_MAX_CFEM,
            "AnoLabel"
        ] = (
            str(ANO_MAX_CFEM)
            + "*"
        )

    anual["Rotulo"] = (
        anual["ValorRecolhido"]
        .map(moeda_resumida)
    )

    anual["Hover"] = (
        anual["ValorRecolhido"]
        .map(moeda)
    )

    fig_anual = px.bar(
        anual,
        x="AnoLabel",
        y="ValorRecolhido",
        text="Rotulo",
        custom_data=["Hover"],
        title="Evolução anual da CFEM"
    )

    fig_anual.update_traces(
        marker_color=AZUL_MEDIO,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>Ano %{x}</b><br>"
            "CFEM arrecadada: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    fig_anual.update_xaxes(
        title=None
    )

    fig_anual.update_yaxes(
        title=None,
        tickformat=".2s"
    )

    layout_grafico(
        fig_anual,
        altura=440
    )

    esquerda.plotly_chart(
        fig_anual,
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # --------------------------------------------------------
    # TOP MUNICÍPIOS
    # --------------------------------------------------------

    ranking_mun = (
        dados
        .groupby(
            "Município",
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .nlargest(
            10,
            "ValorRecolhido"
        )
        .sort_values(
            "ValorRecolhido"
        )
    )

    ranking_mun["Rotulo"] = (
        ranking_mun["ValorRecolhido"]
        .map(moeda_resumida)
    )

    ranking_mun["Hover"] = (
        ranking_mun["ValorRecolhido"]
        .map(moeda)
    )

    fig_mun = px.bar(
        ranking_mun,
        x="ValorRecolhido",
        y="Município",
        orientation="h",
        text="Rotulo",
        custom_data=["Hover"],
        title="10 maiores municípios arrecadadores"
    )

    fig_mun.update_traces(
        marker_color=AZUL,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "CFEM arrecadada: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    fig_mun.update_xaxes(
        title=None,
        showticklabels=False,
        range=[
            0,
            ranking_mun["ValorRecolhido"].max()
            * 1.28
        ]
    )

    fig_mun.update_yaxes(
        title=None
    )

    layout_grafico(
        fig_mun,
        altura=440,
        margem_esquerda=25,
        margem_direita=60
    )

    direita.plotly_chart(
        fig_mun,
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # --------------------------------------------------------
    # SUBSTÂNCIAS
    # --------------------------------------------------------

    st.subheader(
        "Principais substâncias minerais"
    )

    total_cfem = (
        dados["ValorRecolhido"]
        .fillna(0)
        .sum()
    )

    substancias = (
        dados
        .groupby(
            "Substância",
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .nlargest(
            10,
            "ValorRecolhido"
        )
        .sort_values(
            "ValorRecolhido"
        )
    )

    if total_cfem > 0:

        substancias["Participacao"] = (
            substancias["ValorRecolhido"]
            / total_cfem
            * 100
        )

    else:
        substancias["Participacao"] = 0

    substancias["Rotulo"] = (
        substancias["ValorRecolhido"]
        .map(moeda_resumida)
        + "  •  "
        + substancias["Participacao"]
        .map(percentual_br)
    )

    substancias["Hover"] = (
        substancias["ValorRecolhido"]
        .map(moeda)
    )

    fig_sub = px.bar(
        substancias,
        x="ValorRecolhido",
        y="Substância",
        orientation="h",
        text="Rotulo",
        custom_data=[
            "Hover",
            "Participacao"
        ]
    )

    fig_sub.update_traces(
        marker_color=VERDE,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "CFEM: %{customdata[0]}<br>"
            "Participação: %{customdata[1]:.1f}%"
            "<extra></extra>"
        )
    )

    maior_sub = (
        substancias["ValorRecolhido"].max()
        if not substancias.empty
        else 1
    )

    fig_sub.update_xaxes(
        title=None,
        showticklabels=False,
        range=[
            0,
            maior_sub * 1.28
        ]
    )

    fig_sub.update_yaxes(
        title=None
    )

    layout_grafico(
        fig_sub,
        altura=500,
        margem_esquerda=25,
        margem_direita=80
    )

    plotar(fig_sub)

    if ANO_PARCIAL:

        st.caption(
            f"* {ANO_MAX_CFEM}: dados parciais até "
            f"{MESES_LONGOS[MES_MAX_CFEM]}."
        )


# ============================================================
# 24. CFEM
# ============================================================

elif pagina == "💰 CFEM":

    st.header(
        "CFEM"
    )

    st.caption(
        "Consulta e análise da Compensação Financeira "
        "pela Exploração Mineral em Minas Gerais."
    )

    dados = filtros_cfem(
        cfem,
        "cfem"
    )

    processo = st.text_input(
        "Processo minerário",
        placeholder="Ex.: 832.776/2009"
    )

    if processo:

        chave = criar_chave_processo(
            processo
        )

        dados = dados[
            dados["Processo_key"] == chave
        ]

    mostrar_cards(dados)

    st.write("")

    modo = st.radio(
        "Visualização temporal",
        [
            "Mensal",
            "Anual",
            "Acumulado"
        ],
        horizontal=True
    )

    # --------------------------------------------------------
    # ANUAL
    # --------------------------------------------------------

    if modo == "Anual":

        temporal = (
            dados
            .groupby(
                "Ano",
                as_index=False
            )
            ["ValorRecolhido"]
            .sum()
            .sort_values("Ano")
        )

        temporal["AnoLabel"] = (
            temporal["Ano"]
            .astype(int)
            .astype(str)
        )

        if ANO_PARCIAL:

            temporal.loc[
                temporal["Ano"] == ANO_MAX_CFEM,
                "AnoLabel"
            ] = (
                str(ANO_MAX_CFEM)
                + "*"
            )

        temporal["Hover"] = (
            temporal["ValorRecolhido"]
            .map(moeda)
        )

        fig = px.line(
            temporal,
            x="AnoLabel",
            y="ValorRecolhido",
            markers=True,
            custom_data=["Hover"],
            title="Evolução anual da CFEM"
        )

        fig.update_traces(
            line_color=AZUL,
            marker_color=AZUL_MEDIO,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "CFEM arrecadada: %{customdata[0]}"
                "<extra></extra>"
            )
        )

        fig.update_xaxes(
            title=None
        )

    # --------------------------------------------------------
    # MENSAL / ACUMULADO
    # --------------------------------------------------------

    else:

        temporal = (
            dados
            .groupby(
                ["Ano", "Mês"],
                as_index=False
            )
            ["ValorRecolhido"]
            .sum()
            .dropna()
        )

        # Remove meses sem arrecadação.
        # Assim meses ainda não publicados não aparecem como zero.
        temporal = temporal[
            temporal["ValorRecolhido"] > 0
        ].copy()

        if not temporal.empty:

            temporal["Data"] = pd.to_datetime(
                dict(
                    year=temporal["Ano"].astype(int),
                    month=temporal["Mês"].astype(int),
                    day=1
                )
            )

            temporal = temporal.sort_values(
                "Data"
            )

            if modo == "Acumulado":

                temporal["ValorGrafico"] = (
                    temporal["ValorRecolhido"]
                    .cumsum()
                )

            else:

                temporal["ValorGrafico"] = (
                    temporal["ValorRecolhido"]
                )

            temporal["Hover"] = (
                temporal["ValorGrafico"]
                .map(moeda)
            )

            temporal["MesAno"] = (
                temporal["Mês"]
                .map(MESES_LONGOS)
                + "/"
                + temporal["Ano"]
                .astype(int)
                .astype(str)
            )

            fig = px.line(
                temporal,
                x="Data",
                y="ValorGrafico",
                markers=True,
                custom_data=[
                    "Hover",
                    "MesAno"
                ],
                title=(
                    "Evolução "
                    + modo.lower()
                    + " da CFEM"
                )
            )

            fig.update_traces(
                line_color=AZUL,
                marker_color=AZUL_MEDIO,
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "CFEM arrecadada: %{customdata[0]}"
                    "<extra></extra>"
                )
            )

            fig.update_xaxes(
                title=None
            )

        else:

            fig = px.line(
                title="Sem dados para o filtro selecionado"
            )

    fig.update_yaxes(
        title=None,
        tickformat=".2s"
    )

    layout_grafico(
        fig,
        altura=470
    )

    plotar(fig)

    # --------------------------------------------------------
    # COMPARAÇÃO MENSAL
    # --------------------------------------------------------

    comparacao = (
        dados
        .groupby(
            ["Mês", "Ano"],
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
    )

    comparacao = comparacao[
        comparacao["ValorRecolhido"] > 0
    ].copy()

    if not comparacao.empty:

        comparacao["Ano"] = (
            comparacao["Ano"]
            .astype(int)
            .astype(str)
        )

        comparacao["MesNome"] = (
            comparacao["Mês"]
            .map(MESES)
        )

        comparacao["Hover"] = (
            comparacao["ValorRecolhido"]
            .map(moeda)
        )

        fig_comp = px.line(
            comparacao,
            x="Mês",
            y="ValorRecolhido",
            color="Ano",
            markers=True,
            custom_data=[
                "Hover",
                "MesNome"
            ],
            title="Comparação mensal entre anos"
        )

        fig_comp.update_traces(
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "CFEM: %{customdata[0]}"
                "<extra></extra>"
            )
        )

        fig_comp.update_xaxes(
            title=None,
            tickmode="array",
            tickvals=list(
                MESES.keys()
            ),
            ticktext=list(
                MESES.values()
            )
        )

        fig_comp.update_yaxes(
            title=None,
            tickformat=".2s"
        )

        layout_grafico(
            fig_comp,
            altura=470
        )

        plotar(fig_comp)

    # --------------------------------------------------------
    # MUNICÍPIO X ANO
    # --------------------------------------------------------

    st.subheader(
        "Arrecadação por município e ano"
    )

    pivot = dados.pivot_table(
        index="Município",
        columns="Ano",
        values="ValorRecolhido",
        aggfunc="sum",
        fill_value=0
    )

    pivot["Total"] = (
        pivot.sum(axis=1)
    )

    pivot = (
        pivot
        .sort_values(
            "Total",
            ascending=False
        )
        .reset_index()
    )

    pivot_formatada = (
        pivot.copy()
    )

    for coluna in pivot_formatada.columns:

        if coluna != "Município":

            pivot_formatada[coluna] = (
                pivot_formatada[coluna]
                .map(moeda)
            )

    st.dataframe(
        pivot_formatada,
        use_container_width=True,
        hide_index=True,
        height=400
    )

    # --------------------------------------------------------
    # DETALHAMENTO
    # --------------------------------------------------------

    st.subheader(
        "Dados detalhados"
    )

    colunas = [
        c for c in [
            "Ano",
            "Mês",
            "Processo_fmt",
            "Município",
            "Substância",
            "QuantidadeComercializada",
            "UnidadeDeMedida",
            "ValorRecolhido"
        ]
        if c in dados.columns
    ]

    detalhes = (
        dados[colunas]
        .copy()
    )

    detalhes = detalhes.rename(
        columns={
            "Processo_fmt": "Processo",
            "QuantidadeComercializada":
                "Quantidade comercializada",
            "UnidadeDeMedida": "Unidade",
            "ValorRecolhido":
                "CFEM arrecadada",
        }
    )

    if "Mês" in detalhes.columns:

        detalhes["Mês"] = (
            detalhes["Mês"]
            .map(MESES)
        )

    if (
        "Quantidade comercializada"
        in detalhes.columns
    ):

        detalhes[
            "Quantidade comercializada"
        ] = (
            detalhes[
                "Quantidade comercializada"
            ]
            .map(
                lambda x: numero_br(
                    x,
                    2
                )
            )
        )

    if "CFEM arrecadada" in detalhes.columns:

        detalhes["CFEM arrecadada"] = (
            detalhes["CFEM arrecadada"]
            .map(moeda)
        )

    st.dataframe(
        detalhes,
        use_container_width=True,
        hide_index=True,
        height=450
    )

    csv = (
        dados.to_csv(
            index=False,
            sep=";",
            decimal=","
        )
        .encode("utf-8-sig")
    )

    st.download_button(
        "⬇️ Baixar consulta em CSV",
        csv,
        "consulta_cfem_mg.csv",
        "text/csv"
    )


# ============================================================
# 25. MAPA MINERÁRIO
# ============================================================

elif pagina == "🗺️ Mapa Minerário":

    st.header(
        "Mapa Minerário"
    )

    st.caption(
        "Consulta espacial dos processos minerários "
        "de Minas Gerais a partir do SIGMINE/ANM."
    )

    try:

        with st.spinner(
            "Carregando poligonais do SIGMINE..."
        ):

            sigmine = load_sigmine()

        campos = campos_sigmine(
            sigmine
        )

        mapa_dados = sigmine.copy()

        # ----------------------------------------------------
        # FILTROS
        # ----------------------------------------------------

        with st.expander(
            "⚙️ Filtros do mapa",
            expanded=True
        ):

            f1, f2, f3 = st.columns(3)

            f4, f5 = st.columns(
                [2, 1]
            )

            # Município
            if campos["municipio"]:

                opcoes = sorted(
                    mapa_dados[
                        campos["municipio"]
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                municipio = f1.selectbox(
                    "Município",
                    ["Todos"] + opcoes
                )

                if municipio != "Todos":

                    mapa_dados = mapa_dados[
                        mapa_dados[
                            campos["municipio"]
                        ].astype(str)
                        == municipio
                    ]

            else:

                f1.caption(
                    "Município não disponível "
                    "diretamente no shapefile."
                )

            # Substância
            if campos["substancia"]:

                opcoes = sorted(
                    mapa_dados[
                        campos["substancia"]
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                substancia = f2.selectbox(
                    "Substância",
                    ["Todas"] + opcoes
                )

                if substancia != "Todas":

                    mapa_dados = mapa_dados[
                        mapa_dados[
                            campos["substancia"]
                        ].astype(str)
                        == substancia
                    ]

            else:

                f2.caption(
                    "Substância não disponível "
                    "diretamente no shapefile."
                )

            # Fase
            if campos["fase"]:

                opcoes = sorted(
                    mapa_dados[
                        campos["fase"]
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                fase = f3.selectbox(
                    "Fase processual",
                    ["Todas"] + opcoes
                )

                if fase != "Todas":

                    mapa_dados = mapa_dados[
                        mapa_dados[
                            campos["fase"]
                        ].astype(str)
                        == fase
                    ]

            # Titular
            if campos["titular"]:

                titulares = sorted(
                    mapa_dados[
                        campos["titular"]
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                titular = f4.selectbox(
                    "Titular",
                    ["Todos"] + titulares
                )

                if titular != "Todos":

                    mapa_dados = mapa_dados[
                        mapa_dados[
                            campos["titular"]
                        ].astype(str)
                        == titular
                    ]

            else:

                f4.caption(
                    "Titular não disponível "
                    "diretamente no shapefile."
                )

            processo_mapa = (
                f5.text_input(
                    "Processo",
                    placeholder="830.195/2006"
                )
            )

            if processo_mapa:

                chave_mapa = (
                    criar_chave_processo(
                        processo_mapa
                    )
                )

                mapa_dados = mapa_dados[
                    mapa_dados[
                        "Processo_key"
                    ] == chave_mapa
                ]

        somente_cfem = st.checkbox(
            "Mostrar somente processos encontrados na CFEM"
        )

        if somente_cfem:

            processos_cfem = set(
                cfem["Processo_key"]
            )

            mapa_dados = mapa_dados[
                mapa_dados[
                    "Processo_key"
                ].isin(
                    processos_cfem
                )
            ]

        # ----------------------------------------------------
        # KPIs MAPA
        # ----------------------------------------------------

        mc1, mc2, mc3, mc4 = (
            st.columns(4)
        )

        mc1.metric(
            "⛏️ Processos",
            inteiro_br(
                mapa_dados[
                    "Processo_key"
                ].nunique()
            )
        )

        if campos["titular"]:

            mc2.metric(
                "🏢 Titulares",
                inteiro_br(
                    mapa_dados[
                        campos["titular"]
                    ].nunique()
                )
            )

        else:
            mc2.metric(
                "🏢 Titulares",
                "-"
            )

        if campos["substancia"]:

            mc3.metric(
                "💎 Substâncias",
                inteiro_br(
                    mapa_dados[
                        campos["substancia"]
                    ].nunique()
                )
            )

        else:
            mc3.metric(
                "💎 Substâncias",
                "-"
            )

        if campos["area"]:

            areas = pd.to_numeric(
                mapa_dados[
                    campos["area"]
                ],
                errors="coerce"
            )

            mc4.metric(
                "📐 Área das feições",
                (
                    numero_br(
                        areas.sum(),
                        2
                    )
                    + " ha"
                )
            )

        else:
            mc4.metric(
                "📐 Área",
                "-"
            )

        # ----------------------------------------------------
        # PERFORMANCE
        # ----------------------------------------------------

        LIMITE_MAPA = 12000
        total_encontrado = len(mapa_dados)

        if total_encontrado > LIMITE_MAPA:

            mapa_exibicao = (
                mapa_dados.sample(
                    LIMITE_MAPA,
                    random_state=42
                )
                .copy()
            )

            st.info(
                f"Foram encontrados {inteiro_br(total_encontrado)} processos/feições "
                f"para os filtros atuais. Para preservar o desempenho do WebGIS, "
                f"{inteiro_br(len(mapa_exibicao))} feições estão renderizadas no mapa. "
                "Os indicadores continuam considerando o conjunto completo. "
                "Use município, fase, substância ou número do processo para detalhar."
            )

        else:

            mapa_exibicao = (
                mapa_dados.copy()
            )

        if mapa_exibicao.empty:

            st.warning(
                "Nenhum processo encontrado "
                "para os filtros selecionados."
            )

        else:

            # ------------------------------------------------
            # CENTRO
            # ------------------------------------------------

            if len(mapa_exibicao) <= 200:

                bounds = (
                    mapa_exibicao
                    .total_bounds
                )

                centro = (
                    (
                        bounds[1]
                        + bounds[3]
                    ) / 2,
                    (
                        bounds[0]
                        + bounds[2]
                    ) / 2
                )

                zoom = 9

            else:

                centro = (
                    -18.6,
                    -44.2
                )

                zoom = 6

            mapa = criar_mapa_base(
                centro,
                zoom
            )

            # ------------------------------------------------
            # TOOLTIP
            # ------------------------------------------------

            tooltip_campos = []
            tooltip_aliases = []

            if "Processo_fmt" in mapa_exibicao:

                tooltip_campos.append(
                    "Processo_fmt"
                )

                tooltip_aliases.append(
                    "Processo:"
                )

            for chave_campo, titulo in [
                ("fase", "Fase:"),
                ("substancia", "Substância:"),
                ("titular", "Titular:"),
                ("municipio", "Município:"),
                ("area", "Área (ha):"),
            ]:

                coluna = campos.get(
                    chave_campo
                )

                if (
                    coluna
                    and coluna
                    in mapa_exibicao.columns
                ):

                    tooltip_campos.append(
                        coluna
                    )

                    tooltip_aliases.append(
                        titulo
                    )

            tooltip = None

            if tooltip_campos:

                tooltip = folium.GeoJsonTooltip(
                    fields=tooltip_campos,
                    aliases=tooltip_aliases,
                    sticky=True,
                    labels=True
                )

            folium.GeoJson(
                mapa_exibicao.to_json(),
                name="Processos minerários",
                style_function=lambda feature: {
                    "color": AZUL,
                    "weight": 1.1,
                    "fillColor": AZUL_MEDIO,
                    "fillOpacity": 0.20,
                },
                highlight_function=lambda feature: {
                    "color": DOURADO,
                    "weight": 3,
                    "fillColor": DOURADO,
                    "fillOpacity": 0.35,
                },
                tooltip=tooltip
            ).add_to(mapa)

            folium.LayerControl(
                collapsed=False
            ).add_to(mapa)

            Fullscreen(
                position="topright",
                title="Tela cheia",
                title_cancel="Sair da tela cheia"
            ).add_to(mapa)

            st_folium(
                mapa,
                use_container_width=True,
                height=700
            )

            # ------------------------------------------------
            # DOWNLOAD QUANDO HOUVER PROCESSO
            # ------------------------------------------------

            if processo_mapa:

                geo_processo = (
                    mapa_dados.copy()
                )

                if not geo_processo.empty:

                    st.subheader(
                        "📦 Exportar polígono do processo"
                    )

                    st.caption(
                        "Arquivos preparados em WGS 84 "
                        "(EPSG:4326), compatíveis com QGIS."
                    )

                    nome_limpo = (
                        "processo_"
                        + chave_mapa[:-4]
                        + "_"
                        + chave_mapa[-4:]
                    )

                    d1, d2, d3 = (
                        st.columns(3)
                    )

                    try:

                        shp_zip = (
                            exportar_shapefile_zip(
                                geo_processo,
                                nome_limpo
                            )
                        )

                        d1.download_button(
                            "📦 Shapefile ZIP",
                            data=shp_zip,
                            file_name=(
                                nome_limpo
                                + ".zip"
                            ),
                            mime="application/zip",
                            use_container_width=True
                        )

                    except Exception as erro:

                        d1.warning(
                            "Não foi possível "
                            "gerar o Shapefile."
                        )

                    try:

                        geojson = (
                            exportar_geojson(
                                geo_processo
                            )
                        )

                        d2.download_button(
                            "🌐 GeoJSON",
                            data=geojson,
                            file_name=(
                                nome_limpo
                                + ".geojson"
                            ),
                            mime="application/geo+json",
                            use_container_width=True
                        )

                    except Exception:

                        d2.warning(
                            "Não foi possível "
                            "gerar o GeoJSON."
                        )

                    try:

                        kml = exportar_kml(
                            geo_processo
                        )

                        d3.download_button(
                            "🌍 KML",
                            data=kml,
                            file_name=(
                                nome_limpo
                                + ".kml"
                            ),
                            mime=(
                                "application/vnd."
                                "google-earth.kml+xml"
                            ),
                            use_container_width=True
                        )

                    except Exception:

                        d3.warning(
                            "Não foi possível "
                            "gerar o KML."
                        )

    except Exception as erro:

        st.error(
            "Não foi possível carregar o SIGMINE."
        )

        st.exception(erro)


# ============================================================
# 26. MUNICÍPIOS
# ============================================================

elif pagina == "🏙️ Municípios":

    st.header(
        "Perfil Mineral Municipal"
    )

    st.caption(
        "Indicadores de CFEM e perfil da atividade "
        "mineral por município."
    )

    municipios = sorted(
        cfem["Município"]
        .dropna()
        .unique()
    )

    municipio = st.selectbox(
        "Município",
        municipios
    )

    dados = cfem[
        cfem["Município"] == municipio
    ].copy()

    st.subheader(
        municipio
    )

    mostrar_cards(
        dados
    )

    st.write("")

    c1, c2 = st.columns(2)

    # --------------------------------------------------------
    # ANUAL
    # --------------------------------------------------------

    anual = (
        dados
        .groupby(
            "Ano",
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .sort_values("Ano")
    )

    anual["AnoLabel"] = (
        anual["Ano"]
        .astype(int)
        .astype(str)
    )

    if ANO_PARCIAL:

        anual.loc[
            anual["Ano"] == ANO_MAX_CFEM,
            "AnoLabel"
        ] = (
            str(ANO_MAX_CFEM)
            + "*"
        )

    anual["Rotulo"] = (
        anual["ValorRecolhido"]
        .map(moeda_resumida)
    )

    anual["Hover"] = (
        anual["ValorRecolhido"]
        .map(moeda)
    )

    fig = px.bar(
        anual,
        x="AnoLabel",
        y="ValorRecolhido",
        text="Rotulo",
        custom_data=["Hover"],
        title=(
            "CFEM por ano — "
            + municipio
        )
    )

    fig.update_traces(
        marker_color=AZUL_MEDIO,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "CFEM: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    fig.update_xaxes(
        title=None
    )

    fig.update_yaxes(
        title=None,
        showticklabels=False
    )

    layout_grafico(
        fig,
        altura=440
    )

    c1.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # --------------------------------------------------------
    # SUBSTÂNCIAS
    # --------------------------------------------------------

    subst = (
        dados
        .groupby(
            "Substância",
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .nlargest(
            8,
            "ValorRecolhido"
        )
        .sort_values(
            "ValorRecolhido"
        )
    )

    subst["Rotulo"] = (
        subst["ValorRecolhido"]
        .map(moeda_resumida)
    )

    subst["Hover"] = (
        subst["ValorRecolhido"]
        .map(moeda)
    )

    fig = px.bar(
        subst,
        x="ValorRecolhido",
        y="Substância",
        orientation="h",
        text="Rotulo",
        custom_data=["Hover"],
        title="Principais substâncias"
    )

    fig.update_traces(
        marker_color=VERDE,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "CFEM: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    maior = (
        subst["ValorRecolhido"].max()
        if not subst.empty
        else 1
    )

    fig.update_xaxes(
        title=None,
        showticklabels=False,
        range=[
            0,
            maior * 1.30
        ]
    )

    fig.update_yaxes(
        title=None
    )

    layout_grafico(
        fig,
        altura=440,
        margem_direita=70
    )

    c2.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # --------------------------------------------------------
    # PROCESSOS
    # --------------------------------------------------------

    st.subheader(
        "Processos com arrecadação"
    )

    processos = (
        dados
        .groupby(
            [
                "Processo_fmt",
                "Substância"
            ],
            as_index=False
        )
        ["ValorRecolhido"]
        .sum()
        .sort_values(
            "ValorRecolhido",
            ascending=False
        )
    )

    processos = processos.rename(
        columns={
            "Processo_fmt":
                "Processo",
            "ValorRecolhido":
                "CFEM arrecadada"
        }
    )

    processos[
        "CFEM arrecadada"
    ] = (
        processos[
            "CFEM arrecadada"
        ]
        .map(moeda)
    )

    st.dataframe(
        processos,
        use_container_width=True,
        hide_index=True,
        height=400
    )


# ============================================================
# 27. PROCESSOS
# ============================================================

elif pagina == "🔎 Processos":

    st.header(
        "Consulta Integrada de Processo"
    )

    st.caption(
        "Ficha técnica integrando CFEM, SIGMINE, "
        "SCM e geometria do processo minerário."
    )

    processo_digitado = st.text_input(
        "Número do processo",
        placeholder="Ex.: 830.195/2006"
    )

    if not processo_digitado:

        st.info(
            "Digite o número de um processo "
            "para iniciar a consulta."
        )

    else:

        chave = criar_chave_processo(
            processo_digitado
        )

        processo_formatado = (
            formatar_processo(
                chave
            )
        )

        st.subheader(
            f"Processo {processo_formatado}"
        )

        aba_ficha, aba_cfem, aba_scm = (
            st.tabs(
                [
                    "🗺️ Ficha e localização",
                    "💰 CFEM",
                    "📑 SCM / títulos"
                ]
            )
        )

        # ====================================================
        # FICHA + SIGMINE
        # ====================================================

        with aba_ficha:

            try:

                with st.spinner(
                    "Consultando SIGMINE..."
                ):

                    sigmine = load_sigmine()

                geo = sigmine[
                    sigmine[
                        "Processo_key"
                    ] == chave
                ].copy()

                if geo.empty:

                    st.info(
                        "Processo não encontrado "
                        "no SIGMINE de Minas Gerais."
                    )

                else:

                    st.success(
                        "Processo localizado no SIGMINE."
                    )

                    campos = campos_sigmine(
                        geo
                    )

                    primeira = geo.iloc[0]

                    # ----------------------------------------
                    # FICHA
                    # ----------------------------------------

                    ficha = []

                    ficha.append(
                        {
                            "Informação": "Processo",
                            "Valor": processo_formatado
                        }
                    )

                    if campos["fase"]:

                        ficha.append(
                            {
                                "Informação": "Fase",
                                "Valor": str(
                                    primeira[
                                        campos["fase"]
                                    ]
                                )
                            }
                        )

                    if campos["area"]:

                        area_val = pd.to_numeric(
                            pd.Series([
                                primeira[
                                    campos["area"]
                                ]
                            ]),
                            errors="coerce"
                        ).iloc[0]

                        ficha.append(
                            {
                                "Informação": "Área",
                                "Valor": (
                                    area_br(
                                        area_val
                                    )
                                    if pd.notna(area_val)
                                    else "-"
                                )
                            }
                        )

                    if campos["substancia"]:

                        ficha.append(
                            {
                                "Informação":
                                    "Substância",
                                "Valor": str(
                                    primeira[
                                        campos[
                                            "substancia"
                                        ]
                                    ]
                                )
                            }
                        )

                    if campos["titular"]:

                        ficha.append(
                            {
                                "Informação":
                                    "Titular",
                                "Valor": str(
                                    primeira[
                                        campos[
                                            "titular"
                                        ]
                                    ]
                                )
                            }
                        )

                    if campos["municipio"]:

                        ficha.append(
                            {
                                "Informação":
                                    "Município",
                                "Valor": str(
                                    primeira[
                                        campos[
                                            "municipio"
                                        ]
                                    ]
                                )
                            }
                        )

                    if campos["evento"]:

                        ficha.append(
                            {
                                "Informação":
                                    "Último evento",
                                "Valor": str(
                                    primeira[
                                        campos[
                                            "evento"
                                        ]
                                    ]
                                )
                            }
                        )

                    st.subheader(
                        "Ficha cadastral"
                    )

                    st.dataframe(
                        pd.DataFrame(ficha),
                        use_container_width=True,
                        hide_index=True
                    )

                    # ----------------------------------------
                    # MAPA
                    # ----------------------------------------

                    bounds = geo.total_bounds

                    centro = (
                        (
                            bounds[1]
                            + bounds[3]
                        ) / 2,
                        (
                            bounds[0]
                            + bounds[2]
                        ) / 2
                    )

                    mapa = criar_mapa_base(
                        centro,
                        12
                    )

                    tooltip_campos = [
                        "Processo_fmt"
                    ]

                    tooltip_aliases = [
                        "Processo:"
                    ]

                    for chave_campo, titulo in [
                        ("fase", "Fase:"),
                        ("substancia", "Substância:"),
                        ("titular", "Titular:"),
                        ("municipio", "Município:"),
                        ("area", "Área (ha):"),
                    ]:

                        coluna = campos.get(
                            chave_campo
                        )

                        if (
                            coluna
                            and coluna
                            in geo.columns
                        ):

                            tooltip_campos.append(
                                coluna
                            )

                            tooltip_aliases.append(
                                titulo
                            )

                    tooltip = (
                        folium.GeoJsonTooltip(
                            fields=tooltip_campos,
                            aliases=tooltip_aliases,
                            sticky=True
                        )
                    )

                    folium.GeoJson(
                        geo.to_json(),
                        name="Processo minerário",
                        style_function=lambda feature: {
                            "color": DOURADO,
                            "weight": 4,
                            "fillColor": DOURADO,
                            "fillOpacity": 0.32,
                        },
                        highlight_function=lambda feature: {
                            "color": "#FFD166",
                            "weight": 5,
                            "fillOpacity": 0.42,
                        },
                        tooltip=tooltip
                    ).add_to(mapa)

                    folium.LayerControl(
                        collapsed=False
                    ).add_to(mapa)

                    Fullscreen(
                        position="topright"
                    ).add_to(mapa)

                    st_folium(
                        mapa,
                        use_container_width=True,
                        height=620
                    )

                    # ----------------------------------------
                    # EXPORTAÇÃO
                    # ----------------------------------------

                    st.subheader(
                        "📦 Exportar geometria"
                    )

                    st.caption(
                        "Baixe somente a poligonal deste "
                        "processo para utilização no QGIS, "
                        "ArcGIS ou Google Earth. "
                        "Sistema de referência: WGS 84 "
                        "(EPSG:4326)."
                    )

                    nome_base = (
                        "processo_"
                        + chave[:-4]
                        + "_"
                        + chave[-4:]
                    )

                    d1, d2, d3 = (
                        st.columns(3)
                    )

                    try:

                        shp = (
                            exportar_shapefile_zip(
                                geo,
                                nome_base
                            )
                        )

                        d1.download_button(
                            "📦 Baixar Shapefile ZIP",
                            data=shp,
                            file_name=(
                                nome_base
                                + ".zip"
                            ),
                            mime="application/zip",
                            use_container_width=True
                        )

                    except Exception:

                        d1.warning(
                            "Shapefile indisponível."
                        )

                    try:

                        geojson = (
                            exportar_geojson(
                                geo
                            )
                        )

                        d2.download_button(
                            "🌐 Baixar GeoJSON",
                            data=geojson,
                            file_name=(
                                nome_base
                                + ".geojson"
                            ),
                            mime="application/geo+json",
                            use_container_width=True
                        )

                    except Exception:

                        d2.warning(
                            "GeoJSON indisponível."
                        )

                    try:

                        kml = (
                            exportar_kml(
                                geo
                            )
                        )

                        d3.download_button(
                            "🌍 Baixar KML",
                            data=kml,
                            file_name=(
                                nome_base
                                + ".kml"
                            ),
                            mime=(
                                "application/vnd."
                                "google-earth.kml+xml"
                            ),
                            use_container_width=True
                        )

                    except Exception:

                        d3.warning(
                            "KML indisponível."
                        )

                    # ----------------------------------------
                    # ATRIBUTOS COMPLETOS
                    # ----------------------------------------

                    with st.expander(
                        "Ver atributos completos do SIGMINE"
                    ):

                        atributos = (
                            geo.drop(
                                columns=["geometry"],
                                errors="ignore"
                            )
                        )

                        st.dataframe(
                            atributos,
                            use_container_width=True,
                            hide_index=True
                        )

            except Exception as erro:

                st.error(
                    "Não foi possível consultar "
                    "o SIGMINE."
                )

                st.exception(erro)

        # ====================================================
        # CFEM DO PROCESSO
        # ====================================================

        with aba_cfem:

            resultado = cfem[
                cfem[
                    "Processo_key"
                ] == chave
            ].copy()

            if resultado.empty:

                st.info(
                    "Não foram encontrados registros "
                    "de CFEM para este processo no "
                    "período disponível."
                )

            else:

                total = (
                    resultado[
                        "ValorRecolhido"
                    ]
                    .fillna(0)
                    .sum()
                )

                c1, c2, c3, c4 = (
                    st.columns(4)
                )

                c1.metric(
                    "💰 CFEM",
                    moeda_resumida(total)
                )

                c2.metric(
                    "🏙️ Municípios",
                    inteiro_br(
                        resultado[
                            "Município"
                        ].nunique()
                    )
                )

                c3.metric(
                    "💎 Substâncias",
                    inteiro_br(
                        resultado[
                            "Substância"
                        ].nunique()
                    )
                )

                c4.metric(
                    "📅 Registros",
                    inteiro_br(
                        len(resultado)
                    )
                )

                anual = (
                    resultado
                    .groupby(
                        "Ano",
                        as_index=False
                    )
                    ["ValorRecolhido"]
                    .sum()
                )

                anual["AnoLabel"] = (
                    anual["Ano"]
                    .astype(int)
                    .astype(str)
                )

                if ANO_PARCIAL:

                    anual.loc[
                        anual["Ano"]
                        == ANO_MAX_CFEM,
                        "AnoLabel"
                    ] = (
                        str(ANO_MAX_CFEM)
                        + "*"
                    )

                anual["Rotulo"] = (
                    anual[
                        "ValorRecolhido"
                    ]
                    .map(moeda_resumida)
                )

                anual["Hover"] = (
                    anual[
                        "ValorRecolhido"
                    ]
                    .map(moeda)
                )

                fig = px.bar(
                    anual,
                    x="AnoLabel",
                    y="ValorRecolhido",
                    text="Rotulo",
                    custom_data=["Hover"],
                    title="Arrecadação por ano"
                )

                fig.update_traces(
                    marker_color=AZUL_MEDIO,
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "CFEM: %{customdata[0]}"
                        "<extra></extra>"
                    )
                )

                fig.update_xaxes(
                    title=None
                )

                fig.update_yaxes(
                    title=None,
                    showticklabels=False
                )

                layout_grafico(
                    fig,
                    altura=420
                )

                plotar(fig)

                colunas = [
                    c for c in [
                        "Ano",
                        "Mês",
                        "Município",
                        "Substância",
                        "QuantidadeComercializada",
                        "UnidadeDeMedida",
                        "ValorRecolhido"
                    ]
                    if c in resultado.columns
                ]

                tabela = (
                    resultado[colunas]
                    .copy()
                )

                if "Mês" in tabela.columns:

                    tabela["Mês"] = (
                        tabela["Mês"]
                        .map(MESES)
                    )

                if (
                    "QuantidadeComercializada"
                    in tabela.columns
                ):

                    tabela[
                        "QuantidadeComercializada"
                    ] = (
                        tabela[
                            "QuantidadeComercializada"
                        ]
                        .map(
                            lambda x:
                            numero_br(x, 2)
                        )
                    )

                if (
                    "ValorRecolhido"
                    in tabela.columns
                ):

                    tabela[
                        "ValorRecolhido"
                    ] = (
                        tabela[
                            "ValorRecolhido"
                        ]
                        .map(moeda)
                    )

                tabela = tabela.rename(
                    columns={
                        "QuantidadeComercializada":
                            "Quantidade comercializada",
                        "UnidadeDeMedida":
                            "Unidade",
                        "ValorRecolhido":
                            "CFEM arrecadada"
                    }
                )

                st.dataframe(
                    tabela,
                    use_container_width=True,
                    hide_index=True
                )

        # ====================================================
        # SCM
        # ====================================================

        with aba_scm:

            st.caption(
                "Pesquisa do processo nas bases "
                "públicas do Sistema de Cadastro "
                "Mineiro da ANM."
            )

            if st.button(
                "🔎 Consultar bases SCM",
                type="primary"
            ):

                encontrados = 0

                barra = st.progress(0)

                status = st.empty()

                total_arquivos = len(
                    SCM_FILES
                )

                for indice, (
                    titulo,
                    arquivo
                ) in enumerate(
                    SCM_FILES.items(),
                    start=1
                ):

                    status.caption(
                        f"Consultando {titulo}..."
                    )

                    try:

                        scm = load_scm_file(
                            arquivo
                        )

                        if (
                            "_processo_key"
                            in scm.columns
                        ):

                            resultado_scm = (
                                scm[
                                    scm[
                                        "_processo_key"
                                    ] == chave
                                ]
                                .copy()
                            )

                            if (
                                not resultado_scm.empty
                            ):

                                encontrados += 1

                                st.subheader(
                                    titulo
                                )

                                resultado_scm = (
                                    resultado_scm.drop(
                                        columns=[
                                            "_processo_key"
                                        ],
                                        errors="ignore"
                                    )
                                )

                                st.dataframe(
                                    resultado_scm,
                                    use_container_width=True,
                                    hide_index=True
                                )

                    except Exception:
                        pass

                    barra.progress(
                        indice
                        / total_arquivos
                    )

                barra.empty()
                status.empty()

                if encontrados == 0:

                    st.info(
                        "Nenhuma ocorrência foi "
                        "encontrada nas bases SCM "
                        "consultadas."
                    )


# ============================================================
# 28. RODAPÉ
# ============================================================

st.divider()

rodape = (
    "Fonte: Agência Nacional de Mineração — ANM • "
    "CFEM • SIGMINE • Sistema de Cadastro Mineiro (SCM). "
    "Dados públicos sujeitos às atualizações das bases de origem."
)

if (
    ANO_MAX_CFEM
    and MES_MAX_CFEM
):

    rodape += (
        f" • CFEM disponível até "
        f"{MESES_LONGOS[MES_MAX_CFEM]}/"
        f"{ANO_MAX_CFEM}."
    )

st.caption(
    rodape
)
