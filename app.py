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
    """Formata número completo no padrão brasileiro: 1.234.567,89"""
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_compacto(valor):
    """Formata número de forma compacta: 170k, 1,2 Mi"""
    if abs(valor) >= 1_000_000:
        return f"{valor/1_000_000:.1f}".replace('.', ',') + " Mi"
    elif abs(valor) >= 1_000:
        return f"{valor/1_000:.0f}k"
    return f"{valor:.0f}"

# ============================================================
# Descobre dinamicamente o período real dos dados
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
# KPIs: Total | Últimos 12 meses | YTD | Último mês
# delta_color="inverse": para internações, MENOS é positivo (verde), MAIS é negativo (vermelho)
# ============================================================
total_geral = consultar("SELECT total_internacoes FROM VW_KPIS_GERAIS")['TOTAL_INTERNACOES'][0]

ultimos_12 = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN
          ({periodo['FIM'][0]} - 100) + 1 AND {periodo['FIM'][0]}
""")['QTD'][0]

ultimos_12_anterior = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN
          ({periodo['FIM'][0]} - 200) + 1 AND ({periodo['FIM'][0]} - 100)
""")['QTD'][0]

ytd = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = {fim_ano} AND nr_mes_competencia <= {fim_mes}
""")['QTD'][0]

ytd_anterior = consultar(f"""
    SELECT COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia = {fim_ano - 1} AND nr_mes_competencia <= {fim_mes}
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

delta_12m = ((ultimos_12 - ultimos_12_anterior) / ultimos_12_anterior * 100) if ultimos_12_anterior else 0
delta_ytd = ((ytd - ytd_anterior) / ytd_anterior * 100) if ytd_anterior else 0
delta_mes = ((mes_atual - mes_anterior) / mes_anterior * 100) if mes_anterior else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Total de Internações",
    fmt_num(total_geral),
    help=f"Soma de todas as internações registradas no período completo disponível ({ini_str} a {fim_str})."
)
col2.metric(
    "Últimos 12 Meses",
    fmt_num(ultimos_12),
    delta=f"{delta_12m:+.1f}% vs. 12 meses anteriores ({fmt_num(ultimos_12_anterior)})",
    delta_color="inverse",
    help="Soma dos 12 meses mais recentes disponíveis, comparada com os 12 meses imediatamente anteriores a eles."
)
col3.metric(
    f"YTD ({fim_ano})",
    fmt_num(ytd),
    delta=f"{delta_ytd:+.1f}% vs. YTD {fim_ano - 1} ({fmt_num(ytd_anterior)})",
    delta_color="inverse",
    help=f"Year to Date: soma de janeiro até {fim_mes:02d}/{fim_ano}, comparada ao mesmo intervalo de {fim_ano - 1}."
)
col4.metric(
    f"Último Mês ({fim_str})",
    fmt_num(mes_atual),
    delta=f"{delta_mes:+.1f}% vs. mês anterior ({fmt_num(mes_anterior)})",
    delta_color="inverse",
    help="Total do mês mais recente disponível, comparado percentualmente com o mês imediatamente anterior."
)

# ============================================================
# Gráfico de evolução: ÍNDICE DE CRESCIMENTO (base 100 no primeiro mês)
# Resolve o problema de escala (regiões pequenas ficavam esmagadas) e
# responde diretamente a pergunta "onde está crescendo mais"
# ============================================================
st.subheader("📈 Evolução do Crescimento por Região (índice, base 100)")
st.caption("Cada linha começa em 100 no primeiro mês disponível. Uma linha subindo mais que as outras "
           "indica crescimento relativo mais rápido — independente do volume absoluto da região.")

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
temporal_total['grupo'] = 'Total Geral'
temporal_total = temporal_total.rename(columns={'QTD_INTERNACOES': 'QTD_INTERNACOES'})

# Junta tudo (regiões + total) e calcula o índice base 100
base_completa = pd.concat([temporal_agrupado, temporal_total[['competencia', 'grupo', 'QTD_INTERNACOES']]])
base_completa = base_completa.sort_values('competencia')

base_completa = base_completa.sort_values(['grupo', 'competencia'])
primeiro_valor_por_grupo = base_completa.groupby('grupo')['QTD_INTERNACOES'].transform('first')
base_completa['indice'] = base_completa['QTD_INTERNACOES'] / primeiro_valor_por_grupo * 100
base_indexada = base_completa

# Ordena a legenda pelo crescimento final (quem mais cresceu aparece primeiro)
crescimento_final = base_indexada.sort_values('competencia').groupby('grupo')['indice'].last().sort_values(ascending=False)
ordem_categorias = crescimento_final.index.tolist()

fig_evolucao = px.line(
    base_indexada, x='competencia', y='indice', color='grupo',
    category_orders={'grupo': ordem_categorias},
    line_shape='spline'
)
# Destaca a linha do Total Geral (pontilhada, branca, mais grossa)
for trace in fig_evolucao.data:
    if trace.name == 'Total Geral':
        trace.line.update(color='white', width=3, dash='dot')

fig_evolucao.add_hline(y=100, line_dash='dot', line_color='gray', annotation_text='Base (100)')
fig_evolucao.update_layout(
    legend_title_text='Região (por crescimento)', hovermode='x unified',
    xaxis_title=None, yaxis_title='Índice (base 100)', height=450
)
st.plotly_chart(fig_evolucao, use_container_width=True)

# ============================================================
# Rankings: Top 10 Regiões | Top 10 Causas | Share por Caráter
# Altura padronizada (height=420) + números compactos (170k, 1,5 Mi)
# ============================================================
ALTURA_PADRAO = 420

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("🏙️ Top 10 Regiões")
    regioes = consultar("""
        SELECT nm_regiao_saude, qtd_internacoes FROM VW_VOLUME_REGIAO
        ORDER BY qtd_internacoes DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD_INTERNACOES')
    regioes['label'] = regioes['QTD_INTERNACOES'].apply(fmt_compacto)
    fig = px.bar(regioes, x='QTD_INTERNACOES', y='NM_REGIAO_SAUDE', orientation='h', text='label')
    fig.update_traces(textposition='outside')
    fig.update_layout(yaxis_title=None, xaxis_title='Internações', height=ALTURA_PADRAO,
                       yaxis=dict(automargin=True), margin=dict(l=10, r=40, t=10, b=10))
    fig.update_xaxes(tickformat="~s")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("🩺 Top 10 Causas")
    diagnosticos = consultar("""
        SELECT ds_diagnostico, qtd FROM VW_TOP_DIAGNOSTICOS
        ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD')
    diagnosticos['label'] = diagnosticos['QTD'].apply(fmt_compacto)
    fig = px.bar(diagnosticos, x='QTD', y='DS_DIAGNOSTICO', orientation='h', text='label')
    fig.update_traces(textposition='outside')
    fig.update_layout(yaxis_title=None, xaxis_title='Internações', height=ALTURA_PADRAO,
                       yaxis=dict(automargin=True), margin=dict(l=10, r=40, t=10, b=10))
    fig.update_xaxes(tickformat="~s")
    st.plotly_chart(fig, use_container_width=True)

with col_c:
    st.subheader("🚑 Share por Caráter de Internação")
    carater_share = consultar("SELECT ds_carater_internacao, qtd_internacoes FROM VW_MORTALIDADE_CARATER")
    carater_share['pct'] = carater_share['QTD_INTERNACOES'] / carater_share['QTD_INTERNACOES'].sum() * 100
    carater_share = carater_share.sort_values('pct')
    carater_share['label'] = carater_share['pct'].apply(lambda v: f"{v:.1f}%".replace('.', ','))
    fig = px.bar(carater_share, x='pct', y='DS_CARATER_INTERNACAO', orientation='h', text='label')
    fig.update_traces(textposition='outside')
    fig.update_layout(xaxis_title='% do total', yaxis_title=None, height=ALTURA_PADRAO,
                       yaxis=dict(automargin=True), margin=dict(l=10, r=40, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Mortalidade por caráter de internação (achado-chave)
# ============================================================
st.subheader("⚠️ Mortalidade por Caráter de Internação")
st.caption("Achado-chave do projeto: internações de urgência têm mortalidade significativamente maior que eletivas.")
mortalidade = consultar("""
    SELECT ds_carater_internacao, taxa_mortalidade FROM VW_MORTALIDADE_CARATER
    ORDER BY taxa_mortalidade DESC
""")
mortalidade['label'] = mortalidade['TAXA_MORTALIDADE'].apply(lambda v: f"{v:.2f}%".replace('.', ','))
fig = px.bar(mortalidade.sort_values('TAXA_MORTALIDADE'), x='TAXA_MORTALIDADE', y='DS_CARATER_INTERNACAO',
             orientation='h', text='label')
fig.update_traces(textposition='outside')
fig.update_layout(yaxis_title=None, xaxis_title='Taxa de mortalidade (%)', height=380,
                   yaxis=dict(automargin=True), margin=dict(l=10, r=40, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Seção 2 — Capacidade Instalada (dispersão: volume x pressão)
# ============================================================
st.header("Seção 2 — Capacidade Instalada")
st.caption("Cada bolha é uma região de saúde. Eixo X = volume de internações. Eixo Y = pressão sobre a "
           "capacidade (internações por leito). Tamanho da bolha = quantidade de leitos disponíveis. "
           "Regiões no canto superior direito (muito volume + muita pressão) são as realmente críticas — "
           "alta pressão com baixo volume pode ser só efeito de escala pequena, não um problema real de capacidade.")

capacidade_completa = consultar("SELECT * FROM VW_CAPACIDADE_REGIAO")
mediana_x = capacidade_completa['INTERNACOES'].median()
mediana_y = capacidade_completa['INTERNACOES_POR_LEITO'].median()

fig_capacidade = px.scatter(
    capacidade_completa, x='INTERNACOES', y='INTERNACOES_POR_LEITO',
    size='LEITOS_REGIAO', color='INTERNACOES_POR_LEITO', color_continuous_scale='RdYlGn_r',
    hover_name='NM_REGIAO_SAUDE'
)
fig_capacidade.add_vline(x=mediana_x, line_dash='dash', line_color='gray')
fig_capacidade.add_hline(y=mediana_y, line_dash='dash', line_color='gray')
fig_capacidade.update_layout(xaxis_title='Volume de Internações', yaxis_title='Internações por Leito (pressão)',
                              height=500, margin=dict(l=10, r=10, t=10, b=10))
fig_capacidade.update_xaxes(tickformat="~s")
st.plotly_chart(fig_capacidade, use_container_width=True)
