# Análisis secundario: re-extracción de PMC11417641

- Desviación documentada respecto de la corrida primaria (results/test-primary).
- Única diferencia: PX_EXTRACTION_MAX_TOKENS=32000 y PX_EXTRACTION_TIMEOUT=1800,
  solo para PMC11417641. Prompt y guidelines sin cambios (freeze-v1).
- Cambio de código previo: timeout configurable (sin efecto con el valor por defecto).
- Resultado: 2 arms, 7 outcomes, 166 AEs; 0 errores de validación;
  tokens in/out 61702/26974.
- Los otros 19 papers son los de la corrida primaria.
- Métricas: eval_test_20papers.json (sin adjudicar).

## Trazabilidad

- Código usado en la re-extracción: commit b705e4e
  (commiteado después de correr; el diff es solo el timeout configurable).

## Métricas (20 papers, sin adjudicar)

| Set | Precisión | Recall |
|---|---|---|
| arms | 95% | 95% |
| outcomes | 68% | 92% |
| adverse_events | 77% | 92% |

## Hallazgos de PMC11417641

- adverse_events.term cae a 60% en total: el modelo omite el prefijo de la fila padre
  (Possibly-related / Study-related / Not study-related adverse events, discontinuation).
  El gold aplica la regla de fila padre calificadora; la guideline es ambigua cuando la fila
  también nombra un evento. Para adjudicar: error del modelo con guideline ambigua.
- 6 outcomes de composición corporal marcados como primarios (el gold tiene 1): verificar en el paper.
- Dose con escalada en gold (patrón conocido); "1·0" con punto medio no normalizado por dose_eq.
