# Dicionário de Dados — Layout RD (SIH/DATASUS)

**Projeto DATAHOLICS — FIAP Challenge | Parceria Oracle**

Este documento descreve as 114 colunas disponíveis no arquivo RD (AIH Reduzida) do SIH/SUS, organizadas por grupo temático. A coluna **"No banco?"** indica se o campo foi incorporado à tabela `T_SIH_INTERNACAO` no Oracle.

---

## 1. Identificação da internação

| Coluna | Descrição | No banco? |
|---|---|---|
| `UF_ZI` | Código da unidade da federação de zona de influência do hospital | Não |
| `ANO_CMPT` | Ano de competência da AIH (ano de processamento) | **Sim** (`nr_ano_competencia`) |
| `MES_CMPT` | Mês de competência da AIH | **Sim** (`nr_mes_competencia`) |
| `ESPEC` | Especialidade do leito: 1-Cirúrgica, 2-Obstetrícia, 3-Clínica Médica, 4-Crônicos/FPT, 5-Psiquiatria, 6-Tisiologia, 7-Pediatria, 8-Reabilitação, 9 a 14-variações de Hospital Dia (pós-2008) | **Sim** (`cd_especialidade_leito`) |
| `CGC_HOSP` | CNPJ do hospital (permite identificar o estabelecimento via CNES) | Não |
| `N_AIH` | Número da Autorização de Internação Hospitalar — identificador da internação | **Sim** (`nr_aih`, chave primária) |
| `IDENT` | Tipo de AIH: 1-Normal, 5-Longa permanência/FPT (Fora de Possibilidade Terapêutica) | **Sim** (`cd_tipo_aih`) |
| `CNES` | Código do estabelecimento no Cadastro Nacional de Estabelecimentos de Saúde | **Sim** (`cd_hospital`) |
| `MUNIC_MOV` | Código do município onde está o hospital (município de movimentação) | **Sim** (`cd_municipio_hospital`) |

## 2. Perfil do paciente

| Coluna | Descrição | No banco? |
|---|---|---|
| `SEXO` | Sexo do paciente: 0-Ignorado, 1-Masculino, 3-Feminino | **Sim** (`sg_sexo`) |
| `IDADE` | Idade do paciente, na unidade indicada por `COD_IDADE` | **Sim** (`nr_idade`) |
| `COD_IDADE` | Unidade de medida da idade: 0-Ignorada, 2-Dias, 3-Meses, 4-Anos | Não |
| `NASC` | Data de nascimento do paciente (AAAAMMDD) | Não |
| `MUNIC_RES` | Código do município de residência do paciente | **Sim** (`cd_municipio_residencia`) |
| `CEP` | CEP de residência do paciente | Não |
| `RACA_COR` | Raça/cor conforme classificação IBGE: 01-Branca, 02-Preta, 03-Parda, 04-Amarela, 05-Indígena, 99-Sem informação | Não |
| `ETNIA` | Código de etnia indígena (só relevante quando `RACA_COR` = 05) | Não |
| `INSTRU` | Grau de instrução (preenchido apenas em procedimentos de laqueadura/vasectomia) | Não |
| `NACIONAL` | Nacionalidade do paciente (tabela de códigos: 10-brasileiro, 20-naturalizado, demais códigos por país) | Não |
| `CBOR` | Código da ocupação do paciente (CBO) | Não |
| `NUM_FILHOS` | Número de filhos (preenchido em laqueadura/vasectomia) | Não |
| `VINCPREV` | Vínculo previdenciário do paciente | Não |

## 3. Diagnóstico

| Coluna | Descrição | No banco? |
|---|---|---|
| `DIAG_PRINC` | CID-10 do diagnóstico principal — motivo da internação | **Sim** (`cd_diagnostico_principal`) |
| `DIAG_SECUN` | Indicador de existência de diagnóstico secundário | Não |
| `DIAGSEC1` a `DIAGSEC9` | CID-10 dos diagnósticos secundários (até 9), disponíveis a partir de 2015 | Não |
| `CID_ASSO` | CID-10 de causa associada | **Removido** — validado na base completa (6.107.861 registros) como 100% valor único (`0000`), sem informação distintiva |
| `CID_MORTE` | CID-10 da causa de óbito (preenchido apenas quando há óbito) | Não |
| `CID_NOTIF` | CID de indicação para laqueadura (não usado em vasectomia) | Não |

## 4. Datas e desfecho

| Coluna | Descrição | No banco? |
|---|---|---|
| `DT_INTER` | Data de internação (AAAAMMDD) | **Sim** (`dt_internacao`) |
| `DT_SAIDA` | Data de saída/alta (AAAAMMDD) | **Sim** (`dt_saida`) |
| `DIAS_PERM` | Dias de permanência no hospital | **Sim** (`qt_dias_permanencia`) |
| `MORTE` | Indicador de óbito: 0-Não, 1-Sim | **Sim** (`fl_obito`) |
| `COBRANCA` | Motivo de alta/saída: código detalhado por categoria (cura, transferência, óbito com/sem autópsia, alta a pedido, etc. — tabela extensa) | Não |
| `CAR_INT` | Caráter da internação: 01-Eletiva, 02-Urgência/Emergência, 03 a 09-acidentes de trabalho/trajeto/trânsito/outros | **Candidata a inclusão** — relevante para a Frente 2 (tipo de atendimento em expansão), ainda não carregada |

## 5. UTI e cuidados intensivos

| Coluna | Descrição | No banco? |
|---|---|---|
| `UTI_MES_TO` | Total de dias de UTI no mês | **Sim** (`qt_dias_uti`) |
| `MARCA_UTI` | Tipo de UTI utilizada (00-09 padrão antigo; 74-83 pós-2008; 99-não utilizou) | Não |
| `UTI_MES_IN` | Dias de UTI tipo I no mês (quase sempre zerado no período analisado) | Não |
| `UTI_MES_AN` | Dias de UTI tipo I com acompanhante no mês | Não |
| `UTI_MES_AL` | Dias de UTI tipo I alta complexidade no mês | Não |
| `UTI_INT_TO` | Total de dias de unidade intermediária | Não |
| `UTI_INT_IN`, `UTI_INT_AN`, `UTI_INT_AL` | Variações de dias de unidade intermediária (quase sempre zerados) | Não |
| `MARCA_UCI` | Tipo de Unidade de Cuidados Intermediários utilizada | Não |
| `VAL_UTI` | Valor gasto com UTI | **Sim** (`vl_uti`) |
| `VAL_UCI` | Valor gasto com unidade de cuidados intermediários | Não |

## 6. Financeiro

| Coluna | Descrição | No banco? |
|---|---|---|
| `VAL_TOT` | Valor total pago pela internação | **Sim** (`vl_total_internacao`) |
| `VAL_SH` | Valor de serviços hospitalares (diárias, taxas, materiais) | Não |
| `VAL_SP` | Valor de serviços profissionais | Não |
| `VAL_SADT` | Valor de serviços auxiliares de diagnose e terapia (incorporado ao VAL_SH após 2007) | Não |
| `VAL_RN` | Valor referente a recém-nato | Não |
| `VAL_ACOMP` | Valor de diária de acompanhante | Não |
| `VAL_ORTP` | Valor de órtese/prótese | Não |
| `VAL_SANGUE` | Valor gasto com sangue/hemoderivados | Não |
| `VAL_SADTSR` | Valor de tomografia/ressonância magnética | Não |
| `VAL_TRANSP` | Valor referente a transplantes | Não |
| `VAL_OBSANG` | Valor de observação com uso de sangue | Não |
| `VAL_PED1AC` | Valor de pediatria (1ª criança acompanhante) | Não |
| `VAL_SH_FED`, `VAL_SP_FED` | Componentes de valor com participação federal | Não |
| `VAL_SH_GES`, `VAL_SP_GES` | Componentes de valor com participação do gestor local | Não |
| `US_TOT` | Valor total da AIH convertido em dólares | Não |
| `FINANC` | Tipo de financiamento (FAEC ou MAC) | Não |
| `FAEC_TP` | Subtipo de financiamento FAEC | Não |
| `COMPLEX` | Complexidade do procedimento: alta ou média | **Sim** (`cd_complexidade`) |
| `TOT_PT_SP` | Número de pontos de Serviços Profissionais para remuneração | Não |

## 7. Sobre o hospital / gestão

| Coluna | Descrição | No banco? |
|---|---|---|
| `NATUREZA` | Vínculo do hospital com o SUS: público (federal/estadual/municipal), contratado, filantrópico, universitário | Não (tratado via `T_SIH_ESTABELECIMENTO`/CNES) |
| `NAT_JUR` | Código de natureza jurídica do estabelecimento (tabela do IBGE/Receita Federal) | Não |
| `GESTAO` | Tipo de gestão do hospital: 0-Estadual, 1-Plena Municipal, 2-Plena Estadual | Não (varia por AIH, não é atributo fixo do hospital — ver nota metodológica na Tabela 2) |
| `REGCT` | Regra contratual do estabelecimento | Não |
| `GESTOR_COD`, `GESTOR_CPF`, `GESTOR_DT`, `GESTOR_TP` | Identificação do gestor responsável pela autorização (dados administrativos internos) | Não |
| `CNPJ_MANT` | CNPJ da entidade mantenedora do hospital | Não |
| `IND_VDRL` | Indicador de realização de exame VDRL | Não |
| `INFEHOSP` | Indicador de infecção hospitalar | Não |

## 8. Obstetrícia e procedimentos específicos

| Coluna | Descrição | No banco? |
|---|---|---|
| `GESTRISCO` | Indicador de gestação de risco | Não |
| `INSC_PN` | Número de inscrição no pré-natal | Não |
| `CONTRACEP1`, `CONTRACEP2` | Métodos contraceptivos utilizados (contexto de laqueadura) | Não |
| `NUM_PROC` | Número do processo (laqueadura/vasectomia) | Não |
| `CPF_AUT` | CPF de autorização (contexto de esterilização) | Não |
| `HOMONIMO` | Indicador de possível homônimo de paciente | Não |

## 9. Diagnósticos secundários (detalhamento)

| Coluna | Descrição | No banco? |
|---|---|---|
| `TPDISEC1` a `TPDISEC9` | Tipo de cada diagnóstico secundário: se é condição pré-existente ou adquirida durante a internação | Não |

## 10. Controle interno / processamento

| Coluna | Descrição | No banco? |
|---|---|---|
| `SEQUENCIA` | Número de sequência do registro no arquivo de processamento | Não |
| `SEQ_AIH5` | Sequência de AIH de longa permanência | Não |
| `REMESSA` | Identificação do arquivo/remessa de origem do registro | Não |
| `RUBRICA` | Código de rubrica orçamentária | Não |
| `FONTE_ORC` | Fonte orçamentária | Não |
| `CNAER` | Código de classificação de atividade econômica | Não |
| `AUD_JUST`, `SIS_JUST` | Justificativas de auditoria/glosa | Não |
| `DIAR_ACOM` | Diárias de acompanhante | Não |
| `QT_DIARIAS` | Quantidade total de diárias cobradas | Não |
| `PROC_SOLIC` | Código do procedimento solicitado (tabela SIGTAP, 10 dígitos) | Não |
| `PROC_REA` | Código do procedimento efetivamente realizado (tabela SIGTAP) | Não |

---

## Resumo

- **19 colunas** compõem hoje a tabela fato `T_SIH_INTERNACAO`
- **95 colunas** permanecem fora do escopo da tabela fato — por baixa relevância para as perguntas de negócio do projeto, por serem constantes/quase vazias no período analisado, por pertencerem a outro nível de granularidade (hospital, não internação), ou por exigirem tabelas de referência muito grandes (ex.: SIGTAP) para se tornarem úteis
