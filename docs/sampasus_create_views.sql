-- Consolida internações com dimensões clínicas, demográficas e hospitalares.
CREATE OR REPLACE VIEW ADMIN.VW_INTERNACAO_COMPLETA AS
SELECT
    i.nr_aih,
    i.cd_hospital,
    i.nr_ano_competencia,
    i.nr_mes_competencia,
    r.nm_regiao_saude,
    r.nm_municipio,
    c.ds_diagnostico,
    ci.ds_carater_internacao,
    cx.ds_complexidade,
    s.ds_sexo,
    rc.ds_raca_cor,
    i.nr_idade,
    i.dt_internacao,
    i.dt_saida,
    i.qt_dias_permanencia,
    i.fl_obito,
    i.qt_dias_uti,
    i.vl_uti,
    i.vl_total_internacao,
    h.qt_leitos_existentes,
    h.qt_leitos_sus,
    h.qt_leitos_uti_total
FROM T_SIH_INTERNACAO i
JOIN T_SIH_REGIAO_SAUDE r
    ON i.cd_municipio_hospital = r.cd_municipio
LEFT JOIN T_SIH_CID10 c
    ON i.cd_diagnostico_principal = c.cd_diagnostico
JOIN T_SIH_CARATER_INTERNACAO ci
    ON i.cd_carater_internacao = ci.cd_carater_internacao
JOIN T_SIH_COMPLEXIDADE cx
    ON i.cd_complexidade = cx.cd_complexidade
JOIN T_SIH_SEXO s
    ON i.sg_sexo = s.sg_sexo
JOIN T_SIH_RACA_COR rc
    ON i.cd_raca_cor = rc.cd_raca_cor
LEFT JOIN T_SIH_HOSPITAL h
    ON i.cd_hospital = h.cd_hospital
WHERE i.cd_tipo_aih = 1;

-- Consolida a população mais recente dos municípios por região de saúde.
CREATE OR REPLACE VIEW ADMIN.VW_POPULACAO_REGIAO AS
WITH pop_muni AS (
    SELECT cd_municipio, qt_populacao
    FROM (
        SELECT
            cd_municipio,
            qt_populacao,
            ROW_NUMBER() OVER (
                PARTITION BY cd_municipio
                ORDER BY nr_ano_referencia DESC
            ) AS rn
        FROM T_SIH_MUNICIPIO
    )
    WHERE rn = 1
)
SELECT
    rs.nm_regiao_saude,
    SUM(pm.qt_populacao) AS populacao,
    COUNT(DISTINCT rs.cd_municipio) AS municipios
FROM T_SIH_REGIAO_SAUDE rs
JOIN pop_muni pm
    ON pm.cd_municipio = rs.cd_municipio
GROUP BY rs.nm_regiao_saude;

-- Calcula os principais indicadores executivos das internações.
CREATE OR REPLACE VIEW ADMIN.VW_KPIS_GERAIS AS
SELECT
    COUNT(*) AS total_internacoes,
    ROUND(SUM(fl_obito) / COUNT(*) * 100, 2) AS taxa_mortalidade,
    ROUND(SUM(vl_total_internacao), 2) AS valor_total,
    ROUND(AVG(qt_dias_permanencia), 1) AS permanencia_media
FROM VW_INTERNACAO_COMPLETA;

-- Consolida o volume de internações por diagnóstico.
CREATE OR REPLACE VIEW ADMIN.VW_TOP_DIAGNOSTICOS AS
SELECT
    ds_diagnostico,
    COUNT(*) AS qtd
FROM VW_INTERNACAO_COMPLETA
GROUP BY ds_diagnostico;

-- Consolida a evolução mensal das internações por diagnóstico.
CREATE OR REPLACE VIEW ADMIN.VW_DIAGNOSTICO_TEMPORAL AS
SELECT
    ds_diagnostico,
    nr_ano_competencia,
    nr_mes_competencia,
    COUNT(*) AS qtd
FROM VW_INTERNACAO_COMPLETA
GROUP BY
    ds_diagnostico,
    nr_ano_competencia,
    nr_mes_competencia;

-- Calcula o volume e a mortalidade por caráter da internação.
CREATE OR REPLACE VIEW ADMIN.VW_MORTALIDADE_CARATER AS
SELECT
    ds_carater_internacao,
    COUNT(*) AS qtd_internacoes,
    ROUND(SUM(fl_obito) / COUNT(*) * 100, 2) AS taxa_mortalidade
FROM VW_INTERNACAO_COMPLETA
GROUP BY ds_carater_internacao;

-- Calcula mortalidade por diagnóstico para grupos com volume mínimo.
CREATE OR REPLACE VIEW ADMIN.VW_MORTALIDADE_DIAGNOSTICO AS
SELECT
    ds_diagnostico,
    COUNT(*) AS qtd_internacoes,
    SUM(fl_obito) AS qtd_obitos,
    ROUND(SUM(fl_obito) / COUNT(*) * 100, 2) AS taxa_mortalidade
FROM VW_INTERNACAO_COMPLETA
GROUP BY ds_diagnostico
HAVING COUNT(*) >= 500;

-- Consolida o volume total de internações por região de saúde.
CREATE OR REPLACE VIEW ADMIN.VW_VOLUME_REGIAO AS
SELECT
    nm_regiao_saude,
    COUNT(*) AS qtd_internacoes
FROM VW_INTERNACAO_COMPLETA
GROUP BY nm_regiao_saude;

-- Consolida a evolução mensal das internações por região de saúde.
CREATE OR REPLACE VIEW ADMIN.VW_VOLUME_REGIAO_TEMPORAL AS
SELECT
    nm_regiao_saude,
    nr_ano_competencia,
    nr_mes_competencia,
    COUNT(*) AS qtd_internacoes
FROM VW_INTERNACAO_COMPLETA
GROUP BY
    nm_regiao_saude,
    nr_ano_competencia,
    nr_mes_competencia;

-- Compara volume, permanência, UTI, mortalidade e valor por tipo de leito.
CREATE OR REPLACE VIEW ADMIN.VW_LEITOS_TIPO AS
SELECT
    CASE
        WHEN qt_dias_uti > 0 THEN 'UTI'
        ELSE 'Enfermaria / Outros'
    END AS tipo_leito,
    COUNT(*) AS qtd_internacoes,
    ROUND(AVG(qt_dias_permanencia), 1) AS permanencia_media,
    ROUND(AVG(qt_dias_uti), 1) AS dias_uti_medio,
    ROUND(SUM(fl_obito) / COUNT(*) * 100, 2) AS taxa_mortalidade,
    ROUND(SUM(vl_total_internacao), 2) AS valor_total
FROM VW_INTERNACAO_COMPLETA
GROUP BY
    CASE
        WHEN qt_dias_uti > 0 THEN 'UTI'
        ELSE 'Enfermaria / Outros'
    END;

-- Calcula internações por mil habitantes em cada região de saúde.
CREATE OR REPLACE VIEW ADMIN.VW_INTERNACAO_PER_CAPITA_REGIAO AS
SELECT
    v.nm_regiao_saude,
    v.qtd_internacoes,
    p.populacao,
    ROUND(v.qtd_internacoes / NULLIF(p.populacao, 0) * 1000, 1)
        AS internacoes_por_mil_hab
FROM VW_VOLUME_REGIAO v
JOIN VW_POPULACAO_REGIAO p
    ON p.nm_regiao_saude = v.nm_regiao_saude;

-- Enriquce internações com nome e esfera administrativa do estabelecimento.
CREATE OR REPLACE VIEW ADMIN.VW_INTERNACAO_ENRIQUECIDA AS
WITH estab AS (
    SELECT
        LPAD(e.cd_hospital, 10, '0') AS cd_hospital,
        MAX(JSON_VALUE(e.json_cadastro, '$.NO_FANTASIA')) AS nm_hospital,
        MAX(JSON_VALUE(e.json_cadastro, '$.DS_ESFERA_ADMINISTRATIVA'))
            AS esfera_admin
    FROM T_SIH_ESTABELECIMENTO e
    GROUP BY LPAD(e.cd_hospital, 10, '0')
)
SELECT
    i.nr_ano_competencia,
    i.nr_mes_competencia,
    i.nm_regiao_saude,
    i.nm_municipio,
    LPAD(i.cd_hospital, 10, '0') AS cd_hospital,
    NVL(x.nm_hospital, 'Hospital ' || LPAD(i.cd_hospital, 10, '0'))
        AS nm_hospital,
    NVL(x.esfera_admin, 'Não informado') AS esfera_admin,
    i.ds_diagnostico,
    i.ds_carater_internacao,
    i.ds_complexidade,
    i.qt_dias_permanencia,
    i.qt_dias_uti,
    i.fl_obito,
    i.vl_total_internacao,
    i.qt_leitos_sus
FROM VW_INTERNACAO_COMPLETA i
LEFT JOIN estab x
    ON x.cd_hospital = LPAD(i.cd_hospital, 10, '0');

-- Consolida permanência, capacidade, mortalidade e ocupação por hospital.
CREATE OR REPLACE VIEW ADMIN.VW_HOSPITAL_PERMANENCIA AS
WITH periodo AS (
    SELECT
        (
            MAX(nr_ano_competencia * 12 + nr_mes_competencia)
            - MIN(nr_ano_competencia * 12 + nr_mes_competencia)
            + 1
        ) * 30.4375 AS dias_periodo
    FROM VW_INTERNACAO_COMPLETA
),
base AS (
    SELECT
        LPAD(i.cd_hospital, 10, '0') AS cd_hospital,
        MAX(i.nm_regiao_saude) AS nm_regiao_saude,
        MAX(i.nm_municipio) AS nm_municipio,
        COUNT(*) AS qtd_internacoes,
        ROUND(AVG(i.qt_dias_permanencia), 1) AS permanencia_media,
        SUM(i.qt_dias_permanencia) AS dias_permanencia,
        MAX(i.qt_leitos_sus) AS leitos_sus,
        ROUND(SUM(i.fl_obito) / COUNT(*) * 100, 2) AS taxa_mortalidade
    FROM VW_INTERNACAO_COMPLETA i
    GROUP BY LPAD(i.cd_hospital, 10, '0')
    HAVING COUNT(*) >= 200
),
estab AS (
    SELECT
        LPAD(e.cd_hospital, 10, '0') AS cd_hospital,
        MAX(JSON_VALUE(e.json_cadastro, '$.NO_FANTASIA')) AS nm_fantasia,
        MAX(JSON_VALUE(e.json_cadastro, '$.NO_RAZAO_SOCIAL')) AS nm_razao_social,
        MAX(JSON_VALUE(e.json_cadastro, '$.DS_ESFERA_ADMINISTRATIVA'))
            AS esfera_admin,
        MAX(JSON_VALUE(e.json_cadastro, '$.NO_BAIRRO')) AS bairro,
        MAX(
            TO_NUMBER(
                JSON_VALUE(e.json_cadastro, '$.NU_LATITUDE')
                DEFAULT NULL ON CONVERSION ERROR
            )
        ) AS latitude,
        MAX(
            TO_NUMBER(
                JSON_VALUE(e.json_cadastro, '$.NU_LONGITUDE')
                DEFAULT NULL ON CONVERSION ERROR
            )
        ) AS longitude
    FROM T_SIH_ESTABELECIMENTO e
    GROUP BY LPAD(e.cd_hospital, 10, '0')
)
SELECT
    b.cd_hospital,
    NVL(x.nm_fantasia, 'Hospital ' || b.cd_hospital) AS nm_hospital,
    x.nm_razao_social,
    x.esfera_admin,
    x.bairro,
    x.latitude,
    x.longitude,
    b.nm_regiao_saude,
    b.nm_municipio,
    b.qtd_internacoes,
    b.permanencia_media,
    b.leitos_sus,
    b.taxa_mortalidade,
    ROUND(
        b.dias_permanencia
        / NULLIF(b.leitos_sus * p.dias_periodo, 0)
        * 100,
        1
    ) AS taxa_ocupacao
FROM base b
CROSS JOIN periodo p
LEFT JOIN estab x
    ON x.cd_hospital = b.cd_hospital;

-- Consolida capacidade instalada e ocupação por região de saúde.
CREATE OR REPLACE VIEW ADMIN.VW_CAPACIDADE_REGIAO AS
WITH leitos_por_hospital AS (
    SELECT
        nm_regiao_saude,
        cd_hospital,
        MAX(qt_leitos_sus) AS qt_leitos_hospital
    FROM VW_INTERNACAO_COMPLETA
    GROUP BY
        nm_regiao_saude,
        cd_hospital
),
leitos_por_regiao AS (
    SELECT
        nm_regiao_saude,
        SUM(qt_leitos_hospital) AS leitos_regiao
    FROM leitos_por_hospital
    GROUP BY nm_regiao_saude
),
metrica_regiao AS (
    SELECT
        nm_regiao_saude,
        COUNT(*) AS internacoes,
        SUM(qt_dias_permanencia) AS dias_permanencia
    FROM VW_INTERNACAO_COMPLETA
    GROUP BY nm_regiao_saude
),
periodo AS (
    SELECT
        (
            MAX(nr_ano_competencia * 12 + nr_mes_competencia)
            - MIN(nr_ano_competencia * 12 + nr_mes_competencia)
            + 1
        ) * 30.4375 AS dias_periodo
    FROM VW_INTERNACAO_COMPLETA
)
SELECT
    m.nm_regiao_saude,
    m.internacoes,
    l.leitos_regiao,
    ROUND(m.internacoes / NULLIF(l.leitos_regiao, 0), 1)
        AS internacoes_por_leito,
    ROUND(
        m.dias_permanencia
        / NULLIF(l.leitos_regiao * p.dias_periodo, 0)
        * 100,
        1
    ) AS taxa_ocupacao
FROM metrica_regiao m
JOIN leitos_por_regiao l
    ON m.nm_regiao_saude = l.nm_regiao_saude
CROSS JOIN periodo p;

-- Verifica o status de compilação das views recriadas.
SELECT
    object_name AS view_name,
    status
FROM user_objects
WHERE object_type = 'VIEW'
  AND object_name IN (
      'VW_INTERNACAO_COMPLETA',
      'VW_POPULACAO_REGIAO',
      'VW_KPIS_GERAIS',
      'VW_TOP_DIAGNOSTICOS',
      'VW_DIAGNOSTICO_TEMPORAL',
      'VW_MORTALIDADE_CARATER',
      'VW_MORTALIDADE_DIAGNOSTICO',
      'VW_VOLUME_REGIAO',
      'VW_VOLUME_REGIAO_TEMPORAL',
      'VW_LEITOS_TIPO',
      'VW_INTERNACAO_PER_CAPITA_REGIAO',
      'VW_INTERNACAO_ENRIQUECIDA',
      'VW_HOSPITAL_PERMANENCIA',
      'VW_CAPACIDADE_REGIAO'
  )
ORDER BY object_name;
