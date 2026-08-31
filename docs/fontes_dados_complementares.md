# Fontes de Dados Complementares

**Projeto DATAHOLICS — FIAP Challenge | Parceria Oracle**

Este documento lista todas as fontes externas ao SIH/DATASUS utilizadas para enriquecer o modelo de dados do projeto, com a URL de origem, o que cada uma fornece, e como foi utilizada.

---

## 1. Tabela de categorias CID-10 (descrição de diagnósticos)

- **O que fornece:** Descrição textual de cada código CID-10 de 3 dígitos (ex.: `J90` → "Derrame pleural não classificado em outra parte"), organizados por capítulo, categoria e subcategoria.
- **Fonte original:** DATASUS / CBCD (Centro Brasileiro de Classificação de Doenças, USP), publicação oficial da CID-10 em formato eletrônico.
- **URL utilizada (réplica em CSV, mesma fonte oficial):** https://raw.githubusercontent.com/cleytonferrari/CidDataSus/master/CIDImport/Repositorio/Resources/CID-10-CATEGORIAS.CSV
- **Como foi usada:** Cruzada com `DIAG_PRINC` na análise exploratória, para traduzir os códigos mais frequentes em descrições legíveis.
- **Observação:** O portal oficial do DATASUS (`www2.datasus.gov.br/cid10`) bloqueia acesso automatizado; a réplica em CSV usada reproduz o mesmo conteúdo oficial, publicamente disponível para download.

## 2. Especialidade do leito e demais códigos do layout SIH (ESPEC, SEXO, IDENT, MARCA_UTI, CAR_INT, NATUREZA, GESTAO, RACA_COR, COBRANCA)

- **O que fornece:** Dicionário de dados detalhado do layout de AIH do SIH/SUS, com a tabela de códigos e descrições de diversos campos categóricos.
- **Fonte original:** Centro de Estudos da Metrópole (CEM/CEBRAP, USP) — *Dicionário da Base de Dados Geocodificados AIH-SUS, Município de São Paulo, 2000-2016*, elaborado com base na documentação oficial do DATASUS.
- **URL utilizada:** https://centrodametropole.fflch.usp.br/en/file/16341/download
- **Como foi usada:** Fonte de referência para a tradução dos códigos categóricos identificados na análise exploratória (Seção 5 do notebook de exploração).
- **Observação:** Complementada por uma segunda fonte (DATASUS/SIAB) para confirmação cruzada da tabela de especialidade do leito.

## 3. Especialidade do leito — confirmação cruzada

- **Fonte:** DATASUS/SIAB, página de tabelas auxiliares do SIH/SUS.
- **URL:** http://siab.datasus.gov.br/DATASUS/index.php?area=0901&item=1&acao=13&noticia=7765
- **Como foi usada:** Confirmação cruzada dos 9 primeiros códigos de especialidade do leito antes de documentá-los no dicionário de dados.

## 4. Cadastro de estabelecimentos (CNES) — documento JSON

- **O que fornece:** Cadastro completo de estabelecimentos de saúde do Brasil (nome, tipo, natureza administrativa, turno de atendimento, geolocalização, situação de habilitação, entre outros).
- **Fonte original:** Ministério da Saúde — Portal de Dados Abertos (CNES).
- **URL utilizada:** https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_json.zip
- **Como foi usada:** Carregada integralmente (filtrada para SP) como documento JSON na tabela `T_SIH_ESTABELECIMENTO` — a peça "documento" da arquitetura de 3 formatos do projeto.

## 5. Cadastro de leitos SUS (capacidade instalada)

- **O que fornece:** Quantidade de leitos existentes, leitos SUS e leitos de UTI (total, adulto, pediátrico, neonatal) por estabelecimento, atualizado mensalmente.
- **Fonte original:** Ministério da Saúde — Portal de Dados Abertos (Leitos SUS).
- **URL utilizada:** https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip
- **Como foi usada:** Cruzada com os hospitais únicos da tabela fato para compor a `T_SIH_HOSPITAL` (dimensão hospital), usando a competência mais recente disponível como snapshot de capacidade.

## 6. Estimativas de população por município

- **O que fornece:** População estimada por município, por ano de referência.
- **Fonte original:** IBGE — Estimativas da População Residente.
- **URLs utilizadas:**
  - 2024: https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2024/POP2024_20241230.xls
  - 2025: https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2025/POP2025_20260828.xls
- **Como foi usada:** Base da Tabela 4 (população), planejada para carga via external table no Oracle. Exige ajuste de código de município (7 dígitos do IBGE → 6 dígitos, removendo o dígito verificador, para bater com `MUNIC_MOV`/`MUNIC_RES` do SIH).

## 7. Região de Saúde e Macrorregião de Saúde por município

- **O que fornece:** Classificação de cada município em região de saúde e macrorregião de saúde, usada para planejamento regional do SUS.
- **Fonte original:** Ministério da Saúde — painel de Regionalização no SUS (Base Nacional de Regiões de Saúde / DBGeral).
- **URL de origem:** https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_MACRORREGIOES/SEIDIGI_DEMAS_MACRORREGIOES.html
- **Como foi obtida:** O portal bloqueia acesso automatizado; o arquivo foi baixado manualmente pelo usuário através do navegador e fornecido para processamento.
- **Como foi usada:** Base da tabela complementar `T_SIH_REGIAO_SAUDE` (645 municípios de SP, 62 regiões de saúde, 19 macrorregiões), permitindo agregações regionais (Pergunta de Negócio 1) via `JOIN` com `cd_municipio_hospital`.
- **Observação:** Existe uma segunda classificação regional oficial, específica do estado de São Paulo — os 17 Departamentos Regionais de Saúde (DRS) da Secretaria de Estado da Saúde de SP (fonte: https://saude.sp.gov.br, decreto estadual nº 51.433/2006). Um arquivo agregado dessa classificação (com contagem de municípios e população por DRS, mas sem a lista individual de municípios) também foi obtido, mas não chegou a ser usado como chave de junção por não ter o nível de detalhe por município.

---

## Resumo das tabelas de apoio geradas

| Tabela | Fonte principal | Registros |
|---|---|---|
| `T_SIH_ESTABELECIMENTO` (JSON) | CNES — Dados Abertos MS | 153.366 (SP) |
| `T_SIH_HOSPITAL` (leitos) | Leitos SUS — Dados Abertos MS | 650 hospitais |
| `T_SIH_MUNICIPIO` (população) | IBGE — Estimativas de População | Planejada |
| `T_SIH_REGIAO_SAUDE` | Ministério da Saúde — Regionalização no SUS | 645 municípios |
