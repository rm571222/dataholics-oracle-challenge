import streamlit as st
import oracledb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64, os, zipfile, io

st.set_page_config(page_title="Painel Hospitalar SP - DATAHOLICS", layout="wide")

st.markdown("""
<style>
[data-testid="stMetric"] {
    background-color: #1C1F26;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 15px;
}
h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def conectar():
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

@st.cache_data(ttl=3600)
def consultar(query):
    return pd.read_sql(query, conectar())

def fmt_num(valor, casas=0):
    """Formata número no padrão brasileiro: 1.234.567,89"""
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

# ============================================================
# Descobre dinamicamente o período real dos dados (não fixo no código)
# ============================================================
periodo = consultar("""
    SELECT MIN(nr_ano_competencia*100+nr_mes_competencia) AS ini,
           MAX(nr_ano_competencia*100+nr_mes_competencia) AS fim
    FROM VW_INTERNACAO_COMPLETA
""")
ini_str = f"{str(periodo['INI'][0])[4:6]}/{str(periodo['INI'][0])[0:4]}"
fim_ano, fim_mes = int(str(periodo['FIM'][0])[0:4]), int(str(periodo['FIM'][0])[4:6])
fim_str = f"{fim_mes:02d}/{fim_ano}"

st.title("🏥 Painel Hospitalar SP — DATAHOLICS")
st.caption(f"FIAP Challenge | Parceria Oracle — Dados SIH/DATASUS, {ini_str} a {fim_str} · "
           f"Dados atualizados até: {fim_str}")

st.header("Seção 1 — Visão Executiva")

# ============================================================
# KPIs: Total | Últimos 12 meses | YTD | Último mês (com comparativo)
# ============================================================
total_geral = consultar("SELECT total_internacoes FROM VW_KPIS_GERAIS")['TOTAL_INTERNACOES'][0]

ultimos_12 = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN
          ({periodo['FIM'][0]} - 100) + 1 AND {periodo['FIM'][0]}
""")['QTD'][0]

ytd = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = {fim_ano} AND nr_mes_competencia <= {fim_mes}
""")['QTD'][0]

mes_atual = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = {fim_ano} AND nr_mes_competencia = {fim_mes}
""")['QTD'][0]

mes_anterior_ano = fim_ano if fim_mes > 1 else fim_ano - 1
mes_anterior_mes = fim_mes - 1 if fim_mes > 1 else 12
mes_anterior = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = {mes_anterior_ano} AND nr_mes_competencia = {mes_anterior_mes}
""")['QTD'][0]

delta_pct = ((mes_atual - mes_anterior) / mes_anterior * 100) if mes_anterior else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Total de Internações",
    fmt_num(total_geral),
    help=f"Soma de todas as internações registradas no período completo disponível ({ini_str} a {fim_str})."
)
col2.metric(
    "Últimos 12 Meses",
    fmt_num(ultimos_12),
    help=f"Internações somadas nos 12 meses mais recentes disponíveis (até {fim_str})."
)
col3.metric(
    f"YTD ({fim_ano})",
    fmt_num(ytd),
    help=f"Year to Date: soma de internações de janeiro de {fim_ano} até o mês mais recente disponível ({fim_str})."
)
col4.metric(
    f"Último Mês ({fim_str})",
    fmt_num(mes_atual),
    delta=f"{delta_pct:+.1f}% vs. mês anterior",
    help="Total do mês mais recente disponível, comparado percentualmente com o mês imediatamente anterior."
)

# ============================================================
# Gráfico de evolução: Top 5 regiões (área empilhada) + Outras + Total
# ============================================================
st.subheader("📈 Evolução Mensal por Região")
st.caption("Composição do volume mensal: as 5 regiões de maior volume no período, agrupando as demais em 'Outras'.")

top5_regioes = consultar("""
    SELECT nm_regiao_saude FROM VW_VOLUME_REGIAO
    ORDER BY qtd_internacoes DESC FETCH FIRST 5 ROWS ONLY
""")['NM_REGIAO_SAUDE'].tolist()

temporal_completo = consultar("""
    SELECT nm_regiao_saude, nr_ano_competencia, nr_mes_competencia, qtd_internacoes
    FROM VW_VOLUME_REGIAO_TEMPORAL
""")
temporal_completo['competencia'] = pd.to_datetime(
    temporal_completo['NR_ANO_COMPETENCIA'].astype(str) + '-' +
    temporal_completo['NR_MES_COMPETENCIA'].astype(str).str.zfill(2) + '-01'
)
temporal_completo['grupo'] = temporal_completo['NM_REGIAO_SAUDE'].apply(
    lambda x: x if x in top5_regioes else 'Outras Regiões'
)
temporal_agrupado = temporal_completo.groupby(['competencia', 'grupo'])['QTD_INTERNACOES'].sum().reset_index()
temporal_total = temporal_completo.groupby('competencia')['QTD_INTERNACOES'].sum().reset_index()

fig_evolucao = px.area(
    temporal_agrupado, x='competencia', y='QTD_INTERNACOES', color='grupo',
    title=None
)
fig_evolucao.add_trace(go.Scatter(
    x=temporal_total['competencia'], y=temporal_total['QTD_INTERNACOES'],
    mode='lines', name='Total Geral', line=dict(color='white', width=3, dash='dot')
))
fig_evolucao.update_layout(legend_title_text='Região', hovermode='x unified')
st.plotly_chart(fig_evolucao, use_container_width=True)

# ============================================================
# Rankings: Top 10 Regiões | Top 10 Causas | Share por Caráter
# ============================================================
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("🏙️ Top 10 Regiões")
    regioes = consultar("""
        SELECT nm_regiao_saude, qtd_internacoes FROM VW_VOLUME_REGIAO
        ORDER BY qtd_internacoes DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD_INTERNACOES')
    fig = px.bar(regioes, x='QTD_INTERNACOES', y='NM_REGIAO_SAUDE', orientation='h',
                 text='QTD_INTERNACOES')
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("🩺 Top 10 Causas")
    diagnosticos = consultar("""
        SELECT ds_diagnostico, qtd FROM VW_TOP_DIAGNOSTICOS
        ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD')
    fig = px.bar(diagnosticos, x='QTD', y='DS_DIAGNOSTICO', orientation='h', text='QTD')
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with col_c:
    st.subheader("🚑 Share por Caráter de Internação")
    carater = consultar("SELECT ds_carater_internacao, qtd_internacoes FROM VW_MORTALIDADE_CARATER")
    fig = px.pie(carater, names='DS_CARATER_INTERNACAO', values='QTD_INTERNACOES', hole=0.4)
    fig.update_traces(textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Mortalidade por caráter (mantido, mas com rótulo)
# ============================================================
st.subheader("⚠️ Mortalidade por Caráter de Internação")
st.caption("Achado-chave do projeto: internações de urgência têm mortalidade significativamente maior que eletivas.")
mortalidade = consultar("""
    SELECT ds_carater_internacao, taxa_mortalidade FROM VW_MORTALIDADE_CARATER
    ORDER BY taxa_mortalidade DESC
""")
fig = px.bar(mortalidade.sort_values('TAXA_MORTALIDADE'), x='TAXA_MORTALIDADE', y='DS_CARATER_INTERNACAO',
             orientation='h', text='TAXA_MORTALIDADE')
fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Seção 2 (mantida como estava — ajustes na Sprint C)
# ============================================================
st.header("Seção 2 — Capacidade Instalada")
capacidade = consultar("""
    SELECT nm_regiao_saude, internacoes_por_leito FROM VW_CAPACIDADE_REGIAO
    ORDER BY internacoes_por_leito DESC FETCH FIRST 10 ROWS ONLY
""")
fig = px.bar(capacidade.sort_values('INTERNACOES_POR_LEITO'), x='INTERNACOES_POR_LEITO', y='NM_REGIAO_SAUDE',
             orientation='h', text='INTERNACOES_POR_LEITO',
             color='INTERNACOES_POR_LEITO', color_continuous_scale='RdYlGn_r')
fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
st.plotly_chart(fig, use_container_width=True)
