import streamlit as st
import oracledb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64, os, zipfile, io, re, math

# ============================================================
# CONFIG GLOBAL
# ============================================================
st.set_page_config(
    page_title="Painel Hospitalar SP - DATAHOLICS",
    page_icon="🏥",
    layout="wide",
)

CHART_HEIGHT = 380
CHART_HEIGHT_LG = 460
MARGEM_PADRAO = dict(l=10, r=30, t=30, b=10)

PALETA = ["#4C9AFF", "#F5A623", "#2ECC71", "#E74C3C", "#9B59B6",
          "#1ABC9C", "#E84393", "#F1C40F", "#95A5A6"]

COR_STATUS = {"Crítico": "#E74C3C", "Atenção": "#F5A623", "Estável": "#2ECC71"}
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
# CONEXÃO E CONSULTA  (com reconexão automática)
# A conexão fica em cache_resource, mas o Oracle derruba a sessão por
# ociosidade/reinício do worker no Streamlit Cloud. Para evitar o erro
# "not connected" (_check_connected), fazemos ping e reconectamos se cair.
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
    """Devolve uma conexão viva: faz ping e reconecta (limpando o cache) se cair."""
    conn = conectar()
    try:
        conn.ping()                      # valida a sessão; lança erro se estiver morta
        return conn
    except Exception:
        conectar.clear()                 # descarta a conexão morta do cache_resource
        return conectar()                # cria e cacheia uma nova

@st.cache_data(ttl=3600)
def consultar(query):
    """Executa a query reaproveitando a conexão; em caso de queda, reconecta 1x e tenta de novo."""
    try:
        return pd.read_sql(query, _get_conexao())
    except oracledb.DatabaseError:
        conectar.clear()                 # força recriação da conexão
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
    """Encurta rótulos longos (nome completo fica no tooltip)."""
    label = str(label)
    return label if len(label) <= n else label[:n - 1] + "…"

def simplificar_causa(texto):
    """Remove ruído clínico de CID: '... não especificada', 'de localização ...', etc."""
    if texto is None:
        return "Não informado"
    t = str(texto).strip()
    if t.lower() in ("nan", "none", "null", ""):
        return "Não informado"
    t = re.sub(r",?\s*(de\s+\w+\s+)?n[ãa]o\s+especificad[oa].*$", "", t, flags=re.IGNORECASE)
    t = t.strip(" ,;")
    return t if t else "Não informado"


# ============================================================
# TEMA ÚNICO DOS GRÁFICOS
# ============================================================
def aplicar_tema(fig, altura=CHART_HEIGHT, mostrar_legenda=True):
    fig.update_layout(
        template="plotly_dark",
        height=altura,
        colorway=PALETA,
        font=dict(family="Segoe UI, sans-serif", size=13, color="#E6E6E6"),
        margin=MARGEM_PADRAO,
        separators=SEPARADOR_BR,
        hovermode="closest",
        hoverlabel=dict(font_size=12, font_family="Segoe UI"),
        showlegend=mostrar_legenda,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    if mostrar_legenda:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                      xanchor="left", x=0, title=dict(text="")))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig

def barra_horizontal(df, x, y_full, texto, titulo_x, altura=CHART_HEIGHT, cores=None):
    """Fábrica única de barras horizontais. Trunca rótulo, mantém nome completo no hover."""
    df = df.copy()
    df["_ylabel"] = df[y_full].apply(truncar)
    ordem = df["_ylabel"].tolist()
    fig = px.bar(df, x=x, y="_ylabel", orientation="h", text=texto, custom_data=[y_full])
    if cores:
        fig.update_traces(marker_color=cores)
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title=titulo_x,
                      yaxis=dict(automargin=True, categoryorder="array", categoryarray=ordem))
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
data_atualizacao = f"01/{fim_str}"

st.title("🏥 Painel Hospitalar SP — DATAHOLICS")
st.caption(f"FIAP Challenge | Parceria Oracle — Dados SIH/DATASUS, {ini_str} a {fim_str}  ·  "
           f"Dados atualizados em: {data_atualizacao}")

st.header("Seção 1 — Visão Executiva")

# ============================================================
# KPIs
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
col1.metric("Total de Internações (todo o período)", fmt_num(total_geral),
            help=f"Soma de todas as internações registradas no período completo ({ini_str} a {fim_str}).")
col2.metric("Últimos 12 Meses", fmt_num(ultimos_12),
            delta=f"{fmt_num(delta_12m, 1)}% vs. 12 meses anteriores ({fmt_num(ultimos_12_anterior)})",
            delta_color="inverse",
            help="Soma dos 12 meses mais recentes, comparada com os 12 meses imediatamente anteriores.")
col3.metric(f"YTD ({fim_ano})", fmt_num(ytd),
            delta=f"{fmt_num(delta_ytd, 1)}% vs. YTD {fim_ano - 1} ({fmt_num(ytd_anterior)})",
            delta_color="inverse",
            help=f"Year to Date: soma de janeiro até {fim_mes:02d}/{fim_ano}, comparada ao mesmo intervalo de {fim_ano - 1}.")
col4.metric(f"Último Mês ({fim_str})", fmt_num(mes_atual),
            delta=f"{fmt_num(delta_mes, 1)}% vs. mês anterior ({fmt_num(mes_anterior)})",
            delta_color="inverse",
            help="Total do mês mais recente, comparado com o mês imediatamente anterior.")

# ============================================================
# Evolução mensal — 2 painéis empilhados (X compartilhado)
# ============================================================
st.subheader("📈 Evolução Mensal de Internações")
st.caption("Painel superior: total do estado de SP. Painel inferior: as 5 regiões de maior volume — "
           "eixo em proporção logarítmica para revelar padrões e sazonalidade, com rótulos em volume real.")

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
temporal_total = temporal_completo.groupby('competencia')['QTD_INTERNACOES'].sum().reset_index()
top5_df = temporal_completo[temporal_completo['NM_REGIAO_SAUDE'].isin(top5_regioes)]
piv = top5_df.pivot_table(index='competencia', columns='NM_REGIAO_SAUDE',
                          values='QTD_INTERNACOES', aggfunc='sum').sort_index()

fig_evolucao = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
    row_heights=[0.22, 0.78], subplot_titles=("", "Top 5 Regiões")
)
# Painel superior: Total (linha única, sem eixo Y, rótulos por ponto + nome/valor no fim)
rotulos_total = [fmt_compacto(v) for v in temporal_total['QTD_INTERNACOES']]
fig_evolucao.add_trace(
    go.Scatter(x=temporal_total['competencia'], y=temporal_total['QTD_INTERNACOES'],
               name="Total Geral", mode="lines+markers+text",
               line=dict(color="#FFFFFF", width=3), marker=dict(size=4, color="#FFFFFF"),
               text=rotulos_total, textposition="top center",
               textfont=dict(size=10, color="#CFCFCF"),
               hovertemplate="Total: %{y:,.0f}<extra></extra>", showlegend=False),
    row=1, col=1
)
_ult_x = temporal_total['competencia'].iloc[-1]
_ult_y = temporal_total['QTD_INTERNACOES'].iloc[-1]
fig_evolucao.add_trace(
    go.Scatter(x=[_ult_x + pd.Timedelta(days=8)], y=[_ult_y], mode="text",
               text=[f"Total Geral — {fmt_compacto(_ult_y)}"], textposition="middle right",
               textfont=dict(color="#FFFFFF", size=12), cliponaxis=False,
               hoverinfo="skip", showlegend=False),
    row=1, col=1
)

# Painel inferior: Top 5 — linhas limpas; rótulo só no último ponto + nome ao lado.
# Desencontro vertical p/ nomes que se cruzam: verde acima, vermelho meio, roxo abaixo.
_ult_x_reg = piv.index[-1]
_desloca_y = {"GRANDE ABC": 1.15, "ALTO DO TIETE": 0.98, "ROTA DOS BANDEIRANTES": 0.82}
for i, nome in enumerate(top5_regioes):
    if nome in piv.columns:
        cor = PALETA[i % len(PALETA)]
        ult_valor = piv[nome].iloc[-1]
        fig_evolucao.add_trace(
            go.Scatter(x=piv.index, y=piv[nome], name=nome, mode="lines",
                       line=dict(width=2, color=cor),
                       hovertemplate=f"<b>{nome}</b>: %{{y:,.0f}}<extra></extra>"),
            row=2, col=1
        )
        # Nome + valor no fim; cliponaxis=False deixa transbordar p/ a margem (não corta)
        y_label = ult_valor * _desloca_y.get(nome.upper(), 1.0)
        fig_evolucao.add_trace(
            go.Scatter(x=[_ult_x_reg + pd.Timedelta(days=8)], y=[y_label], mode="text",
                       text=[f"{nome} — {fmt_compacto(ult_valor)}"], textposition="middle right",
                       textfont=dict(color=cor, size=11), cliponaxis=False,
                       hoverinfo="skip", showlegend=False),
            row=2, col=1
        )

fig_evolucao.update_yaxes(visible=False, showgrid=False, row=1, col=1)
_ticks = [10000, 20000, 30000, 40000, 50000, 60000, 70000]
fig_evolucao.update_yaxes(
    type="log", title_text="Internações", row=2, col=1,
    tickmode="array", tickvals=_ticks, ticktext=[fmt_compacto(v) for v in _ticks]
)
# Pequeno respiro interno (só p/ afastar os textos da última coluna de dados) +
# margem direita ampla p/ os rótulos transbordarem sem cortar "Campinas".
_ticks_x = pd.date_range(start=piv.index.min(), end=piv.index.max(), freq="3MS")
fig_evolucao.update_xaxes(
    range=[piv.index.min(), piv.index.max() + pd.Timedelta(days=20)],
    tickmode="array", tickvals=_ticks_x,
    ticktext=[d.strftime("%b %Y") for d in _ticks_x], row=2, col=1
)
aplicar_tema(fig_evolucao, altura=560, mostrar_legenda=False)
fig_evolucao.update_layout(hovermode="x unified",
                           margin=dict(l=10, r=230, t=30, b=10))  # r alto = espaço p/ nomes
st.plotly_chart(fig_evolucao, use_container_width=True, key="evolucao")

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
    regioes['label'] = regioes['QTD_INTERNACOES'].apply(fmt_compacto)
    fig = barra_horizontal(regioes, 'QTD_INTERNACOES', 'NM_REGIAO_SAUDE', 'label', 'Internações')
    st.plotly_chart(fig, use_container_width=True, key="top_regioes")

with col_b:
    st.subheader("🩺 Top 10 Causas")
    diagnosticos = consultar("""
        SELECT ds_diagnostico, qtd FROM VW_TOP_DIAGNOSTICOS
        ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY
    """).sort_values('QTD')
    diagnosticos['DS_DIAGNOSTICO'] = diagnosticos['DS_DIAGNOSTICO'].apply(simplificar_causa)
    diagnosticos['label'] = diagnosticos['QTD'].apply(fmt_compacto)
    fig = barra_horizontal(diagnosticos, 'QTD', 'DS_DIAGNOSTICO', 'label', 'Internações')
    st.plotly_chart(fig, use_container_width=True, key="top_causas")

with col_c:
    st.subheader("🚑 Share por Caráter")
    carater_share = consultar("SELECT ds_carater_internacao, qtd_internacoes FROM VW_MORTALIDADE_CARATER")
    carater_share['pct'] = carater_share['QTD_INTERNACOES'] / carater_share['QTD_INTERNACOES'].sum() * 100
    carater_share = carater_share[carater_share['pct'] >= 1].sort_values('pct')
    carater_share['label'] = carater_share['pct'].apply(lambda v: f"{v:.1f}%".replace('.', ','))
    fig = barra_horizontal(carater_share, 'pct', 'DS_CARATER_INTERNACAO', 'label', '% do total')
    st.plotly_chart(fig, use_container_width=True, key="share_carater")

# ============================================================
# Seção 2 — Pressão Assistencial (BORBOLETA: região no CENTRO)
# ============================================================
st.header("Seção 2 — Pressão Assistencial")
st.caption("Cada linha é uma região de saúde (nome ao centro). À esquerda, o volume de internações, "
           "com a quantidade de leitos da região na extremidade esquerda; "
           "à direita, a pressão sobre a estrutura (internações por leito). "
           "🔴 Crítico · 🟡 Atenção · 🟢 Estável — pela mediana estadual de pressão.")

capacidade_completa = consultar("SELECT * FROM VW_CAPACIDADE_REGIAO")

q_hi = capacidade_completa['INTERNACOES_POR_LEITO'].quantile(0.66)
q_lo = capacidade_completa['INTERNACOES_POR_LEITO'].quantile(0.33)
def _status(v):
    if v >= q_hi: return "Crítico"
    if v >= q_lo: return "Atenção"
    return "Estável"
capacidade_completa['status'] = capacidade_completa['INTERNACOES_POR_LEITO'].apply(_status)
mediana_pressao = capacidade_completa['INTERNACOES_POR_LEITO'].median()

borb = capacidade_completa.sort_values('INTERNACOES_POR_LEITO', ascending=True).copy()
cores = borb['status'].map(COR_STATUS).tolist()
altura_borboleta = max(650, len(borb) * 22)

fig_borb = make_subplots(
    rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.0,
    column_widths=[0.42, 0.16, 0.42],
    subplot_titles=("Internações (volume)", "", "Internações por leito (pressão)")
)

# Esquerda: barra de internações (log, espelhada) + rótulo de volume no início da barra
fig_borb.add_trace(
    go.Bar(y=borb['NM_REGIAO_SAUDE'], x=borb['INTERNACOES'], orientation='h',
           marker_color=cores, name="Volume",
           text=[fmt_compacto(v) for v in borb['INTERNACOES']],
           textposition="outside", cliponaxis=False,
           customdata=borb['NM_REGIAO_SAUDE'],
           hovertemplate="<b>%{customdata}</b><br>Internações: %{x:,.0f}<extra></extra>"),
    row=1, col=1
)
_ticks_vol = [10000, 50000, 100000, 500000, 1000000]
# Range explícito (log, espelhado) com folga externa p/ os leitos ficarem FORA do gráfico
_int_max = float(borb['INTERNACOES'].max())
_outer = _int_max * 6.0          # borda externa ampla → separa o "1,6 Mi" da coluna de leitos
_inner = 1500.0                  # borda interna (centro) — base das barras
fig_borb.update_xaxes(
    type="log", range=[math.log10(_outer), math.log10(_inner)], row=1, col=1,
    tickmode="array", tickvals=_ticks_vol,
    ticktext=[fmt_compacto(v) for v in _ticks_vol]
)
# nº de leitos FORA do gráfico, na extremidade esquerda (coluna própria, auto-explicativa)
_x_leitos = _outer * 0.95        # bem na borda esquerda, antes das barras começarem
fig_borb.add_trace(
    go.Scatter(y=borb['NM_REGIAO_SAUDE'], x=[_x_leitos] * len(borb), mode="text",
               text=[f"{fmt_num(v)} leitos" for v in borb['LEITOS_REGIAO']],
               textposition="middle right", textfont=dict(size=10, color="#AAB4BF"),
               hoverinfo="skip", showlegend=False),
    row=1, col=1
)

# Centro: rótulos das regiões
fig_borb.add_trace(
    go.Scatter(y=borb['NM_REGIAO_SAUDE'], x=[0] * len(borb), mode="text",
               text=[truncar(n, 24) for n in borb['NM_REGIAO_SAUDE']],
               textposition="middle center", textfont=dict(size=11, color="#E6E6E6"),
               hoverinfo="skip", showlegend=False),
    row=1, col=2
)
# Direita: pressão
fig_borb.add_trace(
    go.Bar(y=borb['NM_REGIAO_SAUDE'], x=borb['INTERNACOES_POR_LEITO'], orientation='h',
           marker_color=cores, name="Pressão",
           text=[fmt_num(v, 1) for v in borb['INTERNACOES_POR_LEITO']],
           textposition="outside", cliponaxis=False,
           customdata=borb['NM_REGIAO_SAUDE'],
           hovertemplate="<b>%{customdata}</b><br>Internações/leito: %{x:,.1f}<extra></extra>"),
    row=1, col=3
)
fig_borb.update_yaxes(showticklabels=False, showgrid=False, row=1, col=1)
fig_borb.update_yaxes(showticklabels=False, showgrid=False, row=1, col=2)
fig_borb.update_yaxes(showticklabels=False, showgrid=False, row=1, col=3)
fig_borb.update_xaxes(visible=False, row=1, col=2)
fig_borb.add_vline(x=mediana_pressao, line_dash='dash', line_color='gray',
                   annotation_text=f"Mediana: {fmt_num(mediana_pressao,1)}",
                   annotation_position="bottom right", row=1, col=3)
aplicar_tema(fig_borb, altura=altura_borboleta, mostrar_legenda=False)
fig_borb.update_layout(bargap=0.25)
for ann in fig_borb.layout.annotations:
    if ann.text in ("Internações (volume)", "Internações por leito (pressão)"):
        ann.yshift = 10
st.plotly_chart(fig_borb, use_container_width=True, key="borboleta")

n_critico = int((capacidade_completa['status'] == "Crítico").sum())
n_atencao = int((capacidade_completa['status'] == "Atenção").sum())
n_estavel = int((capacidade_completa['status'] == "Estável").sum())
k1, k2, k3 = st.columns(3)
k1.metric("🔴 Regiões em estado Crítico", fmt_num(n_critico))
k2.metric("🟡 Regiões em Atenção", fmt_num(n_atencao))
k3.metric("🟢 Regiões Estáveis", fmt_num(n_estavel))
