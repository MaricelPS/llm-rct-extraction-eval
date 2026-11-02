# Corrida primaria de test

- Configuración: commit b2f7b14 (tag freeze-v1)
- Modelo: claude-sonnet-5, effort medium, extraction_max_tokens 8192
- Extracción: 2 papers el 2026-10-27 (corte por límite mensual de gasto de la API),
  17 papers el 2026-11-02; sin cambios de código entre ambas sesiones
- Papers de test: 20; extraídos: 19
- Fallo: PMC11417641, AdverseEventsOutput con JSON truncado
  (probable max_tokens con thinking incluido; stop_reason y tokens no registrados)
- Métricas: eval_test_19papers.json (sin adjudicar)

## Métricas primarias (pre-adjudicación)

PMC11417641 aporta 2 brazos, 1 outcome y 166 AEs en gold (39% de los AEs de test).

| Set | Precisión | Recall (19 papers) | Recall (20, fallo = vacío) |
|---|---|---|---|
| arms | 95,0% | 95,0% | 90,5% |
| outcomes | 81,5% | 91,7% | 88,0% |
| adverse_events | 66,5% | 87,5% | 53,1% |

| Campo | 19 papers | 20 papers |
|---|---|---|
| population.condition | 8/19 | 8/20 |
| population.mean_age | 18/19 | 18/20 |
| population.percent_female | 17/19 | 17/20 |
