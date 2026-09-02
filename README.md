# 🏥 Painel Hospitalar — SampaSUS

**FIAP Challenge · Parceria Oracle** — Dashboard analítico da rede hospitalar SUS do estado de São Paulo, construído sobre dados do **SIH/DATASUS** em uma **arquitetura de 3 formatos** no Oracle Autonomous Database.

🔗 **App:** https://dataholics-oracle-challenge.streamlit.app/

---

## 📑 Sumário

- [Visão geral](#-visão-geral)
- [Arquitetura de dados](#-arquitetura-de-dados-3-formatos)
- [Stack técnica](#-stack-técnica)
- [Estrutura do dashboard](#-estrutura-do-dashboard)
- [Camada analítica (Views)](#-camada-analítica-views)
- [Metodologia](#-metodologia)
- [Decisões técnicas e bugs resolvidos](#-decisões-técnicas-e-bugs-resolvidos)
- [Como rodar](#-como-rodar)
- [Principais achados](#-principais-achados)

---

## 🎯 Visão geral

O painel responde perguntas de **gestão hospitalar** a partir de ~6 milhões de internações SUS (jun/2024 a jun/2026):

- **Onde** as internações crescem e se concentram?
- **De quê** e **de quem** é a demanda (causas, perfil etário, mortalidade)?
- **Onde a capacidade está sob pressão** (ocupação de leitos SUS)?
- **Quais hospitais** têm maior permanência, capacidade e ocupação?
- **Como a demanda se distribui geograficamente** (mapa) e **per capita**?

Todo o conteúdo da **Seção 2 em diante** é filtrável por período, região, município, esfera administrativa, caráter, complexidade, sexo e raça/cor.

---

## 🗄️ Arquitetura de dados (3 formatos)

O projeto integra **três formas de armazenamento** no Oracle, demonstrando versatilidade da plataforma:

| Formato | Tabela(s) | Conteúdo |
|---|---|---|
| **Relacional** | `T_SIH_INTERNACAO`, `T_SIH_HOSPITAL`, dimensões (CID-10, região, complexidade, caráter, sexo, raça/cor, município) | Fato de internações + dimensões clássicas |
| **Documento JSON** | `T_SIH_ESTABELECIMENTO` (`JSON_CADASTRO`) | Cadastro CNES completo: nome fantasia, razão social, esfera administrativa, **geolocalização (lat/long)**, bairro |
| **External Table (CSV)** | `T_SIH_MUNICIPIO` | Estimativas populacionais do IBGE (645 municípios × 2 anos), lidas direto do Object Storage |

---

## 🛠️ Stack técnica

- **Backend de dados:** Oracle Autonomous Database (19c+), acesso via `python-oracledb` (thin mode + wallet).
- **App:** Python + **Streamlit** (página única com sidebar de filtros globais).
- **Visualização:** **Plotly** (gráficos + mapa MapLibre/`carto-darkmatter`, sem necessidade de token).
- **Deploy:** Streamlit Community Cloud (secrets + wallet em base64).

---

## 🧭 Estrutura do dashboard

### Seção 1 — Visão Executiva *(panorama fixo, sem filtros)*
- **KPIs temporais:** Total de internações, Últimos 12 meses, YTD, Último mês (com variação vs. período anterior).
- **Evolução mensal:** Total geral + Top 5 regiões, em escala logarítmica para revelar sazonalidade.

### Seção 2 — Perfil da Demanda *(filtros aplicados)*
- **Top 10 Regiões** · **Top 10 Causas** · **Faixa etária × Óbito** (trio comparativo).
- **Internações por 1.000 habitantes** por região (cruzamento com população).

### Seção 3 — Pressão Assistencial
- **Gráfico borboleta:** região ao centro; à esquerda volume + leitos SUS; à direita **taxa de ocupação** (métrica-chave) com pressão como referência.
- **Cards de status:** 🔴 Crítico (≥70%) · 🟡 Atenção (55–70%) · 🟢 Estável (<55%).

### Seção 4 — Hospitais
- Rankings de **maior permanência** (com linha da média estadual), **maior capacidade** (leitos SUS) e **maior ocupação** (colorido por status).

### Seção 5 — Mapa 🗺️
- Hospitais georreferenciados (coordenadas do CNES). **Cor = ocupação**, **tamanho = leitos SUS**.
- 5 KPIs de resumo (total, crítico, atenção, estável, sem dado).

---

## 🧱 Camada analítica (Views)

Todas as análises são servidas por **views** (arquivo `views_sampasus.sql`), mantendo o app enxuto e a lógica de negócio no banco.

| View | Descrição |
|---|---|
| `VW_CAPACIDADE_REGIAO` | Volume, leitos SUS, pressão e **taxa de ocupação** por região |
| `VW_HOSPITAL_PERMANENCIA` | 1 linha/hospital: nome, esfera, **geo**, permanência, leitos, ocupação, óbito |
| `VW_MORTALIDADE_DIAGNOSTICO` | Top mortalidade por causa (≥500 casos) |
| `VW_LEITOS_TIPO` | UTI vs. Enfermaria/Outros (volume, permanência, dias UTI, óbito, custo) |
| `VW_INTERNACAO_ENRIQUECIDA` | Base fato + hospital + esfera (suporte a filtros) |
| `VW_POPULACAO_REGIAO` | População por região (join por código de município) |
| `VW_INTERNACAO_PER_CAPITA_REGIAO` | Internações por 1.000 habitantes |

---

## 📐 Metodologia

### Taxa de ocupação de leitos
$$\text{Ocupação (\%)} = \frac{\text{pacientes-dia}}{\text{leitos-dia}} \times 100 = \frac{\sum \text{dias de permanência}}{\text{leitos SUS} \times \text{dias do período}} \times 100$$

- Considera **apenas leitos SUS** e internações **SIH/DATASUS** (rede pública) — coerente com a natureza dos dados.
- O **período de referência ajusta-se ao filtro** (nº de meses × 30,4375 dias/mês).
- Valores **> 100%** indicam demanda superior à capacidade instalada.
- Difere de indicadores que incluem rede privada ou recortes de pico (ex.: UTI no inverno) — por isso a nota metodológica no rodapé.

### Limiares de status (benchmarks de gestão)
🔴 **Crítico** ≥ 70% · 🟡 **Atenção** 55–70% · 🟢 **Estável** < 55%.
*(Limiares absolutos, não percentis — evitam a divisão artificial em tercis.)*

### Internações per capita
Volume da região ÷ população residente × 1.000. Regiões-polo (Barretos/oncologia, SJ Rio Preto) apresentam índices altos por **atrair pacientes de fora** — um insight de rede de referência, não de super-demanda local.

---

## 🐛 Decisões técnicas e bugs resolvidos

Ao longo do desenvolvimento, a validação sistemática dos dados revelou (e corrigiu) vários problemas sutis:

1. **Conexão resiliente** — o Oracle derruba sessões ociosas no Streamlit Cloud. Implementado `ping()` + reconexão automática + retry, evitando `DPY-4011`.

2. **Leitos por região (`SUM(DISTINCT)`)** — a lógica original somava *valores distintos* de leitos, colapsando hospitais diferentes com a mesma contagem. Corrigido para somar por **hospital distinto**.

3. **Nome do hospital (join de código)** — `T_SIH_ESTABELECIMENTO` traz `cd_hospital` **sem zeros à esquerda**. Padronizado com `LPAD(cd,10,'0')` nos dois lados → **100% de match**.

4. **Aspas no JSON** — `CAST(json.campo AS VARCHAR2)` preservava aspas (`"MUNICIPAL"`). Trocado por **`JSON_VALUE`**, que retorna o escalar limpo.

5. **População per capita (join por nome)** — juntar por nome de município perdia registros (acentos/grafia), subestimando a população em ~60% e inflando o per capita 10×. Corrigido para **join por `CD_MUNICIPIO`** → cobertura 100% (46 mi hab.).

6. **Divisão por zero (ocupação)** — hospitais com `leitos_sus = 0` geravam `inf` (que passa por `.notna()`). Tratado calculando ocupação apenas quando `leitos > 0`.

7. **Compatibilidade Plotly 6.x** — `Scattermapbox` foi removido em favor de `Scattermap`. Detecção automática de versão para funcionar em ambas.

---

## ▶️ Como rodar

### Pré-requisitos
- Oracle Autonomous Database com as tabelas SIH carregadas.
- As 7 views criadas (execute `views_sampasus.sql` como **script**).

### Secrets (Streamlit)
```toml
db_user = "..."
db_password = "..."
db_dsn = "..."
wallet_password = "..."
wallet_b64 = "..."   # wallet .zip em base64
```

### Local
```bash
pip install streamlit oracledb pandas plotly
streamlit run app.py
```

---

## 💡 Principais achados

- **Sepse (septicemia não especificada):** ~75 mil internações com **~49% de mortalidade** — grande vilão em volume × letalidade.
- **UTI:** apenas ~10% das internações, mas **custa quase o mesmo** que todas as demais juntas e tem mortalidade **~5,7× maior**.
- **Rede privada "esconde" pressão no SUS:** regiões como SJ Rio Preto e Piracicaba sobem muito no ranking de pressão quando medidas por leitos **SUS**.
- **Perfil etário:** volume e mortalidade disparam nas faixas 60-74 e 75+.
- **Regiões-polo** (Barretos, SJ Rio Preto) lideram o per capita por atraírem pacientes de outras regiões.

---
