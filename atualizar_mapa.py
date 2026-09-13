import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

# ============================================================
# WEBGIS CFEM - MINAS GERAIS
# Atualização automática dos dados da ANM
# Autoria: Melissa Carvalho
# ============================================================

URL_CFEM = (
    "https://dadosabertos.anm.gov.br/CFEM/"
    "CFEM_Arrecadacao_2022_2026.csv"
)

print("=" * 60)
print("WEBGIS CFEM - MINAS GERAIS")
print("Iniciando atualização dos dados...")
print("=" * 60)

# ------------------------------------------------------------
# 1. BAIXAR BASE DA ANM
# ------------------------------------------------------------

headers = {
    "User-Agent": "Mozilla/5.0"
}

print("\nBaixando dados da ANM...")

response = requests.get(
    URL_CFEM,
    headers=headers,
    timeout=180
)

response.raise_for_status()

print(
    f"Download concluído: "
    f"{len(response.content) / (1024 * 1024):.2f} MB"
)

# ------------------------------------------------------------
# 2. LER CSV
# ------------------------------------------------------------

print("\nLendo arquivo CSV...")

cfem = pd.read_csv(
    BytesIO(response.content),
    sep=None,
    engine="python",
    encoding="latin1"
)

print(f"Registros encontrados: {len(cfem):,}")
print(f"Colunas encontradas: {len(cfem.columns)}")

# ------------------------------------------------------------
# 3. VERIFICAR ANOS
# ------------------------------------------------------------

anos = sorted(
    cfem["Ano"]
    .dropna()
    .astype(int)
    .unique()
)

print("\nAnos encontrados:")
print(anos)

# ------------------------------------------------------------
# 4. DATA DA ATUALIZAÇÃO
# ------------------------------------------------------------

data_execucao = datetime.now().strftime("%d/%m/%Y %H:%M")

print("\nExecução:")
print(data_execucao)

print("\n" + "=" * 60)
print("TESTE CONCLUÍDO COM SUCESSO")
print("=" * 60)
