-- Importacao manual extraida do PDF "caicara (1).pdf".
-- Antes de executar no Supabase, troque TROQUE_PELO_USERNAME pelo username correto do sistema.
-- Regras usadas:
-- - Galpao 2: A, J = Jumbo, E/EX = Extra.
-- - Galpao 3: A, B, E/EX = Extra.
-- - Cor: sempre Branco.
-- - Q: ovos quebrados do respectivo galpao.
-- - "galinha morta (2)" = aves mortas no Galpao 2; "(3)" = Galpao 3.
-- - O Q do Galpao 2 em 02/08/2026 estava sem numero legivel e foi omitido.

BEGIN;

WITH usuario AS (
    SELECT 'TROQUE_PELO_USERNAME'::text AS username
),
dados_producao(data, galpao, tipo, quantidade) AS (
    VALUES
        ('2026-07-30'::date, 'Galpão 2', 'A', 720),
        ('2026-07-30'::date, 'Galpão 2', 'Jumbo', 1244),
        ('2026-07-30'::date, 'Galpão 2', 'Extra', 612),
        ('2026-07-30'::date, 'Galpão 3', 'A', 2605),
        ('2026-07-30'::date, 'Galpão 3', 'B', 376),
        ('2026-07-30'::date, 'Galpão 3', 'Extra', 520),

        ('2026-07-31'::date, 'Galpão 2', 'A', 648),
        ('2026-07-31'::date, 'Galpão 2', 'Jumbo', 1468),
        ('2026-07-31'::date, 'Galpão 2', 'Extra', 488),
        ('2026-07-31'::date, 'Galpão 3', 'A', 2540),
        ('2026-07-31'::date, 'Galpão 3', 'B', 300),
        ('2026-07-31'::date, 'Galpão 3', 'Extra', 581),

        ('2026-08-01'::date, 'Galpão 2', 'A', 646),
        ('2026-08-01'::date, 'Galpão 2', 'Jumbo', 1138),
        ('2026-08-01'::date, 'Galpão 2', 'Extra', 501),
        ('2026-08-01'::date, 'Galpão 3', 'A', 2501),
        ('2026-08-01'::date, 'Galpão 3', 'B', 300),
        ('2026-08-01'::date, 'Galpão 3', 'Extra', 646),

        ('2026-08-02'::date, 'Galpão 2', 'A', 605),
        ('2026-08-02'::date, 'Galpão 2', 'Jumbo', 1372),
        ('2026-08-02'::date, 'Galpão 2', 'Extra', 658),
        ('2026-08-02'::date, 'Galpão 3', 'A', 2610),
        ('2026-08-02'::date, 'Galpão 3', 'B', 319),
        ('2026-08-02'::date, 'Galpão 3', 'Extra', 702),

        ('2026-08-04'::date, 'Galpão 2', 'A', 623),
        ('2026-08-04'::date, 'Galpão 2', 'Jumbo', 1578),
        ('2026-08-04'::date, 'Galpão 2', 'Extra', 510),
        ('2026-08-04'::date, 'Galpão 3', 'A', 2377),
        ('2026-08-04'::date, 'Galpão 3', 'B', 215),
        ('2026-08-04'::date, 'Galpão 3', 'Extra', 734),

        ('2026-08-05'::date, 'Galpão 2', 'A', 598),
        ('2026-08-05'::date, 'Galpão 2', 'Jumbo', 1600),
        ('2026-08-05'::date, 'Galpão 2', 'Extra', 471),
        ('2026-08-05'::date, 'Galpão 3', 'A', 2520),
        ('2026-08-05'::date, 'Galpão 3', 'B', 260),
        ('2026-08-05'::date, 'Galpão 3', 'Extra', 751),

        ('2026-08-06'::date, 'Galpão 2', 'A', 540),
        ('2026-08-06'::date, 'Galpão 2', 'Jumbo', 1502),
        ('2026-08-06'::date, 'Galpão 2', 'Extra', 480),
        ('2026-08-06'::date, 'Galpão 3', 'A', 2559),
        ('2026-08-06'::date, 'Galpão 3', 'B', 267),
        ('2026-08-06'::date, 'Galpão 3', 'Extra', 779),

        ('2026-08-07'::date, 'Galpão 2', 'A', 639),
        ('2026-08-07'::date, 'Galpão 2', 'Jumbo', 1603),
        ('2026-08-07'::date, 'Galpão 2', 'Extra', 408),
        ('2026-08-07'::date, 'Galpão 3', 'A', 2520),
        ('2026-08-07'::date, 'Galpão 3', 'B', 234),
        ('2026-08-07'::date, 'Galpão 3', 'Extra', 482),

        ('2026-08-08'::date, 'Galpão 2', 'A', 593),
        ('2026-08-08'::date, 'Galpão 2', 'Jumbo', 1469),
        ('2026-08-08'::date, 'Galpão 2', 'Extra', 408),
        ('2026-08-08'::date, 'Galpão 3', 'A', 2350),
        ('2026-08-08'::date, 'Galpão 3', 'B', 251),
        ('2026-08-08'::date, 'Galpão 3', 'Extra', 897),

        ('2026-08-09'::date, 'Galpão 2', 'A', 565),
        ('2026-08-09'::date, 'Galpão 2', 'Jumbo', 1543),
        ('2026-08-09'::date, 'Galpão 2', 'Extra', 550),
        ('2026-08-09'::date, 'Galpão 3', 'A', 2460),
        ('2026-08-09'::date, 'Galpão 3', 'B', 230),
        ('2026-08-09'::date, 'Galpão 3', 'Extra', 885),

        ('2026-08-10'::date, 'Galpão 2', 'A', 647),
        ('2026-08-10'::date, 'Galpão 2', 'Jumbo', 1483),
        ('2026-08-10'::date, 'Galpão 2', 'Extra', 510),
        ('2026-08-10'::date, 'Galpão 3', 'A', 2358),
        ('2026-08-10'::date, 'Galpão 3', 'B', 238),
        ('2026-08-10'::date, 'Galpão 3', 'Extra', 902),

        ('2026-08-11'::date, 'Galpão 2', 'A', 621),
        ('2026-08-11'::date, 'Galpão 2', 'Jumbo', 1688),
        ('2026-08-11'::date, 'Galpão 2', 'Extra', 495),
        ('2026-08-11'::date, 'Galpão 3', 'A', 2393),
        ('2026-08-11'::date, 'Galpão 3', 'B', 232),
        ('2026-08-11'::date, 'Galpão 3', 'Extra', 952),

        ('2026-08-12'::date, 'Galpão 2', 'A', 553),
        ('2026-08-12'::date, 'Galpão 2', 'Jumbo', 1326),
        ('2026-08-12'::date, 'Galpão 2', 'Extra', 540),
        ('2026-08-12'::date, 'Galpão 3', 'A', 2437),
        ('2026-08-12'::date, 'Galpão 3', 'B', 232),
        ('2026-08-12'::date, 'Galpão 3', 'Extra', 932),

        ('2026-08-13'::date, 'Galpão 2', 'A', 592),
        ('2026-08-13'::date, 'Galpão 2', 'Jumbo', 1275),
        ('2026-08-13'::date, 'Galpão 2', 'Extra', 540),
        ('2026-08-13'::date, 'Galpão 3', 'A', 2271),
        ('2026-08-13'::date, 'Galpão 3', 'B', 210),
        ('2026-08-13'::date, 'Galpão 3', 'Extra', 964),

        ('2026-08-14'::date, 'Galpão 2', 'A', 702),
        ('2026-08-14'::date, 'Galpão 2', 'Jumbo', 1586),
        ('2026-08-14'::date, 'Galpão 2', 'Extra', 578),
        ('2026-08-14'::date, 'Galpão 3', 'A', 2313),
        ('2026-08-14'::date, 'Galpão 3', 'B', 237),
        ('2026-08-14'::date, 'Galpão 3', 'Extra', 944)
)
INSERT INTO producao (username, data, quantidade, tipo, galpao, cor)
SELECT u.username, d.data, d.quantidade, d.tipo, d.galpao, 'Branco'
FROM dados_producao d
CROSS JOIN usuario u
WHERE NOT EXISTS (
    SELECT 1
    FROM producao p
    WHERE p.username = u.username
      AND p.data = d.data
      AND p.tipo = d.tipo
      AND p.galpao = d.galpao
);

WITH usuario AS (
    SELECT 'TROQUE_PELO_USERNAME'::text AS username
),
dados_quebrados(data, galpao, quantidade) AS (
    VALUES
        ('2026-07-30'::date, 'Galpão 2', 176),
        ('2026-07-30'::date, 'Galpão 3', 38),
        ('2026-07-31'::date, 'Galpão 2', 165),
        ('2026-07-31'::date, 'Galpão 3', 63),
        ('2026-08-01'::date, 'Galpão 2', 180),
        ('2026-08-01'::date, 'Galpão 3', 42),
        ('2026-08-02'::date, 'Galpão 3', 53),
        ('2026-08-04'::date, 'Galpão 2', 180),
        ('2026-08-04'::date, 'Galpão 3', 53),
        ('2026-08-05'::date, 'Galpão 2', 192),
        ('2026-08-05'::date, 'Galpão 3', 45),
        ('2026-08-06'::date, 'Galpão 2', 207),
        ('2026-08-06'::date, 'Galpão 3', 46),
        ('2026-08-07'::date, 'Galpão 2', 210),
        ('2026-08-07'::date, 'Galpão 3', 35),
        ('2026-08-08'::date, 'Galpão 2', 187),
        ('2026-08-08'::date, 'Galpão 3', 37),
        ('2026-08-09'::date, 'Galpão 2', 229),
        ('2026-08-09'::date, 'Galpão 3', 48),
        ('2026-08-10'::date, 'Galpão 2', 182),
        ('2026-08-10'::date, 'Galpão 3', 45),
        ('2026-08-11'::date, 'Galpão 2', 224),
        ('2026-08-11'::date, 'Galpão 3', 49),
        ('2026-08-12'::date, 'Galpão 2', 295),
        ('2026-08-12'::date, 'Galpão 3', 64),
        ('2026-08-13'::date, 'Galpão 2', 95),
        ('2026-08-13'::date, 'Galpão 3', 35),
        ('2026-08-14'::date, 'Galpão 2', 219),
        ('2026-08-14'::date, 'Galpão 3', 39)
)
INSERT INTO ovos_quebrados (username, galpao, quantidade, data)
SELECT u.username, d.galpao, d.quantidade, d.data
FROM dados_quebrados d
CROSS JOIN usuario u
WHERE NOT EXISTS (
    SELECT 1
    FROM ovos_quebrados q
    WHERE q.username = u.username
      AND q.data = d.data
      AND q.galpao = d.galpao
);

WITH usuario AS (
    SELECT 'TROQUE_PELO_USERNAME'::text AS username
),
dados_mortalidade(data, galpao, quantidade) AS (
    VALUES
        ('2026-08-01'::date, 'Galpão 2', 3),
        ('2026-08-04'::date, 'Galpão 2', 5),
        ('2026-08-05'::date, 'Galpão 2', 2),
        ('2026-08-06'::date, 'Galpão 2', 2),
        ('2026-08-07'::date, 'Galpão 2', 1),
        ('2026-08-07'::date, 'Galpão 3', 3),
        ('2026-08-08'::date, 'Galpão 2', 6),
        ('2026-08-10'::date, 'Galpão 2', 3),
        ('2026-08-11'::date, 'Galpão 2', 3),
        ('2026-08-12'::date, 'Galpão 2', 2),
        ('2026-08-12'::date, 'Galpão 3', 1),
        ('2026-08-13'::date, 'Galpão 2', 1),
        ('2026-08-13'::date, 'Galpão 3', 1),
        ('2026-08-14'::date, 'Galpão 3', 1)
)
INSERT INTO aves_mortas (username, galpao, quantidade, data)
SELECT u.username, d.galpao, d.quantidade, d.data
FROM dados_mortalidade d
CROSS JOIN usuario u
WHERE NOT EXISTS (
    SELECT 1
    FROM aves_mortas m
    WHERE m.username = u.username
      AND m.data = d.data
      AND m.galpao = d.galpao
);

COMMIT;

-- Conferencia apos executar:
-- SELECT data, galpao, tipo, cor, quantidade FROM producao WHERE username = 'TROQUE_PELO_USERNAME' AND data BETWEEN '2026-07-30' AND '2026-08-14' ORDER BY data, galpao, tipo;
-- SELECT data, galpao, quantidade FROM ovos_quebrados WHERE username = 'TROQUE_PELO_USERNAME' AND data BETWEEN '2026-07-30' AND '2026-08-14' ORDER BY data, galpao;
-- SELECT data, galpao, quantidade FROM aves_mortas WHERE username = 'TROQUE_PELO_USERNAME' AND data BETWEEN '2026-07-30' AND '2026-08-14' ORDER BY data, galpao;
