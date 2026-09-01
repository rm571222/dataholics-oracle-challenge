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
CHART_HEIGHT_LG = 460       # altura para gráficos "hero" (evolução)
MARGEM_PADRAO = dict(l=10, r=30, t=30, b=10)

# Paleta categórica única (aplicada por categoria em todos os gráficos)
PALETA = ["#4C9AFF", "#F5A623", "#2ECC71", "#E74C3C", "#9B59B6",
          "#1ABC9C", "#E84393", "#F1C40F", "#95A5A6"]

# Cores de status (usadas na visão de pressão assistencial)
COR_STATUS = {"Crítico": "#E74C3C", "Atenção": "#F5A623", "Estável": "#2ECC71"}

# separators=',.'  => decimal vírgula e milhar ponto (padrão BR) em todo o Plotly
SEPARADOR_BR = ",."

st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1500px; }

[data-testid="stMetric"] {
    background-color: #1C1F26;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 15px;
}
h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }

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

def truncar(label, n=34):
    """Encurta rótulos longos p/ não comerem o espaço da barra (nome completo fica no tooltip)."""
    label = str(label)
    return label if len(label) <= n else label[:n - 1] + "…"


# ============================================================
# TEMA ÚNICO DOS GRÁFICOS  (aplicado em TODOS via aplicar_tema)
# NOTA: NÃO definimos 'title' aqui de propósito — um title sem 'text'
#       fazia o Plotly renderizar a palavra "undefined" em todo gráfico.
# ============================================================
def aplicar_tema(fig, altura=CHART_HEIGHT, mostrar_legenda=True):
    fig.update_layout(
        template="plotly_dark",
        height=altura,
        colorway=PALETA,
        font=dict(family="Segoe UI, sans-serif", size=13, color="#E6E6E6"),
        margin=MARGEM_PADRAO,
        separators=SEPARADOR_BR,                 # milhar "." e decimal "," (BR)
        hovermode="closest",
        hoverlabel=dict(font_size=12, font_family="Segoe UI"),
        showlegend=mostrar_legenda,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    if mostrar_legenda:
        # title="" (com text vazio) evita o "undefined" na legenda
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                      xanchor="left", x=0, title=dict(text="")))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig

def barra_horizontal(df, x, y_full, texto, titulo_x, altura=CHART_HEIGHT,
                     cores=None, coluna_status=None):
    """
    Fábrica única de barras horizontais.
    - y_full: coluna com o NOME COMPLETO (usada no tooltip)
    - trunca o rótulo do eixo Y, mantém o nome inteiro no hover
    """
    df = df.copy()
    df["_ylabel"] = df[y_full].apply(truncar)
    ordem = df["_ylabel"].tolist()  # preserva a ordem já sortada do df

    if coluna_status:
        fig = px.bar(df, x=x, y="_ylabel", orientation="h", text=texto,
                     color=coluna_status, color_discrete_map=COR_STATUS,
                     custom_data=[y_full])
        legenda = True
    else:
        fig = px.bar(df, x=x, y="_ylabel", orientation="h", text=texto,
                     custom_data=[y_full])
        legenda = False
        if cores:
            fig.update_traces(marker_color=cores)

    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title=titulo_x,
                      yaxis=dict(automargin=True, categoryorder="array", categoryarray=ordem))
    aplicar_tema(fig, altura=altura, mostrar_legenda=legenda)
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
# Evolução mensal — 2 PAINÉIS EMPILHADOS
#   • Painel de cima : Total Geral (fica SEMPRE acima, por construção)
#   • Painel de baixo: Top 5 regiões (escala comparável entre si)
#   "Outras Regiões" foi removida por ser um agregado que distorce a leitura.
# ============================================================
st.subheader("📈 Evolução Mensal de Internações")
st.caption("Painel superior: total do estado de SP (linha de referência). "
           "Painel inferior: as 5 regiões com maior volume, em escala comparável entre si.")

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
# Total geral por mês (todas as regiões)
temporal_total = temporal_completo.groupby('competencia')['QTD_INTERNACOES'].sum().reset_index()
# Série por região (só as top 5)
top5_df = temporal_completo[temporal_completo['NM_REGIAO_SAUDE'].isin(top5_regioes)]
piv = top5_df.pivot_table(index='competencia', columns='NM_REGIAO_SAUDE',
                          values='QTD_INTERNACOES', aggfunc='sum').sort_index()

fig_evolucao = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
    row_heights=[0.34, 0.66],
    subplot_titles=("Total Geral — Estado de SP", "Top 5 Regiões (comparação)")
)
# Painel superior: Total
fig_evolucao.add_trace(
    go.Scatter(x=temporal_total['competencia'], y=temporal_total['QTD_INTERNACOES'],
               name="Total Geral", mode="lines", line=dict(color="#FFFFFF", width=3),
               fill="tozeroy", fillcolor="rgba(255,255,255,0.06)",
               hovertemplate="Total: %{y:,.0f}<extra></extra>", showlegend=False),
    row=1, col=1
)
# Painel inferior: Top 5 regiões
for i, nome in enumerate(top5_regioes):
    if nome in piv.columns:
        fig_evolucao.add_trace(
            go.Scatter(x=piv.index, y=piv[nome], name=nome, mode="lines",
                       line=dict(width=2, color=PALETA[i % len(PALETA)]),
                       hovertemplate=f"<b>{nome}</b>: %{{y:,.0f}}<extra></extra>"),
            row=2, col=1
        )
fig_evolucao.update_yaxes(title_text="Total (SP)", row=1, col=1, rangemode="tozero")
fig_evolucao.update_yaxes(title_text="Internações", row=2, col=1)
aplicar_tema(fig_evolucao, altura=CHART_HEIGHT_LG, mostrar_legenda=True)
fig_evolucao.update_layout(hovermode="x unified")
st.plotly_chart(fig_evolucao, use_container_width=True, key="evolucao")

# ============================================================
# Rankings: Top 10 Regiões | Top 10 Causas | Share por Caráter
# Rótulos truncados (nome completo no tooltip) + altura padronizada
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
    st.subheader("🚑 Share por Caráter")
    carater_share = consultar("SELECT ds_carater_internacao, qtd_internacoes FROM VW_MORTALIDADE_CARATER")
    carater_share['pct'] = carater_share['QTD_INTERNACOES'] / carater_share['QTD_INTERNACOES'].sum() * 100
    # Mantém só o que é relevante (>=1%) para não poluir com categorias de 0,0%
    carater_share = carater_share[carater_share['pct'] >= 1].sort_values('pct')
    carater_share['label'] = carater_share['pct'].apply(lambda v: f"{v:.1f}%".replace('.', ','))
    fig = barra_horizontal(carater_share, 'pct', 'DS_CARATER_INTERNACAO', 'label', '% do total')
    st.plotly_chart(fig, use_container_width=True, key="share_carater")

# ============================================================
# Achado-chave: Urgência mata mais que Eletivo (com o "so what")
# Reframe: foco nos 2 caráteres principais + múltiplo de risco em destaque
# ============================================================
st.subheader("⚠️ O peso da Urgência: mais volume e mais letal")

mort = consultar("""
    SELECT ds_carater_internacao, qtd_internacoes, taxa_mortalidade
    FROM VW_MORTALIDADE_CARATER
""")
# Foca nos 2 caráteres de maior volume (tipicamente Urgência e Eletivo)
principais = mort.sort_values('QTD_INTERNACOES', ascending=False).head(2).reset_index(drop=True)

def _busca(df, chave):
    m = df[df['DS_CARATER_INTERNACAO'].str.contains(chave, case=False, na=False)]
    return m.iloc[0] if len(m) else None

urg = _busca(mort, "urg")
ele = _busca(mort, "eletiv")

c1, c2 = st.columns([1, 2])
with c1:
    if urg is not None and ele is not None and ele['TAXA_MORTALIDADE']:
        multiplo = urg['TAXA_MORTALIDADE'] / ele['TAXA_MORTALIDADE']
        st.metric(
            "Risco relativo (Urgência ÷ Eletivo)",
            f"{fmt_num(multiplo, 1)}x",
            help="Quantas vezes a mortalidade de internações de urgência é maior que a de eletivas."
        )
        st.caption(f"Urgência: **{fmt_num(urg['TAXA_MORTALIDADE'],2)}%**  ·  "
                   f"Eletivo: **{fmt_num(ele['TAXA_MORTALIDADE'],2)}%**")
    st.caption("A urgência concentra a maior parte do volume **e** a maior letalidade — "
               "é onde priorizar leitos, fluxo e retaguarda faz mais diferença.")
with c2:
    comp = principais.copy().sort_values('TAXA_MORTALIDADE')
    comp['label'] = comp['TAXA_MORTALIDADE'].apply(lambda v: f"{v:.2f}%".replace('.', ','))
    cores = [COR_STATUS["Crítico"] if "urg" in str(n).lower() else PALETA[0]
             for n in comp['DS_CARATER_INTERNACAO']]
    fig = barra_horizontal(comp, 'TAXA_MORTALIDADE', 'DS_CARATER_INTERNACAO', 'label',
                           'Taxa de mortalidade (%)', cores=cores)
    st.plotly_chart(fig, use_container_width=True, key="mortalidade_foco")

# ============================================================
# Seção 2 — Pressão Assistencial (versão EXECUTIVA)
# Ranking de regiões por internações/leito, colorido por status de alerta.
# (Substitui o scatter técnico volume x pressão x tamanho de bolha.)
# ============================================================
st.header("Seção 2 — Pressão Assistencial")
st.caption("Regiões ordenadas pela pressão sobre a estrutura (internações por leito no período). "
           "🔴 Crítico e 🟡 Atenção indicam onde a demanda mais aperta a capacidade instalada.")

capacidade_completa = consultar("SELECT * FROM VW_CAPACIDADE_REGIAO")

# Classificação de status por tercis (relativa ao próprio conjunto de regiões)
q_hi = capacidade_completa['INTERNACOES_POR_LEITO'].quantile(0.66)
q_lo = capacidade_completa['INTERNACOES_POR_LEITO'].quantile(0.33)
def _status(v):
    if v >= q_hi: return "Crítico"
    if v >= q_lo: return "Atenção"
    return "Estável"
capacidade_completa['status'] = capacidade_completa['INTERNACOES_POR_LEITO'].apply(_status)
mediana_pressao = capacidade_completa['INTERNACOES_POR_LEITO'].median()

top_pressao = (capacidade_completa
               .sort_values('INTERNACOES_POR_LEITO', ascending=False)
               .head(12)
               .sort_values('INTERNACOES_POR_LEITO'))
top_pressao['label'] = top_pressao['INTERNACOES_POR_LEITO'].apply(lambda v: fmt_num(v, 1))

fig_pressao = barra_horizontal(
    top_pressao, 'INTERNACOES_POR_LEITO', 'NM_REGIAO_SAUDE', 'label',
    'Internações por leito', altura=CHART_HEIGHT + 40, coluna_status='status'
)
fig_pressao.add_vline(x=mediana_pressao, line_dash='dash', line_color='gray',
                      annotation_text=f"Mediana ({fmt_num(mediana_pressao,1)})",
                      annotation_position="top")
st.plotly_chart(fig_pressao, use_container_width=True, key="pressao")

# KPIs de apoio da Seção 2
n_critico = int((capacidade_completa['status'] == "Crítico").sum())
n_atencao = int((capacidade_completa['status'] == "Atenção").sum())
n_estavel = int((capacidade_completa['status'] == "Estável").sum())
k1, k2, k3 = st.columns(3)
k1.metric("🔴 Regiões em estado Crítico", fmt_num(n_critico))
k2.metric("🟡 Regiões em Atenção", fmt_num(n_atencao))
k3.metric("🟢 Regiões Estáveis", fmt_num(n_estavel))
