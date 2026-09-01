import streamlit as st
import oracledb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64, os, zipfile, io

# ============================================================
# CONFIG GLOBAL
# ============================================================
st.set_page_config(
    page_title="Painel Hospitalar SP - DATAHOLICS",
    page_icon="🏥",
    layout="wide",
)

# --- Constantes de layout/tema (fonte única de verdade) --------------------
CHART_HEIGHT = 380          # altura padrão de TODOS os gráficos
CHART_HEIGHT_LG = 440       # altura para gráficos "hero" (evolução / dispersão)
MARGEM_PADRAO = dict(l=10, r=30, t=40, b=10)

# Paleta categórica única (aplicada por categoria em todos os gráficos)
PALETA = ["#4C9AFF", "#F5A623", "#2ECC71", "#E74C3C", "#9B59B6",
          "#1ABC9C", "#E84393", "#F1C40F", "#95A5A6"]

# separators=',.'  => decimal vírgula e milhar ponto (padrão BR) em todo o Plotly
SEPARADOR_BR = ",."

st.markdown("""
<style>
/* Container mais estreito em telas gigantes evita gráficos "esticados" demais */
.block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1500px; }

[data-testid="stMetric"] {
    background-color: #1C1F26;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 15px;
}
h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }

/* Responsividade: em telas menores tira o padding lateral pra não cortar */
@media (max-width: 640px) {
    .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# CONEXÃO E CONSULTA  (lógica de dados INALTERADA)
# ============================================================
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


# ============================================================
# UTILITÁRIOS DE FORMATAÇÃO (padrão Brasil)
# ============================================================
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
# TEMA ÚNICO DOS GRÁFICOS  (aplicado em TODOS via aplicar_tema)
# Centraliza cores, fonte, margens, legenda, altura e separador BR.
# ============================================================
def aplicar_tema(fig, altura=CHART_HEIGHT, mostrar_legenda=True):
    fig.update_layout(
        template="plotly_dark",
        height=altura,
        colorway=PALETA,
        font=dict(family="Segoe UI, sans-serif", size=13, color="#E6E6E6"),
        title=dict(font=dict(size=16)),
        margin=MARGEM_PADRAO,
        separators=SEPARADOR_BR,                 # milhar "." e decimal "," (BR)
        hovermode="closest",
        hoverlabel=dict(font_size=12, font_family="Segoe UI"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, title_text=""),
        showlegend=mostrar_legenda,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig

def barra_horizontal(df, x, y, texto, titulo_x, altura=CHART_HEIGHT):
    """Fábrica única de barras horizontais — garante proporção/estilo idêntico."""
    fig = px.bar(df, x=x, y=y, orientation="h", text=texto)
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis_title=None, xaxis_title=titulo_x,
                      yaxis=dict(automargin=True))
    aplicar_tema(fig, altura=altura, mostrar_legenda=False)
    return fig


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
# Data de atualização em dd/mm/aaaa (último dia da competência mais recente)
data_atualizacao = f"01/{fim_str}"

st.title("🏥 Painel Hospitalar SP — DATAHOLICS")
st.caption(f"FIAP Challenge | Parceria Oracle — Dados SIH/DATASUS, {ini_str} a {fim_str}  ·  "
           f"Dados atualizados em: {data_atualizacao}")

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
    "Total de Internações (todo o período)",
    fmt_num(total_geral),
    help=f"Soma de todas as internações registradas no período completo disponível ({ini_str} a {fim_str})."
)
col2.metric(
    "Últimos 12 Meses",
    fmt_num(ultimos_12),
    delta=f"{fmt_num(delta_12m, 1)}% vs. 12 meses anteriores ({fmt_num(ultimos_12_anterior)})",
    delta_color="inverse",
    help="Soma dos 12 meses mais recentes disponíveis, comparada com os 12 meses imediatamente anteriores a eles."
)
col3.metric(
    f"YTD ({fim_ano})",
    fmt_num(ytd),
    delta=f"{fmt_num(delta_ytd, 1)}% vs. YTD {fim_ano - 1} ({fmt_num(ytd_anterior)})",
    delta_color="inverse",
    help=f"Year to Date: soma de janeiro até {fim_mes:02d}/{fim_ano}, comparada ao mesmo intervalo de {fim_ano - 1}."
)
col4.metric(
    f"Último Mês ({fim_str})",
    fmt_num(mes_atual),
    delta=f"{fmt_num(delta_mes, 1)}% vs. mês anterior ({fmt_num(mes_anterior)})",
    delta_color="inverse",
    help="Total do mês mais recente disponível, comparado percentualmente com o mês imediatamente anterior."
)

# ============================================================
# Gráfico de evolução mensal — VALORES ABSOLUTOS
# Top 5 regiões + "Outras Regiões" (eixo esquerdo) + "Total Geral" (eixo direito)
# O Total vai no eixo secundário para não esmagar as linhas regionais.
# ============================================================
st.subheader("📈 Evolução Mensal de Internações — Top 5 Regiões, Outras e Total Geral")
st.caption("Linhas coloridas = internações por região (eixo esquerdo). Linha pontilhada = Total Geral "
           "de SP (eixo direito). Passe o mouse para ver os valores mês a mês.")

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

# Pivota para desenhar cada série como uma linha
piv = temporal_agrupado.pivot_table(index='competencia', columns='grupo',
                                     values='QTD_INTERNACOES', aggfunc='sum').sort_index()

# Ordena as séries: top5 (na ordem do ranking) e depois "Outras Regiões"
ordem_series = [r for r in top5_regioes if r in piv.columns]
if 'Outras Regiões' in piv.columns:
    ordem_series.append('Outras Regiões')

fig_evolucao = make_subplots(specs=[[{"secondary_y": True}]])
for i, nome in enumerate(ordem_series):
    fig_evolucao.add_trace(
        go.Scatter(x=piv.index, y=piv[nome], name=nome, mode="lines+markers",
                   line=dict(width=2, color=PALETA[i % len(PALETA)]),
                   hovertemplate=f"<b>{nome}</b>: %{{y:,.0f}}<extra></extra>"),
        secondary_y=False,
    )
fig_evolucao.add_trace(
    go.Scatter(x=temporal_total['competencia'], y=temporal_total['QTD_INTERNACOES'],
               name="Total Geral", mode="lines",
               line=dict(color="#FFFFFF", width=3, dash="dot"),
               hovertemplate="<b>Total Geral</b>: %{y:,.0f}<extra></extra>"),
    secondary_y=True,
)
fig_evolucao.update_yaxes(title_text="Internações por região", secondary_y=False)
fig_evolucao.update_yaxes(title_text="Total geral (SP)", secondary_y=True, showgrid=False)
fig_evolucao.update_xaxes(title_text=None)
aplicar_tema(fig_evolucao, altura=CHART_HEIGHT_LG)
fig_evolucao.update_layout(hovermode="x unified")
st.plotly_chart(fig_evolucao, use_container_width=True, key="evolucao")

# ============================================================
# Rankings: Top 10 Regiões | Top 10 Causas | Share por Caráter
# Altura padronizada (CHART_HEIGHT) + números compactos (170k, 1,5 Mi)
# ============================================================
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("🏙️ Top 10 Regiões")
    regioes = consultar("""
        SELECT nm_regiao_saude, qtd_internacoes FROM VW_VOLUME_REGIAO
        ORDER BY qtd_internacoes DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD_INTERNACOES')
    regioes['label'] = regioes['QTD_INTERNACOES'].apply(fmt_compacto)
    fig = barra_horizontal(regioes, 'QTD_INTERNACOES', 'NM_REGIAO_SAUDE', 'label', 'Internações')
    st.plotly_chart(fig, use_container_width=True, key="top_regioes")

with col_b:
    st.subheader("🩺 Top 10 Causas")
    diagnosticos = consultar("""
        SELECT ds_diagnostico, qtd FROM VW_TOP_DIAGNOSTICOS
        ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD')
    diagnosticos['label'] = diagnosticos['QTD'].apply(fmt_compacto)
    fig = barra_horizontal(diagnosticos, 'QTD', 'DS_DIAGNOSTICO', 'label', 'Internações')
    st.plotly_chart(fig, use_container_width=True, key="top_causas")

with col_c:
    st.subheader("🚑 Share por Caráter de Internação")
    carater_share = consultar("SELECT ds_carater_internacao, qtd_internacoes FROM VW_MORTALIDADE_CARATER")
    carater_share['pct'] = carater_share['QTD_INTERNACOES'] / carater_share['QTD_INTERNACOES'].sum() * 100
    carater_share = carater_share.sort_values('pct')
    carater_share['label'] = carater_share['pct'].apply(lambda v: f"{v:.1f}%".replace('.', ','))
    fig = barra_horizontal(carater_share, 'pct', 'DS_CARATER_INTERNACAO', 'label', '% do total')
    st.plotly_chart(fig, use_container_width=True, key="share_carater")

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
fig = barra_horizontal(mortalidade.sort_values('TAXA_MORTALIDADE'),
                       'TAXA_MORTALIDADE', 'DS_CARATER_INTERNACAO', 'label', 'Taxa de mortalidade (%)')
st.plotly_chart(fig, use_container_width=True, key="mortalidade")

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
fig_capacidade.update_layout(xaxis_title='Volume de Internações',
                             yaxis_title='Internações por Leito (pressão)')
aplicar_tema(fig_capacidade, altura=CHART_HEIGHT_LG, mostrar_legenda=False)
st.plotly_chart(fig_capacidade, use_container_width=True, key="capacidade")
