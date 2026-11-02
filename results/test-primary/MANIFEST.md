# Corrida primaria de test

- Configuración: commit b2f7b14 (tag freeze-v1)
- Modelo: claude-sonnet-5, effort medium, extraction_max_tokens 8192
- Extracción: 2 papers el 2026-10-27 (corte por límite mensual de gasto de la API),
  17 papers el 2026-11-02; sin cambios de código entre ambas sesiones
- Papers de test: 20; extraídos: 19
- Fallo: PMC11417641, AdverseEventsOutput con JSON truncado
  (probable max_tokens con thinking incluido; stop_reason y tokens no registrados)
- Métricas: eval_test_19papers.json (sin adjudicar)
