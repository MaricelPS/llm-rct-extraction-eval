# Análisis secundario: re-extracción de PMC11417641

- Desviación documentada respecto de la corrida primaria (results/test-primary).
- Única diferencia: PX_EXTRACTION_MAX_TOKENS=32000 y PX_EXTRACTION_TIMEOUT=1800,
  solo para PMC11417641. Prompt y guidelines sin cambios (freeze-v1).
- Cambio de código previo: timeout configurable (sin efecto con el valor por defecto).
- Resultado: 2 arms, 7 outcomes, 166 AEs; 0 errores de validación;
  tokens in/out 61702/26974.
- Los otros 19 papers son los de la corrida primaria.
- Métricas: eval_test_20papers.json (sin adjudicar).
