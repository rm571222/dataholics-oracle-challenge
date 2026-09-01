import streamlit as st
import oracledb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64, os, zipfile, io

# ============================================================
# CONFIG + TEMA (espelha o app.py principal)
# ============================================================
st.set_page_config(page_title="Mapa — Painel Hospitalar SP", page_icon="🗺️", layout="wide")

PALETA = ["#4C9AFF", "#F5A623", "#2ECC71", "#E74C3C", "#9B59B6"]
COR_STATUS = {"Crítico": "#E74C3C", "Atenção": "#F5A623", "Estável": "#2ECC71"}
SEPARADOR_BR = ",."

# Limiares de ocupação (iguais à Seção 2 do app principal)
OCUP_CRITICO = 70.0
OCUP_ATENCAO = 55.0

st.markdown("""
<style>
.block-container { padding-top: 2rem; max-width: 1500px; }
[data-testid="stMetric"] { background:#1C1F26; border:1px solid #333; border-radius:10px; padding:15px; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CONEXÃO (mesma lógica resiliente do app principal)
# ============================================================
def _nova_conexao():
    wallet_path = "/tmp/wallet"
    if not os.path.exists(wallet_path):
        os.makedirs(wallet_path)
        wallet_bytes = base64.b64decode(st.secrets["wallet_b64"])
        with zipfile.ZipFile(io.BytesIO(wallet_bytes)) as z:
            z.extractall(wallet_path)
    return oracledb.connect(
        user=st.secrets["db_user"], password=st.secrets["db_password"],
        dsn=st.secrets["db_dsn"], config_dir=wallet_path,
        wallet_location=wallet_path, wallet_password=st.secrets["wallet_password"]
    )

@st.cache_resource
def conectar():
    return _nova_conexao()

def _get_conexao():
    conn = conectar()
    try:
        conn.ping(); return conn
    except Exception:
        conectar.clear(); return conectar()

@st.cache_data(ttl=3600)
def consultar(query):
    try:
        return pd.read_sql(query, _get_conexao())
    except oracledb.DatabaseError:
        conectar.clear(); return pd.read_sql(query, conectar())


# ============================================================
# UTILITÁRIOS
# ============================================================
def fmt_num(v, casas=0):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def status_ocup(v):
    if pd.isna(v): return "Sem dado"
    if v >= OCUP_CRITICO: return "Crítico"
    if v >= OCUP_ATENCAO: return "Atenção"
    return "Estável"


# ============================================================
# CABEÇALHO
# ============================================================
st.title("🗺️ Mapa — Hospitais de SP")
st.caption("Cada ponto é um hospital, posicionado por sua coordenada (CNES). "
           "A cor indica a taxa de ocupação de leitos SUS e o tamanho reflete a capacidade (leitos). "
           "Passe o mouse para ver os detalhes de cada unidade.")

# ------------------------------------------------------------
# Dados: hospitais com coordenadas
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
def carregar_hospitais():
    df = consultar("""
        SELECT nm_hospital, nm_regiao_saude, nm_municipio, esfera_admin,
               latitude, longitude, qtd_internacoes, permanencia_media,
               leitos_sus, taxa_ocupacao, taxa_mortalidade
        FROM   VW_HOSPITAL_PERMANENCIA
        WHERE  latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    return df

hosp = carregar_hospitais()

# Sanidade: coordenadas dentro do bounding box aproximado de SP
hosp = hosp[(hosp['LATITUDE'].between(-25.5, -19.5)) &
            (hosp['LONGITUDE'].between(-53.5, -44.0))].copy()
hosp['status'] = hosp['TAXA_OCUPACAO'].apply(status_ocup)
# Tamanho do ponto: leitos (com piso p/ hospitais sem leito registrado)
hosp['_size'] = hosp['LEITOS_SUS'].fillna(0).clip(lower=0) + 20

# ------------------------------------------------------------
# Filtros
# ------------------------------------------------------------
st.markdown("### 🎛️ Filtros")
fc1, fc2, fc3 = st.columns(3)
with fc1:
    regioes = st.multiselect("Região de saúde",
                             sorted(hosp['NM_REGIAO_SAUDE'].dropna().unique()))
with fc2:
    esferas = st.multiselect("Esfera administrativa",
                             sorted(hosp['ESFERA_ADMIN'].dropna().unique()))
with fc3:
    status_sel = st.multiselect("Status de ocupação",
                                ["Crítico", "Atenção", "Estável", "Sem dado"])

df = hosp.copy()
if regioes:    df = df[df['NM_REGIAO_SAUDE'].isin(regioes)]
if esferas:    df = df[df['ESFERA_ADMIN'].isin(esferas)]
if status_sel: df = df[df['status'].isin(status_sel)]

# ------------------------------------------------------------
# KPIs do recorte
# ------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Hospitais no mapa", fmt_num(len(df)))
k2.metric("🔴 Críticos (≥70%)", fmt_num(int((df['status'] == "Crítico").sum())))
k3.metric("Leitos SUS (soma)", fmt_num(df['LEITOS_SUS'].fillna(0).sum()))
k4.metric("Ocupação média", f"{fmt_num(df['TAXA_OCUPACAO'].mean() or 0,1)}%")

if len(df) == 0:
    st.warning("Nenhum hospital para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------
# Mapa de pontos (open-street-map, sem necessidade de token)
# ------------------------------------------------------------
df['_hover'] = df.apply(lambda r:
    f"<b>{r['NM_HOSPITAL']}</b><br>"
    f"{r['NM_MUNICIPIO']} · {r['NM_REGIAO_SAUDE']}<br>"
    f"Esfera: {r['ESFERA_ADMIN']}<br>"
    f"Internações: {fmt_num(r['QTD_INTERNACOES'])}<br>"
    f"Leitos SUS: {fmt_num(r['LEITOS_SUS'] or 0)}<br>"
    f"Ocupação: {fmt_num(r['TAXA_OCUPACAO'] or 0,1)}%<br>"
    f"Permanência: {fmt_num(r['PERMANENCIA_MEDIA'] or 0,1)} dias",
    axis=1)

# Compatibilidade Plotly: 6.x usa Scattermap (MapLibre); <6 usa Scattermapbox.
_USA_MAP = hasattr(go, "Scattermap")
_TraceMap = go.Scattermap if _USA_MAP else go.Scattermapbox

def _trace_pontos(sub, nome, cor, tamanho=None):
    marker = dict(color=cor, opacity=0.75)
    if tamanho is not None:
        marker.update(size=tamanho, sizemode='area',
                      sizeref=(tamanho.max() / 900) if tamanho.max() else 1)
    else:
        marker.update(size=8, opacity=0.6)
    return _TraceMap(lat=sub['LATITUDE'], lon=sub['LONGITUDE'], mode='markers',
                     name=nome, marker=marker, text=sub['_hover'], hoverinfo='text')

fig = go.Figure()
for st_nome, cor in COR_STATUS.items():
    sub = df[df['status'] == st_nome]
    if len(sub):
        fig.add_trace(_trace_pontos(sub, st_nome, cor, tamanho=sub['_size']))
# hospitais sem dado de ocupação (cinza)
sub = df[df['status'] == "Sem dado"]
if len(sub):
    fig.add_trace(_trace_pontos(sub, "Sem dado", "#7F8C9B"))

# Layout do mapa: chaves diferem entre as APIs (map vs mapbox)
_layout_mapa = dict(
    height=640, margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01,
                bgcolor="rgba(28,31,38,0.8)", font=dict(color="#E6E6E6")),
    paper_bgcolor="rgba(0,0,0,0)",
)
if _USA_MAP:
    _layout_mapa.update(map=dict(style="carto-darkmatter", zoom=5.6,
                                 center=dict(lat=-22.5, lon=-48.6)))
else:
    _layout_mapa.update(mapbox=dict(style="carto-darkmatter", zoom=5.6,
                                    center=dict(lat=-22.5, lon=-48.6)))
fig.update_layout(**_layout_mapa)
st.plotly_chart(fig, use_container_width=True, key="mapa_hospitais")

st.caption("🔴 ocupação ≥ 70% · 🟡 55–70% · 🟢 < 55% · ⚪ sem dado de leitos SUS. "
           "Tamanho do ponto ∝ leitos SUS. Coordenadas do cadastro CNES; alguns hospitais "
           "sem geolocalização não aparecem no mapa.")

# ------------------------------------------------------------
# Nota sobre a camada de choropleth (próximo passo)
# ------------------------------------------------------------
with st.expander("ℹ️ Sobre o mapa de calor por região (próxima camada)"):
    st.markdown(
        "Este mapa mostra **hospitais como pontos**. A camada de **áreas pintadas "
        "(choropleth) por município/região** — colorida por estado de alerta ou "
        "internações per capita — será adicionada assim que o GeoJSON dos polígonos "
        "for integrado. Os dados (per capita por região, população municipal) já estão prontos."
    )
