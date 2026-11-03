"""Field-level comparison between gold annotations and model extractions."""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from pubmed_extraction.extract.validation import _normalize
from pubmed_extraction.schemas.trial import TrialExtraction

ARM_THRESHOLD = 0.6
TEXT_THRESHOLD = 0.85
NUM_TOLERANCE = 1e-6


@dataclass
class Tally:
    correct: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.total += 1
        self.correct += int(ok)

@dataclass
class Diff:
    pmcid: str
    section: str
    label: str
    field: str   # nombre del campo, o "_object" para faltantes/sobrantes
    kind: str    # "mismatch" | "missing" | "extra"
    gold: object
    pred: object

@dataclass
class PaperReport:
    pmcid: str
    fields: dict[str, Tally] = field(default_factory=dict)
    sets: dict[str, dict[str, int]] = field(default_factory=dict)
    diffs: list[str] = field(default_factory=list)
    records: list[Diff] = field(default_factory=list)

    def check(self, section: str, label: str, name: str, ok: bool, gold, pred) -> None:
        self.fields.setdefault(f"{section}.{name}", Tally()).add(ok)
        if not ok:
            self.diffs.append(f"{section} [{label}] {name}: gold={gold!r} pred={pred!r}")
            self.records.append(Diff(self.pmcid, section, label, name, "mismatch", gold, pred))

    def object_diff(self, section: str, label: str, kind: str) -> None:
        """Objeto faltante ("missing") o sobrante ("extra") en la predicción."""
        if kind == "missing":
            suffix = "missing in prediction"
        elif section == "outcomes":
            suffix = "extra primary in prediction"
        else:
            suffix = "extra in prediction"
        self.diffs.append(f"{section} [{label}] {suffix}")
        gold, pred = (label, None) if kind == "missing" else (None, label)
        self.records.append(Diff(self.pmcid, section, label, "_object", kind, gold, pred))

def similarity(a: str | None, b: str | None) -> float:
    return SequenceMatcher(None, _normalize(a or ""), _normalize(b or "")).ratio()

def text_eq(gold: str | None, pred: str | None) -> bool:
    if not gold and not pred:
        return True
    if not gold or not pred:
        return False
    return similarity(gold, pred) >= TEXT_THRESHOLD

def num_eq(gold: float | None, pred: float | None) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    return abs(float(gold) - float(pred)) <= NUM_TOLERANCE


def p_norm(value: str | None) -> str:
    text = _normalize(value or "").replace(" ", "")
    text = re.sub(r"^p=?", "", text)  # "p<0.01" == "<0.01"
    return re.sub(r"(?<!\d)0\.", ".", text)  # "<0.001" == "<.001"

_TIME_UNITS = r"(day|week|month|year)"


def _numbers(text: str | None) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", _normalize(text or "")))


def tp_eq(gold: str | None, pred: str | None) -> bool:
    """Timepoints match if they name the same number and unit ("week 26" == "26 weeks")."""
    def key(text: str | None) -> str:
        s = _normalize(text or "")
        m = re.search(rf"(\d+(?:\.\d+)?)\s*-?\s*{_TIME_UNITS}s?", s) or re.search(
            rf"{_TIME_UNITS}s?\s*(\d+(?:\.\d+)?)", s
        )
        if not m:
            return s
        groups = m.groups()
        number, unit = (groups[0], groups[1]) if groups[0][0].isdigit() else (groups[1], groups[0])
        return f"{number} {unit}"
    return key(gold) == key(pred) or text_eq(gold, pred)


def dose_eq(gold: str | None, pred: str | None) -> bool:
    """Doses match if they contain the same numbers; otherwise fall back to text similarity."""
    if not gold and not pred:
        return True
    g_nums, p_nums = _numbers(gold), _numbers(pred)
    if g_nums or p_nums:
        return g_nums == p_nums
    return text_eq(gold, pred)


def arm_score(gold_arm, pred_arm) -> float:
    """Name similarity plus bonuses for matching role, drug and dose numbers."""
    score = similarity(gold_arm.name, pred_arm.name)
    if gold_arm.role == pred_arm.role:
        score += 0.1
        if gold_arm.role.value == "placebo":
            score += 0.3
    if gold_arm.drug and pred_arm.drug and text_eq(gold_arm.drug, pred_arm.drug):
        score += 0.3
    gold_nums, pred_nums = _numbers(gold_arm.dose), _numbers(pred_arm.dose)
    if gold_nums and gold_nums == pred_nums:
        score += 0.2
    return score


def match_arms(gold: TrialExtraction, pred: TrialExtraction) -> dict[str, str]:
    """Greedy matching on name, role, drug and dose. Returns {pred arm name: gold arm name}."""
    pairs = sorted(
        ((arm_score(g, p), g.name, p.name) for g in gold.arms for p in pred.arms),
        reverse=True,
    )
    mapping: dict[str, str] = {}
    used_gold: set[str] = set()
    for score, g_name, p_name in pairs:
        if score < ARM_THRESHOLD or p_name in mapping or g_name in used_gold:
            continue
        mapping[p_name] = g_name
        used_gold.add(g_name)
    return mapping


def _sides(comparison: str, arm_map: dict[str, str] | None = None) -> tuple[str, ...]:
    sides = [s.strip() for s in comparison.split(" vs ")]
    if arm_map is not None:
        normalized_map = {_normalize(p): g for p, g in arm_map.items()}
        sides = [normalized_map.get(_normalize(s), s) for s in sides]
    return tuple(_normalize(s) for s in sides)


def compare(gold: TrialExtraction, pred: TrialExtraction) -> PaperReport:
    report = PaperReport(pmcid=gold.pmcid)

    # Population
    gp, pp = gold.population, pred.population
    report.check("population", "-", "condition", text_eq(gp.condition, pp.condition),
                 gp.condition, pp.condition)
    report.check("population", "-", "mean_age", num_eq(gp.mean_age, pp.mean_age),
                 gp.mean_age, pp.mean_age)
    report.check("population", "-", "percent_female", num_eq(gp.percent_female, pp.percent_female),
                 gp.percent_female, pp.percent_female)

    # Arms
    arm_map = match_arms(gold, pred)
    pred_by_gold = {g: p for p, g in arm_map.items()}
    pred_arms = {a.name: a for a in pred.arms}
    report.sets["arms"] = {"gold": len(gold.arms), "pred": len(pred.arms), "matched": len(arm_map)}
    for g_arm in gold.arms:
        p_name = pred_by_gold.get(g_arm.name)
        if p_name is None:
            report.object_diff("arms",g_arm.name, "missing")
            continue
        p_arm = pred_arms[p_name]
        for name, ok, gv, pv in [
            ("role", g_arm.role == p_arm.role, g_arm.role, p_arm.role),
            ("drug", text_eq(g_arm.drug, p_arm.drug), g_arm.drug, p_arm.drug),
            ("dose", dose_eq(g_arm.dose, p_arm.dose), g_arm.dose, p_arm.dose),
            ("route", g_arm.route == p_arm.route, g_arm.route, p_arm.route),
            ("is_fixed_combination", g_arm.is_fixed_combination == p_arm.is_fixed_combination,
             g_arm.is_fixed_combination, p_arm.is_fixed_combination),
            ("n_randomized", num_eq(g_arm.n_randomized, p_arm.n_randomized),
             g_arm.n_randomized, p_arm.n_randomized),
            ("n_analyzed", num_eq(g_arm.n_analyzed, p_arm.n_analyzed),
             g_arm.n_analyzed, p_arm.n_analyzed),
        ]:
            report.check("arms", g_arm.name, name, ok, gv, pv)
    for p_arm in pred.arms:
        if p_arm.name not in arm_map:
            report.object_diff("arms", p_arm.name, "extra")

    # Primary outcomes: match on comparison, then estimand and name similarity
    pred_primary = [o for o in pred.outcomes if o.is_primary]
    remaining = list(pred_primary)
    matched = 0
    for g_out in gold.outcomes:
        g_sides = _sides(g_out.comparison)
        candidates = [o for o in remaining if _sides(o.comparison, arm_map) == g_sides]
        label = f"{g_out.name[:40]} | {g_out.comparison} / {g_out.estimand.value}"
        if not candidates:
            report.object_diff("outcomes",label,"missing")
            continue
        p_out = max(candidates, key=lambda o: (o.estimand == g_out.estimand,
                                               similarity(o.name, g_out.name)))
        remaining.remove(p_out)
        matched += 1
        for name, ok, gv, pv in [
            ("timepoint", tp_eq(g_out.timepoint, p_out.timepoint), g_out.timepoint, p_out.timepoint),
            ("effect_measure", g_out.effect_measure == p_out.effect_measure,
             g_out.effect_measure, p_out.effect_measure),
            ("estimand", g_out.estimand == p_out.estimand, g_out.estimand, p_out.estimand),
            ("value", num_eq(g_out.value, p_out.value), g_out.value, p_out.value),
            ("ci_lower", num_eq(g_out.ci_lower, p_out.ci_lower), g_out.ci_lower, p_out.ci_lower),
            ("ci_upper", num_eq(g_out.ci_upper, p_out.ci_upper), g_out.ci_upper, p_out.ci_upper),
            ("ci_level", num_eq(g_out.ci_level, p_out.ci_level), g_out.ci_level, p_out.ci_level),
            ("p_value", p_norm(g_out.p_value) == p_norm(p_out.p_value), g_out.p_value, p_out.p_value),
            ("unit", text_eq(g_out.unit, p_out.unit), g_out.unit, p_out.unit),
        ]:
            report.check("outcomes", label, name, ok, gv, pv)
    for p_out in remaining:
        report.object_diff("outcomes",f"{p_out.name[:40]} | {p_out.comparison} / {p_out.estimand.value}",
            "extra"
        )
    report.sets["outcomes"] = {"gold": len(gold.outcomes), "pred": len(pred_primary), "matched": matched}

    # Adverse events: match on (term, arm), exact normalized term first, then fuzzy
    normalized_map = {_normalize(p): g for p, g in arm_map.items()}
    pred_aes = [
        (normalized_map.get(_normalize(ae.arm_name), ae.arm_name), ae)
        for ae in pred.adverse_events
    ]
    remaining_aes = list(pred_aes)
    matched_aes = 0
    for g_ae in gold.adverse_events:
        same_arm = [
            (arm, ae) for arm, ae in remaining_aes
            if _normalize(arm) == _normalize(g_ae.arm_name)
        ]
        exact = [x for x in same_arm if _normalize(x[1].term) == _normalize(g_ae.term)]
        fuzzy = [x for x in same_arm if similarity(x[1].term, g_ae.term) >= TEXT_THRESHOLD]

        def _core(term: str) -> str:
            return _normalize(term.split(": ")[-1])

        by_core = [x for x in same_arm if _core(x[1].term) == _core(g_ae.term)]
        pool = exact or fuzzy or by_core
        label = f"{g_ae.term} / {g_ae.arm_name}"
        if not pool:
            report.object_diff("adverse_events",label, "missing")
            continue
        pick = max(pool, key=lambda x: similarity(x[1].term, g_ae.term))
        remaining_aes.remove(pick)
        p_ae = pick[1]
        matched_aes += 1
        for name, ok, gv, pv in [
            ("term", _normalize(p_ae.term) == _normalize(g_ae.term), g_ae.term, p_ae.term),
            ("n_patients", num_eq(g_ae.n_patients, p_ae.n_patients), g_ae.n_patients, p_ae.n_patients),
            ("percent_patients", num_eq(g_ae.percent_patients, p_ae.percent_patients),
             g_ae.percent_patients, p_ae.percent_patients),
            ("is_serious", g_ae.is_serious == p_ae.is_serious, g_ae.is_serious, p_ae.is_serious),
        ]:
            report.check("adverse_events", label, name, ok, gv, pv)
    for arm, p_ae in remaining_aes:
        report.object_diff("adverse_events", f"{p_ae.term} / {arm}", "extra")
    report.sets["adverse_events"] = {
        "gold": len(gold.adverse_events), "pred": len(pred.adverse_events), "matched": matched_aes,
    }
    return report


def summarize(reports: list[PaperReport]) -> dict:
    """Aggregate field accuracy and set-level precision/recall across papers."""
    fields: dict[str, Tally] = {}
    sets: dict[str, dict[str, int]] = {}
    for report in reports:
        for key, tally in report.fields.items():
            agg = fields.setdefault(key, Tally())
            agg.correct += tally.correct
            agg.total += tally.total
        for section, counts in report.sets.items():
            agg_set = sets.setdefault(section, {"gold": 0, "pred": 0, "matched": 0})
            for k, v in counts.items():
                agg_set[k] += v
    return {
        "fields": {k: {"correct": t.correct, "total": t.total} for k, t in sorted(fields.items())},
        "sets": {
            section: {
                **c,
                "precision": c["matched"] / c["pred"] if c["pred"] else None,
                "recall": c["matched"] / c["gold"] if c["gold"] else None,
            }
            for section, c in sets.items()
        },
    }
