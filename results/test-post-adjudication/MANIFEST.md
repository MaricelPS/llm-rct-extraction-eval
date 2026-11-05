# Evaluación de test post-adjudicación

- Gold adjudicado: commit 6abdae3
  (lotes A-F; registro completo en data/gold/adjudications.csv).
- Papers: 19 elegibles. PMC11527811 excluido (GLP-1 RA solo como tratamiento de base,
  detectado durante la adjudicación).
- Extracciones: las de la corrida primaria (results/test-primary), sin re-extraer, salvo
  PMC11417641, que viene del análisis secundario (results/test-secondary-maxtokens).
- Prompt y guidelines: freeze-v1 (sin cambios). Evaluador: solo se agregó el export de
  diferencias (métricas verificadas idénticas antes y después).
- Diferencias restantes: 265, todas categorizadas (adjudication_sheet_test.csv; reglas en
  scripts/categorize_sheet.py).

## Métricas

| Set | Primaria pre (19 extraídos) | Post-adjudicación (19 elegibles) |
|---|---|---|
| arms | P 95,0% / R 95,0% | P 98% / R 98% |
| outcomes | P 81,5% / R 91,7% | P 91% / R 97% |
| adverse_events | P 66,5% / R 87,5% | P 95% / R 96% |

Las bases no son idénticas: la primaria no incluye PMC11417641 (fallo de extracción) e
incluye PMC11527811 (luego excluido).

Campos: ver eval_test_adjudicated.json.
