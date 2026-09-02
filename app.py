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
st.set_page_config(page_title="Painel Hospitalar SP - SampaSUS", page_icon="🏥",
                   layout="wide", initial_sidebar_state="expanded")

CHART_HEIGHT = 380
MARGEM_PADRAO = dict(l=10, r=30, t=30, b=10)
# Paleta categórica (tema claro)
PALETA = ["#2F6DB5", "#E8703A", "#2E9E5B", "#E74C3C", "#8E5FB0",
          "#1AA6A6", "#D6568C", "#E0A400", "#7A8794"]
COR_STATUS = {"Crítico": "#E74C3C", "Atenção": "#E39A0C", "Estável": "#2E9E5B"}
SEPARADOR_BR = ",."
OCUP_CRITICO = 70.0
OCUP_ATENCAO = 55.0
_MESES_PT = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# --- Identidade SampaSUS (tema claro) ---
NAVY        = "#0B2440"   # primária / títulos
BG          = "#F5F7FA"   # fundo
CARD_BG     = "#FFFFFF"   # cards / superfícies
TEXTO       = "#1C2833"   # texto principal
TEXTO_SUAVE = "#5A6B7B"   # texto secundário / captions
BORDA       = "#E2E8F0"   # bordas sutis
GRID        = "rgba(28,40,51,0.08)"
MAPA_STYLE  = "carto-positron"

# Logo em base64 (assets/sampasus_logo.png). Fallback silencioso se ausente.
try:
    with open(os.path.join("assets", "sampasus_logo.png"), "rb") as _f:
        _LOGO_B64 = base64.b64encode(_f.read()).decode()
except Exception:
    _LOGO_B64 = ""

st.markdown(f"""
<style>
/* Centraliza o conteúdo (sidebar aberta ou fechada) + respiro p/ o logo */
.block-container {{ padding-top: 3.2rem; padding-bottom: 2rem; max-width: 1500px;
    margin-left: auto !important; margin-right: auto !important; }}
[data-testid="stMain"] {{ display: flex; flex-direction: column; align-items: center; }}
[data-testid="stMain"] .block-container {{ width: 100%; }}
/* Cards de métrica nativos — tema claro */
[data-testid="stMetric"] {{ background:{CARD_BG}; border:1px solid {BORDA}; border-radius:10px;
    padding:15px; min-height:120px; }}
h1, h2, h3 {{ font-family: 'Segoe UI', sans-serif; color:{NAVY}; }}
section[data-testid="stSidebar"] {{ min-width: 330px; width: 330px; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.55rem; }}
section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stSlider label {{ font-size: 0.85rem; margin-bottom: 0; }}
.sec-divider {{ border:none; border-top:2px solid {BORDA}; margin:2.2rem 0 1rem; }}
/* Separação vertical entre os 3 gráficos do Perfil da Demanda */
.trio-col {{ border-right:1px solid {BORDA}; padding:0 14px; }}
.trio-col:last-child {{ border-right:none; }}
.trio-col h3 {{ text-align:center; }}
/* Logo SampaSUS fixo no topo direito */
.sampasus-logo {{ position: fixed; top: 12px; right: 22px; z-index: 1000;
    width: 132px; height: 81px;
    background-image: url("data:image/png;base64,{_LOGO_B64}");
    background-size: contain; background-repeat: no-repeat; background-position: center;
    filter: drop-shadow(0 2px 6px rgba(11,36,64,0.18)); }}
@media (max-width: 640px) {{ .sampasus-logo {{ width: 96px; height: 59px; }} }}
</style>
<div class="sampasus-logo"></div>
""", unsafe_allow_html=True)

def divisor():
    st.markdown("<hr class='sec-divider'>", unsafe_allow_html=True)


# ============================================================
# CONEXÃO E CONSULTA
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
        wallet_location=wallet_path, wallet_password=st.secrets["wallet_password"])

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
# FORMATAÇÃO
# ============================================================
def fmt_num(v, casas=0):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_inteiro(v):
    return fmt_num(math.floor(float(v) + 0.5), 0)

def fmt_compacto(v):
    if abs(v) >= 1_000_000: return f"{v/1_000_000:.1f}".replace('.', ',') + " Mi"
    if abs(v) >= 1_000:     return f"{v/1_000:.0f}k"
    return f"{v:.0f}"

def truncar(s, n=34):
    s = str(s)
    return s if len(s) <= n else s[:n-1] + "…"

def simplificar_causa(t):
    if t is None: return "Não informado"
    t = str(t).strip()
    if t.lower() in ("nan", "none", "null", ""): return "Não informado"
    t = re.sub(r",?\s*(de\s+\w+\s+)?n[ãa]o\s+especificad[oa].*$", "", t, flags=re.IGNORECASE)
    return t.strip(" ,;") or "Não informado"

def mes_curto(comp):
    return f"{_MESES_PT[comp % 100]}/{str(comp // 100)[2:]}"

def esc(s):
    return str(s).replace("'", "''")

def lst_sql(vals):
    return ", ".join(f"'{esc(v)}'" for v in vals)


# ============================================================
# TEMA (claro)
# ============================================================
def aplicar_tema(fig, altura=CHART_HEIGHT, legenda=False):
    fig.update_layout(template="plotly_white", height=altura, colorway=PALETA,
                      font=dict(family="Segoe UI, sans-serif", size=13, color=TEXTO),
                      margin=MARGEM_PADRAO, separators=SEPARADOR_BR, hovermode="closest",
                      hoverlabel=dict(font_size=12, font_family="Segoe UI"), showlegend=legenda,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    if legenda:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                      xanchor="left", x=0, title=dict(text="")))
    fig.update_xaxes(showgrid=False, zeroline=False, color=TEXTO)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=TEXTO)
    return fig

def barra_h(df, x, y_full, texto, titulo_x=None, altura=CHART_HEIGHT, cores=None,
            eixo_x=True, ordem_cat=None):
    """Barra horizontal padronizada. eixo_x=False esconde ticks e abre headroom p/ rótulos."""
    d = df.copy()
    d["_y"] = d[y_full].apply(truncar)
    ordem = ordem_cat if ordem_cat is not None else d["_y"].tolist()
    fig = px.bar(d, x=x, y="_y", orientation="h", text=texto, custom_data=[y_full])
    if cores is not None:
        fig.update_traces(marker_color=cores)
    fig.update_traces(textposition="outside", cliponaxis=False,
                      textfont=dict(size=11, color=TEXTO),
                      hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title=(titulo_x if eixo_x else None),
                      yaxis=dict(automargin=True, categoryorder="array", categoryarray=ordem))
    if not eixo_x:
        xmax = float(pd.to_numeric(d[x], errors="coerce").replace([float('inf')], pd.NA).max() or 0)
        fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, xmax * 1.32])
    aplicar_tema(fig, altura=altura)
    fig.update_layout(margin=dict(l=10, r=20, t=30, b=10))
    return fig

def status_ocup(v):
    if pd.isna(v): return "Sem dado"
    if v >= OCUP_CRITICO: return "Crítico"
    if v >= OCUP_ATENCAO: return "Atenção"
    return "Estável"

def mini_card(cor, emoji, tit, val, sub=""):
    sub_html = f"<div style='color:{cor}; font-size:0.8rem;'>{sub}</div>" if sub else ""
    return (f"<div style='background:{CARD_BG}; border:1px solid {BORDA}; border-left:5px solid {cor}; "
            f"border-radius:10px; padding:12px 14px; min-height:96px;'>"
            f"<div style='color:{TEXTO_SUAVE}; font-size:0.8rem;'>{emoji} {tit}</div>"
            f"<div style='font-size:1.7rem; font-weight:700; color:{NAVY}; line-height:1.1;'>{fmt_num(val)}</div>"
            f"{sub_html}</div>")


# ============================================================
# DIMENSÕES (1x)
# ============================================================
@st.cache_data(ttl=3600)
def carregar_periodo():
    p = consultar("""
        SELECT MIN(nr_ano_competencia*100+nr_mes_competencia) AS ini,
               MAX(nr_ano_competencia*100+nr_mes_competencia) AS fim
        FROM VW_INTERNACAO_COMPLETA""")
    return int(p['INI'][0]), int(p['FIM'][0])

@st.cache_data(ttl=3600)
def carregar_dim():
    df = consultar("""
        SELECT cd_hospital, nm_hospital, nm_regiao_saude, nm_municipio, esfera_admin,
               latitude, longitude, leitos_sus
        FROM VW_HOSPITAL_PERMANENCIA""")
    for c in ['ESFERA_ADMIN', 'NM_HOSPITAL']:
        df[c] = df[c].astype(str).str.replace('"', '', regex=False).str.strip()
    return df

@st.cache_data(ttl=3600)
def carregar_valores(coluna):
    """Valores distintos de uma coluna categórica da base fato (para filtros)."""
    df = consultar(f"""SELECT DISTINCT {coluna} AS v FROM VW_INTERNACAO_COMPLETA
        WHERE {coluna} IS NOT NULL ORDER BY {coluna}""")
    return df['V'].dropna().astype(str).tolist()

ini_comp, fim_comp = carregar_periodo()
dim = carregar_dim()

def range_competencias(ini, fim):
    out, a, m = [], ini // 100, ini % 100
    while a * 100 + m <= fim:
        out.append(a * 100 + m); m += 1
        if m > 12: m = 1; a += 1
    return out
competencias = range_competencias(ini_comp, fim_comp)


# ============================================================
# SIDEBAR — FILTROS (Seção 2 em diante)
# ============================================================
st.sidebar.title("🎛️ Filtros")
st.sidebar.caption("Aplicam-se da Seção 2 em diante.")

periodo_sel = st.sidebar.select_slider(
    "Período (competência)", options=competencias,
    value=(ini_comp, fim_comp), format_func=mes_curto)
regioes_sel = st.sidebar.multiselect(
    "Região de saúde", sorted(dim['NM_REGIAO_SAUDE'].dropna().unique()))
dim_m = dim[dim['NM_REGIAO_SAUDE'].isin(regioes_sel)] if regioes_sel else dim
municipios_sel = st.sidebar.multiselect(
    "Município", sorted(dim_m['NM_MUNICIPIO'].dropna().unique()))
esferas_sel = st.sidebar.multiselect(
    "Esfera administrativa", sorted(dim['ESFERA_ADMIN'].dropna().unique()))
carater_sel = st.sidebar.multiselect(
    "Caráter da internação", carregar_valores("ds_carater_internacao"))
complex_sel = st.sidebar.multiselect(
    "Complexidade", carregar_valores("ds_complexidade"))
sexo_sel = st.sidebar.multiselect(
    "Sexo", carregar_valores("ds_sexo"))
raca_sel = st.sidebar.multiselect(
    "Raça/cor", carregar_valores("ds_raca_cor"))
diag_sel = []  # filtro de diagnóstico removido (volume alto demais)

if st.sidebar.button("↺ Limpar filtros"):
    st.rerun()

comp_ini, comp_fim = periodo_sel
n_meses = competencias.index(comp_fim) - competencias.index(comp_ini) + 1
dias_periodo = n_meses * 30.4375

where = f" WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN {comp_ini} AND {comp_fim}"
if regioes_sel:
    where += f" AND nm_regiao_saude IN ({lst_sql(regioes_sel)})"
if municipios_sel:
    where += f" AND nm_municipio IN ({lst_sql(municipios_sel)})"
if esferas_sel:
    cds = [str(c).zfill(10) for c in dim[dim['ESFERA_ADMIN'].isin(esferas_sel)]['CD_HOSPITAL']] or ['__none__']
    where += f" AND LPAD(cd_hospital,10,'0') IN ({lst_sql(cds)})"
if carater_sel:
    where += f" AND ds_carater_internacao IN ({lst_sql(carater_sel)})"
if complex_sel:
    where += f" AND ds_complexidade IN ({lst_sql(complex_sel)})"
if sexo_sel:
    where += f" AND ds_sexo IN ({lst_sql(sexo_sel)})"
if raca_sel:
    where += f" AND ds_raca_cor IN ({lst_sql(raca_sel)})"

_extra = []
if carater_sel: _extra.append(f"{len(carater_sel)} caráter")
if complex_sel: _extra.append(f"{len(complex_sel)} complexidade")
if sexo_sel: _extra.append("sexo")
if raca_sel: _extra.append("raça/cor")
recorte_txt = (f"{mes_curto(comp_ini)} a {mes_curto(comp_fim)}"
               + (f" · {len(regioes_sel)} região(ões)" if regioes_sel else "")
               + (f" · {len(municipios_sel)} município(s)" if municipios_sel else "")
               + (f" · {', '.join(esferas_sel)}" if esferas_sel else "")
               + (f" · {' · '.join(_extra)}" if _extra else ""))


# ============================================================
# CABEÇALHO
# ============================================================
st.title("🏥 Painel Hospitalar SP — SampaSUS")
st.caption(f"Dados SIH/DATASUS, {mes_curto(ini_comp)} a {mes_curto(fim_comp)} · "
           f"Dados atualizados em 01/{mes_curto(fim_comp)}")


# ============================================================
# SEÇÃO 1 — VISÃO EXECUTIVA (SEM filtros)
# ============================================================
st.header("Visão Executiva")
st.caption("Panorama do período completo — não afetado pelos filtros da barra lateral.")

total_geral = consultar("SELECT total_internacoes FROM VW_KPIS_GERAIS")['TOTAL_INTERNACOES'][0]
fim_ano, fim_mes = fim_comp // 100, fim_comp % 100
u12 = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN ({fim_comp}-100)+1 AND {fim_comp}""")['Q'][0]
u12a = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE (nr_ano_competencia*100+nr_mes_competencia) BETWEEN ({fim_comp}-200)+1 AND ({fim_comp}-100)""")['Q'][0]
ytd = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia={fim_ano} AND nr_mes_competencia<={fim_mes}""")['Q'][0]
ytda = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia={fim_ano-1} AND nr_mes_competencia<={fim_mes}""")['Q'][0]
mes = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia={fim_ano} AND nr_mes_competencia={fim_mes}""")['Q'][0]
ma_ano, ma_mes = (fim_ano, fim_mes-1) if fim_mes > 1 else (fim_ano-1, 12)
mesa = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA
    WHERE nr_ano_competencia={ma_ano} AND nr_mes_competencia={ma_mes}""")['Q'][0]
d12 = ((u12-u12a)/u12a*100) if u12a else 0
dytd = ((ytd-ytda)/ytda*100) if ytda else 0
dmes = ((mes-mesa)/mesa*100) if mesa else 0

def card_total(tit, val, rod):
    return (f"<div style='background:{CARD_BG}; border:1px solid {BORDA}; border-radius:10px; padding:15px; "
            f"min-height:120px;'><div style='color:{TEXTO_SUAVE}; font-size:0.9rem;'>{tit}</div>"
            f"<div style='font-size:2.3rem; font-weight:700; color:{NAVY}; line-height:1.2; margin-top:0.2rem;'>{val}</div>"
            f"<div style='color:{TEXTO_SUAVE}; font-size:0.85rem; margin-top:0.4rem;'>{rod}</div></div>")

k1, k2, k3, k4 = st.columns(4)
k1.markdown(card_total("Total de Internações", fmt_num(total_geral),
                       f"{mes_curto(ini_comp)} a {mes_curto(fim_comp)}"), unsafe_allow_html=True)
k2.metric("Últimos 12 Meses", fmt_num(u12), delta=f"{fmt_num(d12,1)}% vs. 12m anteriores", delta_color="inverse")
k3.metric(f"YTD ({mes_curto(fim_ano*100+1)} a {mes_curto(fim_comp)})", fmt_num(ytd),
          delta=f"{fmt_num(dytd,1)}% vs. YTD {fim_ano-1}", delta_color="inverse")
k4.metric(f"Último Mês ({mes_curto(fim_comp)})", fmt_num(mes),
          delta=f"{fmt_num(dmes,1)}% vs. mês anterior", delta_color="inverse")

st.subheader("📈 Evolução Mensal de Internações")
top5 = consultar("""SELECT nm_regiao_saude FROM VW_VOLUME_REGIAO
    ORDER BY qtd_internacoes DESC FETCH FIRST 5 ROWS ONLY""")['NM_REGIAO_SAUDE'].tolist()
tc = consultar("""SELECT nm_regiao_saude, nr_ano_competencia, nr_mes_competencia, qtd_internacoes
    FROM VW_VOLUME_REGIAO_TEMPORAL""")
tc['competencia'] = pd.to_datetime(tc['NR_ANO_COMPETENCIA'].astype(str) + '-' +
                                   tc['NR_MES_COMPETENCIA'].astype(str).str.zfill(2) + '-01')
total_mes = tc.groupby('competencia')['QTD_INTERNACOES'].sum().reset_index()
piv = (tc[tc['NM_REGIAO_SAUDE'].isin(top5)]
       .pivot_table(index='competencia', columns='NM_REGIAO_SAUDE', values='QTD_INTERNACOES', aggfunc='sum')
       .sort_index())
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    row_heights=[0.22, 0.78], subplot_titles=("", "Top 5 Regiões"))
fig.add_trace(go.Scatter(x=total_mes['competencia'], y=total_mes['QTD_INTERNACOES'],
    mode="lines+markers+text", line=dict(color=NAVY, width=3), marker=dict(size=4, color=NAVY),
    text=[fmt_compacto(v) for v in total_mes['QTD_INTERNACOES']], textposition="top center",
    textfont=dict(size=10, color=TEXTO_SUAVE), hovertemplate="Total: %{y:,.0f}<extra></extra>",
    showlegend=False), row=1, col=1)
fig.add_trace(go.Scatter(x=[total_mes['competencia'].iloc[-1] + pd.Timedelta(days=8)],
    y=[total_mes['QTD_INTERNACOES'].iloc[-1]], mode="text",
    text=[f"Total — {fmt_compacto(total_mes['QTD_INTERNACOES'].iloc[-1])}"], textposition="middle right",
    textfont=dict(color=NAVY, size=12), cliponaxis=False, hoverinfo="skip", showlegend=False), row=1, col=1)
for i, nome in enumerate(top5):
    if nome in piv.columns:
        cor = PALETA[i % len(PALETA)]
        fig.add_trace(go.Scatter(x=piv.index, y=piv[nome], name=nome, mode="lines",
            line=dict(width=2, color=cor), hovertemplate=f"<b>{nome}</b>: %{{y:,.0f}}<extra></extra>"), row=2, col=1)
        fig.add_trace(go.Scatter(x=[piv.index[-1] + pd.Timedelta(days=8)], y=[piv[nome].iloc[-1]],
            mode="text", text=[truncar(nome,22)], textposition="middle right",
            textfont=dict(color=cor, size=10), cliponaxis=False, hoverinfo="skip", showlegend=False), row=2, col=1)
fig.update_yaxes(visible=False, row=1, col=1)
_tk = [10000,20000,30000,40000,50000,60000,70000]
fig.update_yaxes(type="log", title_text="Internações", tickmode="array", tickvals=_tk,
                 ticktext=[fmt_compacto(v) for v in _tk], row=2, col=1)
fig.update_xaxes(range=[piv.index.min(), piv.index.max() + pd.Timedelta(days=20)], row=2, col=1)
aplicar_tema(fig, altura=540)
fig.update_layout(hovermode="x unified", margin=dict(l=10, r=200, t=30, b=10))
st.plotly_chart(fig, use_container_width=True, key="evolucao")


# ============================================================
# SEÇÃO 2 — PERFIL DA DEMANDA (com filtros)
# ============================================================
divisor()
st.header("Perfil da Demanda")
st.caption(f"Recorte atual: {recorte_txt}")

kpi = consultar(f"""SELECT COUNT(*) AS q FROM VW_INTERNACAO_COMPLETA {where}""")['Q'][0]
if kpi == 0:
    st.warning("Nenhuma internação para os filtros selecionados. Ajuste os filtros na barra lateral.")
    st.stop()

def titulo_centro(txt):
    st.markdown(f"<h3 style='text-align:center; margin:0 0 0.3rem;'>{txt}</h3>", unsafe_allow_html=True)

ca, cb, cc = st.columns(3)
with ca:
    with st.container(border=True):
        titulo_centro("🏙️ Top 10 Regiões")
        d = consultar(f"""SELECT nm_regiao_saude, COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA {where}
            GROUP BY nm_regiao_saude ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY""").sort_values('QTD')
        d['label'] = d['QTD'].apply(fmt_compacto)
        st.plotly_chart(barra_h(d, 'QTD', 'NM_REGIAO_SAUDE', 'label', eixo_x=False),
                        use_container_width=True, key="top_reg")
with cb:
    with st.container(border=True):
        titulo_centro("🩺 Top 10 Causas")
        d = consultar(f"""SELECT ds_diagnostico, COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA {where}
            GROUP BY ds_diagnostico ORDER BY qtd DESC FETCH FIRST 10 ROWS ONLY""").sort_values('QTD')
        d['DS_DIAGNOSTICO'] = d['DS_DIAGNOSTICO'].apply(simplificar_causa)
        d['label'] = d['QTD'].apply(fmt_compacto)
        st.plotly_chart(barra_h(d, 'QTD', 'DS_DIAGNOSTICO', 'label', eixo_x=False),
                        use_container_width=True, key="top_causa")
with cc:
    with st.container(border=True):
        titulo_centro("👥 Faixa etária × Óbito")
        d = consultar(f"""SELECT
                CASE WHEN nr_idade < 1  THEN '0 (< 1 ano)'
                     WHEN nr_idade < 15 THEN '1-14'
                     WHEN nr_idade < 30 THEN '15-29'
                     WHEN nr_idade < 45 THEN '30-44'
                     WHEN nr_idade < 60 THEN '45-59'
                     WHEN nr_idade < 75 THEN '60-74'
                     ELSE '75+' END AS faixa,
                COUNT(*) AS qtd,
                ROUND(SUM(fl_obito)/COUNT(*)*100,1) AS obito
            FROM VW_INTERNACAO_COMPLETA {where}
            GROUP BY CASE WHEN nr_idade < 1  THEN '0 (< 1 ano)'
                     WHEN nr_idade < 15 THEN '1-14'
                     WHEN nr_idade < 30 THEN '15-29'
                     WHEN nr_idade < 45 THEN '30-44'
                     WHEN nr_idade < 60 THEN '45-59'
                     WHEN nr_idade < 75 THEN '60-74'
                     ELSE '75+' END""")
        _ordem_faixa = ['0 (< 1 ano)','1-14','15-29','30-44','45-59','60-74','75+']
        d['faixa'] = pd.Categorical(d['FAIXA'], categories=_ordem_faixa, ordered=True)
        d = d.sort_values('faixa')
        d['label'] = d.apply(lambda r: f"{fmt_compacto(r['QTD'])} · {fmt_num(r['OBITO'],1)}% óbito", axis=1)
        _xmax = float(d['QTD'].max())
        fig = px.bar(d, x='QTD', y='FAIXA', orientation='h', text='label', custom_data=['OBITO'])
        fig.update_traces(marker_color=PALETA[0], textposition="outside", cliponaxis=False,
            textfont=dict(size=11, color=TEXTO),
            hovertemplate="Faixa %{y}<br>%{x:,.0f} internações<br>%{customdata[0]:,.1f}% óbito<extra></extra>")
        fig.update_layout(yaxis_title=None, xaxis_title=None,
                          yaxis=dict(categoryorder="array", categoryarray=_ordem_faixa, automargin=True))
        fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, _xmax * 1.42])
        aplicar_tema(fig, altura=CHART_HEIGHT)
        fig.update_layout(margin=dict(l=10, r=20, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True, key="perfil_etario")

# --- Internações por 1.000 habitantes ---
st.subheader("👥 Internações por 1.000 habitantes (por região)")
st.caption("Cruza o volume do recorte com a população municipal. Índices altos indicam demanda "
           "relativa alta — polos de referência atraem pacientes de fora.")
try:
    pc = consultar(f"""
        WITH rec AS (SELECT nm_regiao_saude, COUNT(*) AS qtd FROM VW_INTERNACAO_COMPLETA {where}
                     GROUP BY nm_regiao_saude)
        SELECT r.nm_regiao_saude, r.qtd, p.populacao,
               ROUND(r.qtd/NULLIF(p.populacao,0)*1000,1) AS por_mil
        FROM rec r JOIN VW_POPULACAO_REGIAO p ON p.nm_regiao_saude = r.nm_regiao_saude
        ORDER BY por_mil DESC FETCH FIRST 15 ROWS ONLY""")
    if len(pc):
        pc = pc.sort_values('POR_MIL')
        pc['_y'] = pc['NM_REGIAO_SAUDE'].apply(lambda s: truncar(s, 40))
        fig = px.bar(pc, x='POR_MIL', y='_y', orientation='h',
                     text=pc['POR_MIL'].apply(lambda v: fmt_num(v, 1)),
                     custom_data=['NM_REGIAO_SAUDE', 'QTD', 'POPULACAO'])
        fig.update_traces(marker_color=PALETA[4], textposition="outside", cliponaxis=False,
            textfont=dict(color=TEXTO),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,.0f} internações"
                          "<br>População: %{customdata[2]:,.0f}<br><b>%{x:,.1f}</b> por 1.000 hab.<extra></extra>")
        fig.update_layout(yaxis_title=None, xaxis_title="Internações por 1.000 habitantes",
                          yaxis=dict(automargin=True), margin=dict(l=10, r=60, t=30, b=10))
        aplicar_tema(fig, altura=max(360, len(pc) * 30))
        st.plotly_chart(fig, use_container_width=True, key="percapita")
    else:
        st.info("Sem correspondência de população para as regiões deste recorte.")
except Exception as e:
    st.info(f"Indicador per capita indisponível: {e}")


# ============================================================
# SEÇÃO 3 — PRESSÃO ASSISTENCIAL (com filtros)
# ============================================================
divisor()
st.header("Pressão Assistencial — Ocupação de Leitos SUS")
st.caption(f"Recorte atual: {recorte_txt}")

reg_m = consultar(f"""SELECT nm_regiao_saude, COUNT(*) AS internacoes, SUM(qt_dias_permanencia) AS pac_dia
    FROM VW_INTERNACAO_COMPLETA {where} GROUP BY nm_regiao_saude""")
reg_l = consultar(f"""SELECT nm_regiao_saude, SUM(leitos) AS leitos FROM (
        SELECT nm_regiao_saude, cd_hospital, MAX(qt_leitos_sus) AS leitos
        FROM VW_INTERNACAO_COMPLETA {where} GROUP BY nm_regiao_saude, cd_hospital
    ) GROUP BY nm_regiao_saude""")
cap = reg_m.merge(reg_l, on='NM_REGIAO_SAUDE', how='left')
cap['TAXA_OCUPACAO'] = (cap['PAC_DIA'] / (cap['LEITOS'] * dias_periodo) * 100).round(1)
cap['INTERNACOES_POR_LEITO'] = (cap['INTERNACOES'] / cap['LEITOS']).round(1)
cap['status'] = cap['TAXA_OCUPACAO'].apply(status_ocup)
cap = cap[cap['LEITOS'].notna() & (cap['LEITOS'] > 0)]

n_c = int((cap['status'] == "Crítico").sum()); n_a = int((cap['status'] == "Atenção").sum())
n_e = int((cap['status'] == "Estável").sum()); n_t = len(cap)
def card_status(cor, emoji, tit, val, tot, crit):
    pct = val / tot * 100 if tot else 0
    return (f"<div style='background:{CARD_BG}; border:1px solid {BORDA}; border-left:5px solid {cor}; "
            f"border-radius:10px; padding:14px 18px;'>"
            f"<div style='color:{TEXTO_SUAVE}; font-size:0.85rem;'>{emoji} {tit}</div>"
            f"<div style='font-size:2rem; font-weight:700; color:{NAVY}; line-height:1.1;'>{fmt_num(val)}</div>"
            f"<div style='color:{cor}; font-size:0.85rem;'>{fmt_num(pct,1)}% · {crit}</div></div>")
s1, s2, s3 = st.columns(3)
s1.markdown(card_status(COR_STATUS["Crítico"], "🔴", "Crítico", n_c, n_t, "ocupação ≥ 70%"), unsafe_allow_html=True)
s2.markdown(card_status(COR_STATUS["Atenção"], "🟡", "Atenção", n_a, n_t, "55–70%"), unsafe_allow_html=True)
s3.markdown(card_status(COR_STATUS["Estável"], "🟢", "Estável", n_e, n_t, "< 55%"), unsafe_allow_html=True)
st.markdown(f"<div style='text-align:center; color:{TEXTO_SUAVE}; font-size:0.9rem; margin:0.8rem 0 0.4rem;'>"
            "Regiões ordenadas pela <b>taxa de ocupação de leitos SUS</b>. À esquerda o volume e os leitos; "
            "à direita a ocupação, com internações por leito como referência.</div>", unsafe_allow_html=True)

if n_t:
    borb = cap.sort_values('TAXA_OCUPACAO', ascending=True)
    cores = borb['status'].map(COR_STATUS).tolist()
    alt = max(650, n_t * 22)
    fb = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.0,
        column_widths=[0.42, 0.16, 0.42],
        subplot_titles=("Internações (volume)", "", "Taxa de ocupação de leitos SUS (%)"))
    fb.add_trace(go.Bar(y=borb['NM_REGIAO_SAUDE'], x=borb['INTERNACOES'], orientation='h',
        marker_color=cores, text=[fmt_compacto(v) for v in borb['INTERNACOES']],
        textposition="outside", cliponaxis=False, customdata=borb['NM_REGIAO_SAUDE'],
        hovertemplate="<b>%{customdata}</b><br>Internações: %{x:,.0f}<extra></extra>"), row=1, col=1)
    _im = float(borb['INTERNACOES'].max()); _out = _im * 6.0
    fb.update_xaxes(type="log", range=[math.log10(_out), math.log10(1500)], showticklabels=False, row=1, col=1)
    fb.add_trace(go.Scatter(y=borb['NM_REGIAO_SAUDE'], x=[_out*0.95]*n_t, mode="text",
        text=[f"{fmt_num(v)} leitos" for v in borb['LEITOS']],
        textposition="middle right", textfont=dict(size=9, color=TEXTO_SUAVE), hoverinfo="skip"), row=1, col=1)
    fb.add_trace(go.Scatter(y=borb['NM_REGIAO_SAUDE'], x=[0]*n_t, mode="text",
        text=[truncar(n,24) for n in borb['NM_REGIAO_SAUDE']],
        textposition="middle center", textfont=dict(size=11, color=TEXTO), hoverinfo="skip"), row=1, col=2)
    fb.add_trace(go.Bar(y=borb['NM_REGIAO_SAUDE'], x=borb['TAXA_OCUPACAO'], orientation='h',
        marker_color=cores, text=[f"{fmt_num(v,1)}%" for v in borb['TAXA_OCUPACAO']],
        textposition="outside", cliponaxis=False, customdata=borb['NM_REGIAO_SAUDE'],
        hovertemplate="<b>%{customdata}</b><br>Ocupação: %{x:,.1f}%<extra></extra>"), row=1, col=3)
    _om = float(borb['TAXA_OCUPACAO'].max()); _oo = _om * 1.45
    fb.add_trace(go.Scatter(y=borb['NM_REGIAO_SAUDE'], x=[_oo*0.99]*n_t, mode="text",
        text=[f"{fmt_inteiro(v)} int./leito" for v in borb['INTERNACOES_POR_LEITO']],
        textposition="middle left", textfont=dict(size=9, color=TEXTO_SUAVE), hoverinfo="skip"), row=1, col=3)
    for cc_ in (1, 2, 3):
        fb.update_yaxes(showticklabels=False, showgrid=False, row=1, col=cc_)
    fb.update_xaxes(visible=False, row=1, col=2)
    fb.update_xaxes(showticklabels=False, range=[0, _oo], row=1, col=3)
    aplicar_tema(fb, altura=alt); fb.update_layout(bargap=0.25)
    for ann in fb.layout.annotations:
        if ann.text in ("Internações (volume)", "Taxa de ocupação de leitos SUS (%)"):
            ann.yshift = 10
    st.plotly_chart(fb, use_container_width=True, key="borboleta")


# ============================================================
# SEÇÃO 4 — HOSPITAIS (com filtros)
# ============================================================
divisor()
st.header("Hospitais — Permanência, Capacidade e Ocupação")
st.caption(f"Recorte atual: {recorte_txt}")

perm_estadual = consultar("SELECT permanencia_media FROM VW_KPIS_GERAIS")['PERMANENCIA_MEDIA'][0]
hosp = consultar(f"""SELECT LPAD(cd_hospital,10,'0') AS cd_hospital, COUNT(*) AS qtd,
        ROUND(AVG(qt_dias_permanencia),1) AS permanencia, SUM(qt_dias_permanencia) AS pac_dia,
        MAX(qt_leitos_sus) AS leitos_sus
    FROM VW_INTERNACAO_COMPLETA {where}
    GROUP BY LPAD(cd_hospital,10,'0') HAVING COUNT(*) >= 100""")
mn = dim[['CD_HOSPITAL', 'NM_HOSPITAL', 'NM_REGIAO_SAUDE']].copy()
mn['CD_HOSPITAL'] = mn['CD_HOSPITAL'].astype(str).str.zfill(10)
hosp = hosp.merge(mn, on='CD_HOSPITAL', how='left')
hosp['NM_HOSPITAL'] = hosp['NM_HOSPITAL'].fillna('Hospital ' + hosp['CD_HOSPITAL'])
# Ocupação só faz sentido com leitos SUS > 0; senão vira inf (bug da barra vazia).
hosp['TAXA_OCUPACAO'] = pd.NA
_ok = hosp['LEITOS_SUS'].notna() & (hosp['LEITOS_SUS'] > 0)
hosp.loc[_ok, 'TAXA_OCUPACAO'] = (
    hosp.loc[_ok, 'PAC_DIA'] / (hosp.loc[_ok, 'LEITOS_SUS'] * dias_periodo) * 100).round(1)
hosp['TAXA_OCUPACAO'] = pd.to_numeric(hosp['TAXA_OCUPACAO'], errors='coerce')

def ranking_hosp(df, col, titx, fmt, cores=None, ref=None, ref_txt=None):
    d = df.copy()
    d['_y'] = d['NM_HOSPITAL'].apply(lambda s: truncar(s, 48))
    ordem = d['_y'].tolist(); d['_t'] = d[col].apply(fmt)
    fig = px.bar(d, x=col, y='_y', orientation='h', text='_t',
                 custom_data=['NM_HOSPITAL', 'NM_REGIAO_SAUDE'])
    if cores is not None: fig.update_traces(marker_color=cores)
    fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TEXTO),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>" + titx + ": %{x:,.1f}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title=titx,
                      yaxis=dict(automargin=True, categoryorder="array", categoryarray=ordem))
    aplicar_tema(fig, altura=460); fig.update_layout(margin=dict(l=10, r=90, t=30, b=10))
    if ref is not None:
        fig.add_vline(x=ref, line_dash='dash', line_color=COR_STATUS["Atenção"], annotation_text=ref_txt,
                      annotation_position="top right", annotation_font_size=10,
                      annotation_font_color=COR_STATUS["Atenção"])
    return fig

st.subheader("🛏️ Maiores permanências médias")
st.caption(f"Linha = média estadual ({fmt_num(perm_estadual,1)} dias). Hospitais especializados têm longa permanência por natureza.")
tp = hosp.sort_values('PERMANENCIA', ascending=False).head(12).sort_values('PERMANENCIA')
st.plotly_chart(ranking_hosp(tp, 'PERMANENCIA', 'Permanência (dias)',
    lambda v: f"{fmt_num(v,1)} dias", ref=perm_estadual, ref_txt=f"Média: {fmt_num(perm_estadual,1)}d"),
    use_container_width=True, key="h_perm")

st.subheader("🏥 Maiores capacidades (leitos SUS)")
tl = hosp[hosp['LEITOS_SUS'].notna()].sort_values('LEITOS_SUS', ascending=False).head(12).sort_values('LEITOS_SUS')
f = ranking_hosp(tl, 'LEITOS_SUS', 'Leitos SUS', lambda v: fmt_inteiro(v)); f.update_traces(marker_color=PALETA[0])
st.plotly_chart(f, use_container_width=True, key="h_leitos")

st.subheader("📊 Maiores taxas de ocupação de leitos SUS")
st.caption("🔴 ≥ 70% · 🟡 55–70% · 🟢 < 55%. Acima de 100% = demanda maior que a capacidade.")
to = hosp[hosp['TAXA_OCUPACAO'].notna()].sort_values('TAXA_OCUPACAO', ascending=False).head(12).sort_values('TAXA_OCUPACAO')
cores_o = to['TAXA_OCUPACAO'].apply(status_ocup).map(COR_STATUS).tolist()
st.plotly_chart(ranking_hosp(to, 'TAXA_OCUPACAO', 'Ocupação (%)',
    lambda v: f"{fmt_num(v,1)}%", cores=cores_o), use_container_width=True, key="h_ocup")


# ============================================================
# SEÇÃO 5 — MAPA (cereja do bolo; com filtros)
# ============================================================
divisor()
st.header("🗺️ Mapa — Hospitais")
st.caption(f"Recorte atual: {recorte_txt} · cor = ocupação · tamanho ∝ leitos SUS")

mp = hosp.merge(dim[['CD_HOSPITAL', 'NM_MUNICIPIO', 'ESFERA_ADMIN', 'LATITUDE', 'LONGITUDE']].assign(
    CD_HOSPITAL=lambda x: x['CD_HOSPITAL'].astype(str).str.zfill(10)), on='CD_HOSPITAL', how='left')
mp = mp[mp['LATITUDE'].notna() & mp['LONGITUDE'].notna()]
mp = mp[(mp['LATITUDE'].between(-25.5, -19.5)) & (mp['LONGITUDE'].between(-53.5, -44.0))].copy()
mp['status'] = mp['TAXA_OCUPACAO'].apply(status_ocup)
mp['_size'] = mp['LEITOS_SUS'].fillna(0).clip(lower=0) + 20

# KPIs do mapa
m_total = len(mp)
m_crit = int((mp['status'] == "Crítico").sum())
m_aten = int((mp['status'] == "Atenção").sum())
m_esta = int((mp['status'] == "Estável").sum())
m_semd = int((mp['status'] == "Sem dado").sum())
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.markdown(mini_card(PALETA[0], "🏥", "Hospitais no mapa", m_total), unsafe_allow_html=True)
mc2.markdown(mini_card(COR_STATUS["Crítico"], "🔴", "Crítico (≥70%)", m_crit), unsafe_allow_html=True)
mc3.markdown(mini_card(COR_STATUS["Atenção"], "🟡", "Atenção (55–70%)", m_aten), unsafe_allow_html=True)
mc4.markdown(mini_card(COR_STATUS["Estável"], "🟢", "Estável (<55%)", m_esta), unsafe_allow_html=True)
mc5.markdown(mini_card("#7F8C9B", "⚪", "Sem dado", m_semd), unsafe_allow_html=True)
st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

mp['_hover'] = mp.apply(lambda r:
    f"<b>{r['NM_HOSPITAL']}</b><br>{r['NM_MUNICIPIO']} · {r['NM_REGIAO_SAUDE']}<br>"
    f"Internações: {fmt_num(r['QTD'])}<br>Leitos SUS: {fmt_num(r['LEITOS_SUS'] or 0)}<br>"
    f"Ocupação: {fmt_num(r['TAXA_OCUPACAO'] or 0,1)}%", axis=1)

if len(mp):
    _USA_MAP = hasattr(go, "Scattermap")
    _T = go.Scattermap if _USA_MAP else go.Scattermapbox
    fig = go.Figure()
    for stn, cor in COR_STATUS.items():
        sub = mp[mp['status'] == stn]
        if len(sub):
            fig.add_trace(_T(lat=sub['LATITUDE'], lon=sub['LONGITUDE'], mode='markers', name=stn,
                marker=dict(size=sub['_size'], sizemode='area',
                            sizeref=(sub['_size'].max()/900) if sub['_size'].max() else 1,
                            color=cor, opacity=0.8), text=sub['_hover'], hoverinfo='text'))
    sub = mp[mp['status'] == "Sem dado"]
    if len(sub):
        fig.add_trace(_T(lat=sub['LATITUDE'], lon=sub['LONGITUDE'], mode='markers', name="Sem dado",
            marker=dict(size=8, color="#7F8C9B", opacity=0.6), text=sub['_hover'], hoverinfo='text'))
    ly = dict(height=620, margin=dict(l=0, r=0, t=0, b=0),
              legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01,
                          bgcolor="rgba(255,255,255,0.85)", bordercolor=BORDA, borderwidth=1,
                          font=dict(color=TEXTO)),
              paper_bgcolor="rgba(0,0,0,0)")
    ly["map" if _USA_MAP else "mapbox"] = dict(style=MAPA_STYLE, zoom=5.6,
                                               center=dict(lat=-22.5, lon=-48.6))
    fig.update_layout(**ly)
    st.plotly_chart(fig, use_container_width=True, key="mapa")
    st.caption("🔴 ≥70% · 🟡 55–70% · 🟢 <55% · tamanho ∝ leitos SUS. Hospitais sem coordenada no CNES não aparecem.")
else:
    st.info("Sem hospitais georreferenciados neste recorte.")

# ---- Disclaimer ----
st.markdown("<hr class='sec-divider'>", unsafe_allow_html=True)
st.caption("ℹ️ **Nota metodológica** — Ocupação = (pacientes-dia ÷ leitos-dia) × 100, considerando "
           "apenas leitos SUS e internações SIH/DATASUS (rede pública). O período ajusta-se ao filtro. "
           "Valores acima de 100% indicam demanda superior à capacidade instalada.")
