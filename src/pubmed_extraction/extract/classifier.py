"""Classify RCT-derived articles by report type from title and abstract."""

from pubmed_extraction.extract.llm import UsageTracker, get_client, structured_call
from pubmed_extraction.ingest.jats_parser import ParsedArticle
from pubmed_extraction.schemas.classification import ArticleClassification
from pubmed_extraction.settings import settings

SYSTEM_PROMPT = """You classify articles derived from randomized controlled trials by report type.

Definitions:
- primary_report: the main results report of a randomized trial, presenting the prespecified
  primary outcome of the randomized comparison. Small or mechanistic RCTs count if the article
  reports their own primary outcome.
- secondary_analysis: post hoc, exploratory or prespecified secondary analyses of one or more
  trials whose main results were reported elsewhere, including pooled analyses and biomarker
  or machine learning analyses of trial data, when the main objective is not a specific
  patient population.
- subgroup_analysis: any secondary, post hoc or pooled analysis whose main objective is to
  evaluate efficacy or safety in specific patient populations defined by demographic or
  clinical characteristics (e.g. age, renal or hepatic function, baseline HbA1c, disease
  duration). This category takes precedence over secondary_analysis: the purpose of the
  analysis determines the label, not the method used to assemble the data.
- protocol_or_design: trial rationale, design, methods or baseline characteristics without
  efficacy results.
- other: anything else (reviews, commentaries, non-randomized studies).

Rules:
- Base the decision only on the title and abstract provided.
- The evidence quote must be a single contiguous span copied verbatim from the title or
  abstract. Never use ellipses or join separate fragments."""


class ArticleClassifier:
    def __init__(self, model: str | None = None) -> None:
        self._client = get_client()
        self._model = model or settings.classification_model

    def classify(
        self, article: ParsedArticle, usage: UsageTracker | None = None
    ) -> ArticleClassification:
        usage = usage if usage is not None else UsageTracker()
        content = f"<title>{article.title}</title>\n<abstract>{article.abstract}</abstract>"
        return structured_call(
            self._client,
            model=self._model,
            max_tokens=settings.classification_max_tokens,
            system=SYSTEM_PROMPT,
            user_content=content,
            output_model=ArticleClassification,
            usage=usage,
        )
