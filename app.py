import streamlit as st
import oracledb
import pandas as pd
import plotly.express as px
import base64, os, zipfile, io

st.set_page_config(page_title="Painel Hospitalar SP - DATAHOLICS", layout="wide")

@st.cache_resource
def conectar():
    wallet_path = "/tmp/wallet"
    if not os.path.exists(wallet_path):
        os.makedirs(wallet_path)
        wallet_bytes = base64.b64decode(st.secrets["wallet_b64"])
        with zipfile.ZipFile(io.BytesIO(wallet_bytes)) as z:
            z.extractall(wallet_path)

    return oracledb.connect(
        user=st.secrets["db_user"],
        password=st.secrets["db_password"],
        dsn=st.secrets["db_dsn"],
        config_dir=wallet_path,
        wallet_location=wallet_path,
        wallet_password=st.secrets["wallet_password"]
    )

@st.cache_data(ttl=3600)
def consultar(query):
    conn = conectar()
    return pd.read_sql(query, conn)

st.title("🏥 Painel Hospitalar SP — DATAHOLICS")
st.caption("FIAP Challenge | Parceria Oracle — Dados SIH/DATASUS, jun/2024 a jun/2026")

st.header("Seção 1 — Evolução Mensal")

kpis = consultar("SELECT * FROM VW_KPIS_GERAIS")
ultimo_mes = consultar("""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = 2026 AND nr_mes_competencia = 6
""")
ultimos_12 = consultar("""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia = 2025 AND nr_mes_competencia >= 7)
       OR (nr_ano_competencia = 2026)
""")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de Internações (todo o período)", f"{kpis['TOTAL_INTERNACOES'][0]:,.0f}")
col2.metric("Últimos 12 meses", f"{ultimos_12['QTD'][0]:,.0f}")
col3.metric("Último mês (jun/2026)", f"{ultimo_mes['QTD'][0]:,.0f}")
col4.metric("Taxa de Mortalidade Geral", f"{kpis['TAXA_MORTALIDADE'][0]}%")

temporal = consultar("""
    SELECT nr_ano_competencia || '-' || LPAD(nr_mes_competencia,2,'0') AS competencia,
           SUM(qtd_internacoes) AS total
    FROM VW_VOLUME_REGIAO_TEMPORAL
    GROUP BY nr_ano_competencia, nr_mes_competencia
    ORDER BY nr_ano_competencia, nr_mes_competencia
""")
st.plotly_chart(
    px.line(temporal, x='COMPETENCIA', y='TOTAL', markers=True,
            title='Evolução Mensal de Internações (todos os meses)'),
    use_container_width=True
)

col_a, col_b, col_c = st.columns(3)

with col_a:
    regioes = consultar("""
        SELECT nm_regiao_saude, qtd_internacoes FROM VW_VOLUME_REGIAO
        ORDER BY qtd_internacoes DESC FETCH FIRST 10 ROWS ONLY
    """)
    st.plotly_chart(
        px.bar(regioes.sort_values('QTD_INTERNACOES'), x='QTD_INTERNACOES', y='NM_REGIAO_SAUDE',
               orientation='h', title='Top 10 Regiões por Volume'),
        use_container_width=True
    )

with col_b:
    diagnosticos = consultar("""
        SELECT ds_diagnostico, qtd FROM VW_TOP_DIAGNOSTICOS
        ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY
    """)
    st.plotly_chart(
        px.bar(diagnosticos.sort_values('QTD'), x='QTD', y='DS_DIAGNOSTICO',
               orientation='h', title='Top 10 Causas de Internação'),
        use_container_width=True
    )

with col_c:
    mortalidade = consultar("""
        SELECT ds_carater_internacao, taxa_mortalidade FROM VW_MORTALIDADE_CARATER
        ORDER BY taxa_mortalidade DESC
    """)
    st.plotly_chart(
        px.bar(mortalidade.sort_values('TAXA_MORTALIDADE'), x='TAXA_MORTALIDADE', y='DS_CARATER_INTERNACAO',
               orientation='h', title='Mortalidade por Caráter de Internação (%)'),
        use_container_width=True
    )

st.header("Seção 2 — Capacidade Instalada")
capacidade = consultar("""
    SELECT nm_regiao_saude, internacoes_por_leito FROM VW_CAPACIDADE_REGIAO
    ORDER BY internacoes_por_leito DESC FETCH FIRST 10 ROWS ONLY
""")
st.plotly_chart(
    px.bar(capacidade.sort_values('INTERNACOES_POR_LEITO'), x='INTERNACOES_POR_LEITO', y='NM_REGIAO_SAUDE',
           orientation='h', title='Regiões Mais Críticas — Internações por Leito',
           color='INTERNACOES_POR_LEITO', color_continuous_scale='RdYlGn_r'),
    use_container_width=True
)
