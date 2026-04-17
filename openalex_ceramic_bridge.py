from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any


RUNTIME_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
USER_BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LEGACY_RUNTIME_DIR = RUNTIME_BASE_DIR / "CeramicSolutionsStudio.exe_extracted"
PYZ_DIR = LEGACY_RUNTIME_DIR / "PYZ.pyz_extracted"
PACKAGE_DIR = PYZ_DIR / "sherif_chemistry_toolkit"
EXTERNAL_ASSETS_DIR = LEGACY_RUNTIME_DIR / "sherif_chemistry_toolkit" / "assets"
EMBEDDED_ASSETS_DIR = PACKAGE_DIR / "assets"
CONFIG_PATH = USER_BASE_DIR / "openalex_config.json"


def _ensure_runtime_ready() -> None:
    if not PYZ_DIR.exists():
        raise FileNotFoundError(
            "تعذر العثور على الملفات المستخرجة للتطبيق الأصلي. "
            "تأكد من وجود المجلد CeramicSolutionsStudio.exe_extracted بجانب هذا الملف."
        )

    if EXTERNAL_ASSETS_DIR.exists():
        try:
            shutil.copytree(EXTERNAL_ASSETS_DIR, EMBEDDED_ASSETS_DIR, dirs_exist_ok=True)
        except shutil.Error:
            pass

    pyz_dir = str(PYZ_DIR)
    if pyz_dir not in sys.path:
        sys.path.insert(0, pyz_dir)


_ensure_runtime_ready()

import tkinter as tk
from tkinter import messagebox

from sherif_chemistry_toolkit.ceramic_knowledge import CeramicIssue, all_issues, find_issues
from sherif_chemistry_toolkit.main_window import CeramicSolutionsStudio as BaseStudio


OPENALEX_URL = "https://api.openalex.org/works"
OPENALEX_AUTOCOMPLETE_URL = "https://api.openalex.org/autocomplete/works"
ANCHOR_TERMS = ("ceramic tile", "porcelain tile", "porcelain", "ceramic")
DEFAULT_OPENALEX_FILTER = "type:article|review,has_abstract:true,publication_year:>1990,cited_by_count:>1"
REMOTE_AUTOCOMPLETE_MIN_CHARS = 2
REMOTE_AUTOCOMPLETE_LIMIT = 4
LOCAL_SUGGESTION_LIMIT = 6
RELATED_WORKS_LIMIT = 6
FINAL_PAPERS_LIMIT = 7
SEMANTIC_COOLDOWN_SECONDS = 1.2
CORE_CERAMIC_SIGNAL_TERMS = {
    "ceramic",
    "ceramic tile",
    "porcelain",
    "porcelain tile",
    "alumina",
    "clay",
    "kaolin",
    "feldspar",
    "quartz",
    "mullite",
    "glaze",
    "kiln",
    "sintering",
}
NOISY_TERMS = {
    "hydroxyapatite",
    "bone",
    "dental",
    "dentistry",
    "implant",
    "orthopedic",
    "scaffold",
    "bioceramic",
    "perovskite",
    "photonic",
    "wood",
    "timber",
    "radioactive",
    "waste disposal",
    "bentonite",
    "geotechnical",
    "snake",
    "melanoma",
    "leukemia",
    "toxin",
    "nanocrystal",
    "nanocrystals",
    "biosensor",
    "drug delivery",
    "bone tissue",
}
MANUFACTURING_TERMS = {
    "tile",
    "porcelain",
    "glaze",
    "firing",
    "kiln",
    "drying",
    "pressing",
    "green body",
    "sintering",
    "kaolin",
    "feldspar",
    "quartz",
    "vitrification",
    "water absorption",
    "porosity",
    "thermal shock",
    "cracks",
    "shivering",
    "crazing",
}
CAUSE_MARKERS = (
    "due to",
    "caused by",
    "because",
    "attributed to",
    "associated with",
    "results from",
    "related to",
)
ACTION_MARKERS = (
    "reduce",
    "improve",
    "control",
    "optimize",
    "increase",
    "decrease",
    "prevent",
    "avoid",
    "stabilize",
)
ISSUE_RESEARCH_HINTS = {
    "drying_cracks": "الأبحاث الأقرب ركزت على معدل التجفيف، توزيع الرطوبة، وسلوك الجسم الأخضر قبل الحرق.",
    "drying_warping": "الدراسات ربطت الاعوجاج غالبًا بعدم تجانس الانكماش والرطوبة داخل البلاطة.",
    "thermal_cracking": "أغلب الأعمال القريبة دعمت أثر التبريد وفروق التمدد الحراري على الشروخ.",
    "high_porosity": "النتائج الأقرب ركزت على نضج الحرق، الكثافة، وامتصاص الماء كعوامل مترابطة.",
    "poor_vitrification": "الأبحاث دعمت دور نضج الطور الزجاجي وتوزيع الفلسبار في اكتمال التزجج الداخلي.",
    "glaze_crazing": "الأعمال الأقرب أكدت أن توافق التمدد الحراري بين الجسم والتزجيج هو العامل الحاسم.",
    "glaze_shivering": "الدراسات القريبة ربطت التقشر بضغط انضغاطي زائد أو عدم اتزان في توافق التزجيج.",
    "glaze_bubbles_pinholes": "الأبحاث ركزت على خروج الغازات وزمن المكوث الحراري ولزوجة التزجيج.",
    "energy_consumption": "الدراسات القريبة ركزت على كفاءة الفرن ومنحنى الحرق وخفض استهلاك الماء والطاقة.",
    "wastewater_turbidity": "الأوراق الأقرب دعمت الفصل والترسيب وإعادة التدوير الداخلي للمياه.",
    "silica_dust": "النتائج القريبة ركزت على التهوية الموضعية والتحكم في الغبار عند المصدر.",
}
CATEGORY_RESEARCH_HINTS = {
    "التزجيج": "الأبحاث الأقرب ركزت على توافق التزجيج، سلوك الغازات، ولزوجة الطلاء.",
    "البيئة والاستدامة": "النتائج ركزت على تقليل الفاقد وإعادة الاستخدام والتحكم عند المصدر.",
}
STAGE_RESEARCH_HINTS = {
    "التجفيف": "الدراسات القريبة دعمت أهمية التحكم في الرطوبة ومعدل التجفيف قبل الحرق.",
    "الحرق والتلبيد": "الأبحاث الأقرب ركزت على نضج الحرق، زمن المكوث، وفروق التمدد الحراري.",
    "التزجيج والتبريد": "الدراسات ركزت على اتزان التزجيج مع الجسم ومسار التبريد النهائي.",
}
ARABIC_HINTS = {
    "drying": "ضبط تدرج الرطوبة وخفض شدة التجفيف قللا من خطر التشقق.",
    "green body": "سلوك الجسم الأخضر قبل الحرق كان عاملًا حاسمًا في جودة القطعة.",
    "thermal shock": "التحكم في التبريد وفروق التمدد الحراري ظهر كعامل أساسي لتقليل الشروخ.",
    "porosity": "رفع كفاءة التلبيد وتحسين الكثافة خفضا المسامية وامتصاص الماء.",
    "water absorption": "خفض امتصاص الماء ارتبط غالبًا برفع نضج الحرق وتحسين الدمك.",
    "glaze": "توافق التزجيج مع الجسم الخزفي وتوزيعه المتجانس كان نقطة متكررة في الأبحاث.",
    "crazing": "اختلاف تمدد التزجيج عن الجسم الخزفي ظهر بوضوح كسبب للشروخ الشعرية.",
    "shivering": "الضغط الزائد في طبقة التزجيج كان من المؤشرات المتكررة في ظاهرة التقشر.",
    "pinholes": "تحسين خروج الغازات وزمن المكوث الحراري ساعد على تقليل الـ pinholes.",
    "blisters": "تحكم أفضل في الاحتراق الداخلي ولزوجة التزجيج خفف الفقاعات والـ blisters.",
    "plasticity": "تحسين اللدونة ارتبط بتوازن أفضل بين الجزء اللدن والحجم الحبيبي والرطوبة.",
    "warping": "تجانس التجفيف والحرق وتخفيف فروق الانكماش كانا عاملين مهمين للحد من الاعوجاج.",
    "energy": "ترشيد منحنى الحرق والعزل الحراري واسترجاع الحرارة ظهر كمسار واضح لخفض الطاقة.",
    "wastewater": "الفصل والترسيب وإعادة تدوير المياه كانت حلولًا متكررة لمعالجة الصرف.",
    "silica": "التهوية الموضعية والترطيب أثناء الطحن وخطط الوقاية المهنية ظهرت بقوة مع السيليكا.",
    "dust": "تقليل الغبار اعتمد على الشفط الموضعي والعزل والعمليات الرطبة أكثر من الحلول المؤقتة.",
}
ISSUE_ENGLISH_EXPANSIONS = {
    "poor_plasticity": ("poor plasticity", "body plasticity", "forming body", "clay plasticity"),
    "lamination_pressing": ("lamination", "pressing cracks", "pressing defect", "air entrapment in pressing"),
    "drying_cracks": ("drying cracks", "drying stress", "green body cracking", "drying behaviour"),
    "drying_warping": ("drying warping", "drying shrinkage", "green body warpage", "non uniform shrinkage"),
    "pre_firing_hydro_deformation": ("hydro deformation", "pre firing deformation", "wet deformation", "shape distortion before firing"),
    "thermal_cracking": ("thermal cracking", "thermal shock", "cooling cracks", "quartz inversion cracking"),
    "high_porosity": ("porosity", "water absorption", "densification", "open porosity in ceramic tiles"),
    "weak_strength": ("mechanical strength", "modulus of rupture", "bending strength", "ceramic strength"),
    "poor_vitrification": ("poor vitrification", "vitrification", "glassy phase", "incomplete sintering"),
    "pyroplastic_deformation": ("pyroplastic deformation", "overfiring deformation", "pyroplasticity", "firing warpage"),
    "glaze_crazing": ("glaze crazing", "glaze cracks", "crazing", "glaze fit"),
    "glaze_shivering": ("glaze shivering", "glaze peeling", "glaze fit compression", "glaze flaking"),
    "glaze_bubbles_pinholes": ("pinholes", "blisters", "glaze bubbles", "gas release in glaze"),
    "color_variation": ("color variation", "color uniformity", "pigment stability", "shade variation"),
    "edge_chipping_residual_stress": ("edge chipping", "residual stress", "finishing defects", "grinding damage"),
    "stain_chemical_resistance": ("stain resistance", "chemical resistance", "surface durability", "glaze resistance"),
    "energy_consumption": ("energy consumption", "kiln efficiency", "fuel consumption", "ceramic tile manufacturing energy"),
    "air_emissions": ("air emissions", "dust emissions", "NOx SO2 emissions", "ceramic plant emissions"),
    "wastewater_turbidity": ("wastewater", "suspended solids", "effluent treatment", "water recycling in ceramic tiles"),
    "solid_waste": ("solid waste", "ceramic waste recycling", "sludge recycling", "scrap reuse"),
    "silica_dust": ("crystalline silica", "silica dust", "occupational exposure", "respirable dust"),
}
FREE_QUERY_EXPANSIONS = {
    "تجفيف": ("drying", "green body", "drying stress"),
    "تشققات": ("cracks", "cracking", "fracture"),
    "حرارية": ("thermal shock", "thermal cracking", "cooling"),
    "مسامية": ("porosity", "water absorption", "densification"),
    "امتصاص": ("water absorption", "porosity"),
    "تزجيج": ("glaze", "glazing", "glaze fit"),
    "شعرية": ("crazing", "glaze cracks"),
    "تقشر": ("shivering", "glaze peeling"),
    "فقاعات": ("blisters", "bubbles", "pinholes"),
    "لون": ("color variation", "pigment stability"),
    "طاقة": ("energy consumption", "kiln efficiency"),
    "انبعاثات": ("air emissions", "particulate emissions", "NOx", "SO2"),
    "مياه": ("wastewater", "water recycling", "suspended solids"),
    "صرف": ("wastewater", "effluent treatment"),
    "نفايات": ("solid waste", "sludge", "waste recycling"),
    "سيليكا": ("crystalline silica", "silica dust", "respirable dust"),
    "غبار": ("dust", "silica dust", "particulate"),
    "لدونة": ("plasticity", "forming body"),
    "كبس": ("pressing", "lamination", "compaction"),
    "اعوجاج": ("warping", "shape distortion", "non uniform shrinkage"),
    "ترخيم": ("pyroplastic deformation", "overfiring deformation"),
    "صلابة": ("mechanical strength", "modulus of rupture"),
}
TERM_TRANSLATIONS = {
    "drying": "التجفيف",
    "green body": "الجسم الأخضر",
    "drying stress": "إجهادات التجفيف",
    "cracks": "التشققات",
    "cracking": "التشقق",
    "thermal shock": "الصدمة الحرارية",
    "cooling": "التبريد",
    "porosity": "المسامية",
    "water absorption": "امتصاص الماء",
    "densification": "زيادة الكثافة",
    "glaze": "التزجيج",
    "glaze fit": "توافق التزجيج",
    "crazing": "الشروخ الشعرية",
    "shivering": "تقشر التزجيج",
    "pinholes": "الـ pinholes",
    "blisters": "الفقاعات المنتفخة",
    "bubbles": "الفقاعات",
    "plasticity": "اللدونة",
    "pressing": "الكبس",
    "lamination": "الانفصال الطبقي",
    "warping": "الاعوجاج",
    "shrinkage": "الانكماش",
    "vitrification": "التزجج الداخلي",
    "sintering": "التلبيد",
    "mullite": "الموليت",
    "mechanical strength": "المقاومة الميكانيكية",
    "modulus of rupture": "مقاومة الكسر",
    "kiln efficiency": "كفاءة الفرن",
    "energy consumption": "استهلاك الطاقة",
    "wastewater": "مياه الصرف",
    "effluent treatment": "معالجة الصرف",
    "solid waste": "النفايات الصلبة",
    "sludge": "الحمأة",
    "silica dust": "غبار السيليكا",
    "crystalline silica": "السيليكا البلورية",
    "respirable dust": "الغبار القابل للاستنشاق",
    "particulate": "الجسيمات العالقة",
    "air emissions": "الانبعاثات الهوائية",
    "no2": "أكاسيد النيتروجين",
    "nox": "أكاسيد النيتروجين",
    "so2": "ثاني أكسيد الكبريت",
    "kaolin": "الكاولين",
    "feldspar": "الفلسبار",
    "quartz": "الكوارتز",
    "ceramic tile": "بلاط السيراميك",
    "porcelain tile": "البورسلين",
}
RESEARCH_ACTIONS = {
    "drying": "خفف شدة التجفيف في البداية واربط السرعة بقياسات الرطوبة لا بالإحساس فقط.",
    "green body": "راقب تجانس الجسم الأخضر قبل الحرق لأن أي تفاوت مبكر يتضخم لاحقًا.",
    "drying stress": "وزع الهواء والحرارة على مراحل لتقليل إجهادات التجفيف عند الحواف.",
    "thermal shock": "بطّئ التبريد في مناطق التحول الحراري لتقليل الشروخ المفاجئة.",
    "porosity": "ارفع جودة الدمك ونضج الحرق لتحسين الكثافة وخفض المسامية.",
    "water absorption": "اقرن قياس امتصاص الماء بمراجعة منحنى الحرق وزمن التثبيت.",
    "glaze": "راجع توافق التمدد الحراري وسماكة التزجيج قبل تغيير الخام مباشرة.",
    "crazing": "قلل فرق التمدد بين الجسم والتزجيج بدل الاكتفاء بترقيع السطح.",
    "shivering": "خفف إجهاد الضغط داخل التزجيج وراجع تركيبه مقارنة بالجسم الخزفي.",
    "pinholes": "حسن خروج الغازات قبل ذروة التزجيج وزد زمن المكوث عند الحاجة.",
    "blisters": "راجع الاحتراق الداخلي ولزوجة الطلاء إذا استمرت الفقاعات المنتفخة.",
    "plasticity": "وازن بين الجزء اللدن والحبيبات والرطوبة بدل رفع الماء وحده.",
    "pressing": "قلل احتباس الهواء وراجع توزيع الضغط والرطوبة قبل الكبس.",
    "warping": "عالج فروق الانكماش بين مناطق القطعة ولا تكتفِ بضبط الحامل أو الرصة.",
    "vitrification": "اربط نسبة الفلسبار ومعدل التسخين بنتيجة التزجج الداخلي الفعلية.",
    "energy consumption": "راجع كفاءة الفرن واسترجاع الحرارة قبل زيادة الوقود مباشرة.",
    "wastewater": "افصل المواد الصلبة مبكرًا وأعد تدوير المياه متى أمكن.",
    "solid waste": "ارجع مسارات الكسر والحمأة للإنتاج بعد ضبط الفرز والتركيب.",
    "silica dust": "ابدأ بالشفط الموضعي والتحكم عند المصدر قبل الاعتماد على معدات الوقاية وحدها.",
    "particulate": "قلل الانبعاثات من المصدر بالاحتواء والشفط والفصل الدوري.",
}


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _normalize_text(text: str) -> str:
    lowered = text.casefold()
    cleaned = re.sub(r"[^\w\s\u0600-\u06FF]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _contains_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def _text_terms(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9\- ]{2,}", text or "")


def _decode_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""

    ordered: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for position in positions:
            ordered.append((position, word))
    ordered.sort(key=lambda item: item[0])
    return " ".join(word for _, word in ordered)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", text)
    return [piece.strip() for piece in pieces if len(piece.strip()) > 40]


def _safe_json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _query_candidate_issue(query_text: str) -> CeramicIssue | None:
    results = find_issues(query=query_text.strip())
    return results[0] if results else None


def _issue_english_terms(issue: CeramicIssue | None) -> list[str]:
    if not issue:
        return []
    terms = [keyword for keyword in issue.keywords if _contains_latin(keyword)]
    return _dedupe_keep_order(terms)


def _query_english_terms(query_text: str) -> list[str]:
    terms = _text_terms(query_text)
    candidate_issue = _query_candidate_issue(query_text)
    terms.extend(_issue_english_terms(candidate_issue))
    return _dedupe_keep_order(terms)


def _search_expression(query_text: str, issue: CeramicIssue | None) -> tuple[str, list[str]]:
    english_terms = _dedupe_keep_order(_issue_english_terms(issue) + _query_english_terms(query_text))

    if not english_terms and query_text.strip():
        english_terms = [query_text.strip()]

    narrowed_terms = english_terms[:5]
    quoted_terms: list[str] = []
    for term in narrowed_terms:
        term = term.strip()
        if not term:
            continue
        quoted_terms.append(f"\"{term}\"" if " " in term else term)

    if not quoted_terms:
        quoted_terms = ["ceramic"]

    anchors = " OR ".join(f"\"{term}\"" if " " in term else term for term in ANCHOR_TERMS)
    body = " OR ".join(quoted_terms)
    return f"({anchors}) AND ({body})", narrowed_terms


def _paper_text(work: dict[str, Any]) -> str:
    keywords = " ".join(keyword.get("display_name", "") for keyword in work.get("keywords", []))
    primary_topic = (work.get("primary_topic") or {}).get("display_name", "")
    primary_location = work.get("primary_location") or {}
    source_name = ((primary_location.get("source") or {}).get("display_name")) or ""
    abstract = _decode_abstract(work.get("abstract_inverted_index"))
    parts = [
        work.get("display_name", ""),
        abstract,
        keywords,
        primary_topic,
        source_name,
    ]
    return _normalize_text(" ".join(parts))


def _score_work(work: dict[str, Any], terms: list[str], issue: CeramicIssue | None) -> float:
    text = _paper_text(work)
    title = _normalize_text(work.get("display_name", ""))
    score = 0.0

    for term in terms:
        normalized_term = _normalize_text(term)
        if not normalized_term:
            continue
        if normalized_term in title:
            score += 10.0
        elif normalized_term in text:
            score += 5.0

    for term in MANUFACTURING_TERMS:
        if term in text:
            score += 1.2

    for term in NOISY_TERMS:
        if term in text:
            score -= 9.0

    if issue:
        if issue.category == "التزجيج" and "glaze" in text:
            score += 5.0
        if issue.stage == "التجفيف" and ("drying" in text or "green body" in text):
            score += 5.0
        if issue.stage == "الحرق والتلبيد" and ("firing" in text or "sintering" in text):
            score += 4.0
        if issue.issue_id == "silica_dust" and ("silica" in text or "dust" in text):
            score += 8.0

    year = work.get("publication_year") or 0
    if year >= 2010:
        score += min((year - 2010) * 0.15, 2.0)

    cited_by_count = work.get("cited_by_count") or 0
    score += min(cited_by_count, 300) / 120.0
    return score


def _paper_url(work: dict[str, Any]) -> str:
    primary_location = work.get("primary_location") or {}
    landing_page = primary_location.get("landing_page_url") or primary_location.get("pdf_url")
    if landing_page:
        return landing_page
    return work.get("id", "")


def _paper_source_name(work: dict[str, Any]) -> str:
    primary_location = work.get("primary_location") or {}
    return ((primary_location.get("source") or {}).get("display_name")) or ""


def _top_evidence_lines(papers: list["OpenAlexPaper"], issue: CeramicIssue | None) -> list[str]:
    lines: list[str] = []
    keyword_hints = []

    if issue:
        issue_hint = ISSUE_RESEARCH_HINTS.get(issue.issue_id)
        if issue_hint:
            lines.append(issue_hint)
        else:
            category_hint = CATEGORY_RESEARCH_HINTS.get(issue.category)
            stage_hint = STAGE_RESEARCH_HINTS.get(issue.stage)
            if category_hint:
                lines.append(category_hint)
            if stage_hint and stage_hint not in lines:
                lines.append(stage_hint)

    for paper in papers[:3]:
        for keyword in paper.keywords:
            hint = ARABIC_HINTS.get(keyword.casefold())
            if hint:
                keyword_hints.append(hint)

    lines.extend(_dedupe_keep_order(keyword_hints)[:2])

    for paper in papers[:3]:
        if paper.source_name:
            lines.append(
                f"{paper.title} ({paper.year or 'بدون سنة'}) ظهر ضمن مصدر بحثي: {paper.source_name}."
            )
        elif paper.topic:
            lines.append(
                f"{paper.title} ({paper.year or 'بدون سنة'}) دعم محور: {paper.topic}."
            )
        else:
            lines.append(f"{paper.title} ({paper.year or 'بدون سنة'}) كان ضمن أقرب النتائج.")

    if issue and not lines:
        lines.append(
            "نتائج OpenAlex جاءت داعمة للتشخيص المحلي أكثر من كونها بديلًا له، لذا اعتمدت الخلاصة على السبب والحل الأقرب للمشكلة."
        )

    return _dedupe_keep_order(lines)[:3]


def _fallback_actions(query_text: str, candidate_issue: CeramicIssue | None) -> list[str]:
    if candidate_issue:
        return list(candidate_issue.solutions[:3])

    query = _normalize_text(query_text)
    if "dry" in query or "تجفيف" in query:
        return [
            "خفف معدل التجفيف وقسمه على مراحل بدل الصدمة الحرارية أو الرطوبية.",
            "راجع توزيع الرطوبة داخل الجسم قبل النقل للمرحلة التالية.",
            "افحص التدرج الحبيبي والتجانس قبل التشكيل.",
        ]
    if "porosity" in query or "مسامية" in query:
        return [
            "ارفع جودة الدمك قبل الحرق وراجع التدرج الحبيبي.",
            "تحقق من نضج الحرق ووقت المكوث الحراري.",
            "راجع نسبة الفلسبار والمواد المساعدة على التلبيد.",
        ]
    if "glaze" in query or "تزجيج" in query:
        return [
            "راجع توافق التمدد الحراري بين التزجيج والجسم الخزفي.",
            "اضبط سماكة التزجيج وتجانس تطبيقه.",
            "تأكد من اكتمال خروج الغازات قبل ذروة التزجيج.",
        ]
    if "silica" in query or "سيليكا" in query or "غبار" in query:
        return [
            "فعّل شفطًا موضعيًا مباشرًا عند الطحن والمناولة.",
            "حوّل العمليات الجافة لعمليات رطبة قدر الإمكان.",
            "اربط الوقاية الشخصية بقياس فعلي للتعرض وليس بالتقدير فقط.",
        ]
    return [
        "حدد المرحلة التي يظهر فيها العيب بدقة قبل أي تعديل كبير.",
        "راجع آخر تغيير في الخامة أو المنحنى الحراري أو الرطوبة.",
        "نفذ تعديلًا واحدًا في كل مرة ثم قارن النتيجة بقياس واضح.",
    ]


def _strip_openalex_id(value: str) -> str:
    return value.rsplit("/", 1)[-1].strip()


def _issue_expansion_terms(issue: CeramicIssue | None) -> list[str]:
    if not issue:
        return []
    terms = list(ISSUE_ENGLISH_EXPANSIONS.get(issue.issue_id, ()))
    terms.extend(issue.keywords)
    return _dedupe_keep_order(terms)


def _query_expansion_terms(query_text: str, issue: CeramicIssue | None) -> list[str]:
    normalized_query = _normalize_text(query_text)
    expanded: list[str] = []
    expanded.extend(_issue_expansion_terms(issue))

    for arabic_term, english_terms in FREE_QUERY_EXPANSIONS.items():
        if arabic_term in query_text:
            expanded.extend(english_terms)

    for latin_term in _text_terms(query_text):
        expanded.append(latin_term)

    if query_text.strip():
        expanded.append(query_text.strip())

    return _dedupe_keep_order(expanded)


def _build_search_bundle(query_text: str, issue: CeramicIssue | None) -> dict[str, Any]:
    expanded_terms = _query_expansion_terms(query_text, issue)
    english_terms = [term for term in expanded_terms if _contains_latin(term)]
    phrase_terms = [term for term in english_terms if " " in term]
    atomic_terms = [term for term in english_terms if " " not in term]

    if not english_terms and query_text.strip():
        english_terms = [query_text.strip()]

    boolean_terms = []
    for term in phrase_terms[:6] + atomic_terms[:6]:
        term = term.strip()
        if not term:
            continue
        boolean_terms.append(f"\"{term}\"" if " " in term else term)

    if not boolean_terms:
        boolean_terms = ["ceramic"]

    anchors = " OR ".join(f"\"{term}\"" if " " in term else term for term in ANCHOR_TERMS)
    boolean_query = f"({anchors}) AND ({' OR '.join(boolean_terms)})"

    exact_queries = _dedupe_keep_order(phrase_terms[:3] + atomic_terms[:2])

    semantic_bits = phrase_terms[:4] + atomic_terms[:4]
    semantic_query = "ceramic manufacturing problem: " + ", ".join(semantic_bits or [query_text.strip() or "ceramic defect"])

    return {
        "boolean_query": boolean_query,
        "exact_queries": exact_queries,
        "semantic_query": semantic_query.strip(),
        "matched_terms": tuple(_dedupe_keep_order(phrase_terms + atomic_terms)[:8]),
    }


def _local_issue_match_score(query_text: str, issue: CeramicIssue) -> float:
    normalized_query = _normalize_text(query_text)
    if not normalized_query:
        return 0.0

    title = _normalize_text(issue.title)
    symptom = _normalize_text(issue.symptom)
    searchable = " ".join(
        _normalize_text(part)
        for part in [issue.title, issue.symptom, *issue.keywords, *_issue_expansion_terms(issue)]
    )

    score = 0.0
    if normalized_query in title:
        score += 12.0
    if title.startswith(normalized_query):
        score += 8.0
    if normalized_query in symptom:
        score += 4.0
    if normalized_query in searchable:
        score += 3.0

    for token in normalized_query.split():
        if token and token in searchable:
            score += 1.4

    return score


def _translate_terms(terms: list[str] | tuple[str, ...], limit: int = 4) -> list[str]:
    translated: list[str] = []
    for term in terms:
        normalized_term = term.casefold()
        for english_term, arabic_term in TERM_TRANSLATIONS.items():
            if english_term in normalized_term:
                translated.append(arabic_term)
    return _dedupe_keep_order(translated)[:limit]


def _has_context_signal(work: dict[str, Any], issue: CeramicIssue | None, query_text: str) -> bool:
    text = _paper_text(work)
    if any(term in text for term in CORE_CERAMIC_SIGNAL_TERMS):
        return True

    if issue and issue.issue_id in {"energy_consumption", "air_emissions", "wastewater_turbidity", "solid_waste", "silica_dust"}:
        environmental_terms = {"industrial", "manufacturing", "factory", "plant", "dust", "silica", "emissions", "wastewater", "sludge", "kiln"}
        if any(term in text for term in environmental_terms):
            return True

    if "سيليكا" in query_text or "غبار" in query_text:
        return "silica" in text or "dust" in text

    return False


@dataclass(frozen=True)
class OpenAlexPaper:
    title: str
    year: int | None
    url: str
    topic: str
    source_name: str
    abstract: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class OpenAlexResearchResult:
    search_expression: str
    matched_terms: tuple[str, ...]
    papers: tuple[OpenAlexPaper, ...]
    error: str | None = None


class OpenAlexClient:
    def __init__(self, config_path: Path) -> None:
        config = _safe_json_load(config_path)
        self.api_key = (
            os.getenv("OPENALEX_API_KEY")
            or str(config.get("api_key", "")).strip()
        )
        self.email = (
            os.getenv("OPENALEX_EMAIL")
            or str(config.get("email", "")).strip()
        )
        self.per_page = max(4, min(int(config.get("per_page", 8) or 8), 12))
        self.timeout_seconds = max(
            8,
            min(int(config.get("timeout_seconds", 15) or 15), 40),
        )

    def search(self, query_text: str, issue: CeramicIssue | None) -> OpenAlexResearchResult:
        search_expression, matched_terms = _search_expression(query_text, issue)
        params = {
            "search": search_expression,
            "per-page": str(self.per_page),
            "select": ",".join(
                [
                    "id",
                    "display_name",
                    "publication_year",
                    "cited_by_count",
                    "primary_location",
                    "primary_topic",
                    "keywords",
                    "abstract_inverted_index",
                ]
            ),
        }
        if self.email:
            params["mailto"] = self.email

        request_url = f"{OPENALEX_URL}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            request_url,
            headers={
                "User-Agent": "CeramicSolutionsStudio-OpenAlex/2026",
                **(
                    {"Authorization": f"Bearer {self.api_key}"}
                    if self.api_key
                    else {}
                ),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                message = (
                    "OpenAlex رفض الطلب. إذا أردت استخدامًا مستمرًا ضع المفتاح في "
                    "openalex_config.json أو في المتغير OPENALEX_API_KEY."
                )
            elif error.code == 429:
                message = "OpenAlex طلب إبطاء الاستعلامات. حاول مرة أخرى بعد قليل."
            else:
                message = f"تعذر جلب OpenAlex (HTTP {error.code})."
            return OpenAlexResearchResult(search_expression, tuple(matched_terms), tuple(), message)
        except (OSError, TimeoutError):
            return OpenAlexResearchResult(
                search_expression,
                tuple(matched_terms),
                tuple(),
                "انقطع الاتصال بـ OpenAlex أو انتهت مهلة الطلب.",
            )

        works = payload.get("results", [])
        ranked = sorted(
            works,
            key=lambda work: _score_work(work, matched_terms, issue),
            reverse=True,
        )
        papers: list[OpenAlexPaper] = []
        for work in ranked[:5]:
            papers.append(
                OpenAlexPaper(
                    title=work.get("display_name", "بدون عنوان"),
                    year=work.get("publication_year"),
                    url=_paper_url(work),
                    topic=(work.get("primary_topic") or {}).get("display_name", ""),
                    source_name=_paper_source_name(work),
                    abstract=_decode_abstract(work.get("abstract_inverted_index")),
                    keywords=tuple(
                        keyword.get("display_name", "")
                        for keyword in work.get("keywords", [])
                        if keyword.get("display_name")
                    ),
                )
            )
        return OpenAlexResearchResult(search_expression, tuple(matched_terms), tuple(papers))


class OpenAlexCeramicSolutionsStudio(BaseStudio):
    def __init__(self, root: tk.Tk) -> None:
        self._openalex_client = OpenAlexClient(CONFIG_PATH)
        self._openalex_cache: dict[str, OpenAlexResearchResult] = {}
        self._openalex_request_token = 0
        self._openalex_pending_updates: queue.SimpleQueue[tuple[int, CeramicIssue | None, str, OpenAlexResearchResult, bool]] = queue.SimpleQueue()
        super().__init__(root)
        self.root.after(150, self._drain_openalex_updates)

    def show_issue(self, issue: CeramicIssue, rerender: bool = True) -> None:
        super().show_issue(issue, rerender=rerender)
        self._start_openalex_lookup(issue=issue, query_text=self.search_var.get().strip())

    def run_search(self, _event=None) -> None:
        super().run_search(_event=_event)
        query_text = self.search_var.get().strip()
        if query_text and not self.current_results:
            candidate_issue = _query_candidate_issue(query_text)
            self._start_openalex_lookup(issue=candidate_issue, query_text=query_text, query_only=True)

    def _start_openalex_lookup(
        self,
        issue: CeramicIssue | None,
        query_text: str,
        query_only: bool = False,
    ) -> None:
        if not issue and not query_text.strip():
            return

        cache_key = f"{issue.issue_id if issue else 'query'}::{query_text.strip().casefold()}"
        self._openalex_request_token += 1
        request_token = self._openalex_request_token

        if issue:
            self._write_text(
                self.reference_text,
                self._build_quick_summary(issue) + "\n\nجاري إضافة دعم OpenAlex للمشكلة الحالية...",
            )
            self._set_status(f"جاري دعم التشخيص من OpenAlex: {issue.title}")
        else:
            self._set_current_issue_title(f"تحليل OpenAlex: {query_text}")
            self._write_text(
                self.detail_text,
                "جاري البحث في OpenAlex عن أقرب أوراق للمشكلة المطلوبة...",
            )
            self._write_text(
                self.reference_text,
                "جاري تجهيز خلاصة مختصرة من OpenAlex بدون حشو...",
            )
            self._set_status(f"جاري تحليل عبارة البحث عبر OpenAlex: {query_text}")

        cached_result = self._openalex_cache.get(cache_key)
        if cached_result is not None:
            self.root.after(
                0,
                lambda: self._apply_openalex_result(
                    request_token=request_token,
                    issue=issue,
                    query_text=query_text,
                    result=cached_result,
                    query_only=query_only,
                ),
            )
            return

        worker = threading.Thread(
            target=self._lookup_worker,
            args=(request_token, cache_key, issue, query_text, query_only),
            daemon=True,
        )
        worker.start()

    def _lookup_worker(
        self,
        request_token: int,
        cache_key: str,
        issue: CeramicIssue | None,
        query_text: str,
        query_only: bool,
    ) -> None:
        result = self._openalex_client.search(query_text=query_text, issue=issue)
        self._openalex_cache[cache_key] = result
        self._openalex_pending_updates.put(
            (request_token, issue, query_text, result, query_only)
        )

    def _drain_openalex_updates(self) -> None:
        try:
            while True:
                request_token, issue, query_text, result, query_only = self._openalex_pending_updates.get_nowait()
                self._apply_openalex_result(
                    request_token=request_token,
                    issue=issue,
                    query_text=query_text,
                    result=result,
                    query_only=query_only,
                )
        except queue.Empty:
            pass

        try:
            self.root.after(150, self._drain_openalex_updates)
        except tk.TclError:
            return

    def _apply_openalex_result(
        self,
        request_token: int,
        issue: CeramicIssue | None,
        query_text: str,
        result: OpenAlexResearchResult,
        query_only: bool,
    ) -> None:
        if request_token != self._openalex_request_token:
            return

        if issue:
            detail = self._build_issue_detail(issue, result)
            summary = self._build_issue_reference_summary(issue, result)
            self._write_text(self.detail_text, detail)
            self._write_text(self.reference_text, summary)
            suffix = "مع دعم OpenAlex" if result.papers else "مع الخلاصة المحلية فقط"
            self._set_status(f"التشخيص الحالي: {issue.title} - {suffix}")
            return

        detail = self._build_query_only_detail(query_text, result)
        summary = self._build_query_only_summary(query_text, result)
        self._write_text(self.detail_text, detail)
        self._write_text(self.reference_text, summary)
        if result.papers:
            self._set_status(f"تم إعداد خلاصة OpenAlex لعبارة: {query_text}")
        else:
            self._set_status(f"تعذر دعم العبارة بحثيًا من OpenAlex: {query_text}")

    def _build_quick_summary(self, issue: CeramicIssue) -> str:
        lines = [
            f"ملخص سريع: {issue.title}",
            "",
            f"العرض: {issue.symptom}",
            "",
            "الأسباب:",
        ]
        lines.extend(f"- {cause}" for cause in issue.causes[:3])
        return "\n".join(lines)


class OpenAlexCeramicSolutionsStudio(BaseStudio):
    def __init__(self, root: tk.Tk) -> None:
        self._openalex_client = OpenAlexClient(CONFIG_PATH)
        self._openalex_cache: dict[str, OpenAlexResearchResult] = {}
        self._openalex_request_token = 0
        self._openalex_pending_updates: queue.SimpleQueue[tuple[int, CeramicIssue | None, str, OpenAlexResearchResult, bool]] = queue.SimpleQueue()
        self._suggestion_cache: dict[str, list[SearchSuggestion]] = {}
        self._suggestion_request_token = 0
        self._suggestion_pending_updates: queue.SimpleQueue[tuple[int, str, list[SearchSuggestion]]] = queue.SimpleQueue()
        self._suggestion_after_id: str | None = None
        self._suspend_suggestion_events = False
        self._visible_suggestions: list[SearchSuggestion] = []
        self._search_entry: tk.Entry | None = None
        self._suggestion_popup: tk.Toplevel | None = None
        self._suggestion_listbox: tk.Listbox | None = None
        super().__init__(root)
        self._setup_autocomplete_ui()
        self.root.after(120, self._poll_async_updates)

    def _setup_autocomplete_ui(self) -> None:
        self._search_entry = self._find_first_widget(self.root, "Entry")
        if self._search_entry is None:
            return

        self._suggestion_popup = tk.Toplevel(self.root)
        self._suggestion_popup.withdraw()
        self._suggestion_popup.overrideredirect(True)
        self._suggestion_popup.transient(self.root)

        self._suggestion_listbox = tk.Listbox(
            self._suggestion_popup,
            height=8,
            activestyle="none",
            font=("Segoe UI", 11),
        )
        self._suggestion_listbox.pack(fill="both", expand=True)
        self._suggestion_listbox.bind("<Return>", self._handle_listbox_activate)
        self._suggestion_listbox.bind("<ButtonRelease-1>", self._handle_listbox_activate)

        self.search_var.trace_add("write", self._on_query_text_changed)
        self._search_entry.bind("<Down>", self._move_focus_to_suggestions)
        self._search_entry.bind("<FocusOut>", self._hide_suggestions_later)
        self._search_entry.bind("<Escape>", lambda _event: self._hide_suggestions())
        self.root.bind("<Button-1>", self._handle_global_click, add="+")

    def _find_first_widget(self, widget: tk.Widget, class_name: str) -> tk.Widget | None:
        if widget.winfo_class() == class_name:
            return widget
        for child in widget.winfo_children():
            found = self._find_first_widget(child, class_name)
            if found is not None:
                return found
        return None

    def _on_query_text_changed(self, *_args: object) -> None:
        if self._suspend_suggestion_events:
            return
        if self._suggestion_after_id:
            try:
                self.root.after_cancel(self._suggestion_after_id)
            except tk.TclError:
                pass
        self._suggestion_after_id = self.root.after(180, self._refresh_suggestions)

    def _refresh_suggestions(self) -> None:
        self._suggestion_after_id = None
        query_text = self.search_var.get().strip()
        if not query_text:
            self._hide_suggestions()
            return

        local_suggestions = _build_local_suggestions(query_text)
        remote_suggestions = self._suggestion_cache.get(query_text.casefold(), [])
        merged = self._merge_suggestions(local_suggestions, remote_suggestions)
        if merged:
            self._show_suggestions(merged)
        else:
            self._hide_suggestions()

        if query_text.casefold() in self._suggestion_cache:
            return

        candidate_issue = _query_candidate_issue(query_text)
        if len(query_text) < REMOTE_AUTOCOMPLETE_MIN_CHARS and candidate_issue is None:
            return

        self._suggestion_request_token += 1
        request_token = self._suggestion_request_token
        threading.Thread(
            target=self._suggestion_worker,
            args=(request_token, query_text, candidate_issue),
            daemon=True,
        ).start()

    def _suggestion_worker(self, request_token: int, query_text: str, candidate_issue: CeramicIssue | None) -> None:
        suggestions = self._openalex_client.autocomplete(query_text, candidate_issue)
        self._suggestion_pending_updates.put((request_token, query_text, suggestions))

    def _merge_suggestions(self, local: list[SearchSuggestion], remote: list[SearchSuggestion]) -> list[SearchSuggestion]:
        merged: list[SearchSuggestion] = []
        seen: set[str] = set()
        for suggestion in local + remote:
            key = suggestion.value.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(suggestion)
        return merged[:8]

    def _show_suggestions(self, suggestions: list[SearchSuggestion]) -> None:
        if self._search_entry is None or self._suggestion_popup is None or self._suggestion_listbox is None:
            return
        if not suggestions:
            self._hide_suggestions()
            return

        self._visible_suggestions = suggestions
        self._suggestion_listbox.delete(0, tk.END)
        for suggestion in suggestions:
            prefix = "مشكلة" if suggestion.source == "local" else "بحث"
            self._suggestion_listbox.insert(tk.END, f"{prefix}: {suggestion.label} - {suggestion.subtitle}")

        width = max(self._search_entry.winfo_width(), 520)
        height = min(len(suggestions), 8) * 26 + 6
        x = self._search_entry.winfo_rootx()
        y = self._search_entry.winfo_rooty() + self._search_entry.winfo_height() + 2
        self._suggestion_popup.geometry(f"{width}x{height}+{x}+{y}")
        self._suggestion_popup.deiconify()
        self._suggestion_popup.lift()

    def _hide_suggestions(self) -> None:
        self._visible_suggestions = []
        if self._suggestion_popup is not None:
            try:
                self._suggestion_popup.withdraw()
            except tk.TclError:
                return

    def _hide_suggestions_later(self, _event=None) -> None:
        self.root.after(150, self._hide_suggestions)

    def _move_focus_to_suggestions(self, _event=None) -> str | None:
        if not self._visible_suggestions or self._suggestion_listbox is None:
            return None
        self._suggestion_listbox.focus_set()
        self._suggestion_listbox.selection_clear(0, tk.END)
        self._suggestion_listbox.selection_set(0)
        self._suggestion_listbox.activate(0)
        return "break"

    def _handle_listbox_activate(self, _event=None) -> str | None:
        if self._suggestion_listbox is None:
            return None
        selection = self._suggestion_listbox.curselection()
        if not selection:
            return None
        suggestion = self._visible_suggestions[selection[0]]
        self._apply_suggestion(suggestion)
        return "break"

    def _apply_suggestion(self, suggestion: SearchSuggestion) -> None:
        self._suspend_suggestion_events = True
        try:
            self.search_var.set(suggestion.value)
        finally:
            self._suspend_suggestion_events = False
        self._hide_suggestions()
        self.run_search()

    def _handle_global_click(self, event) -> None:
        if event.widget in {self._search_entry, self._suggestion_listbox}:
            return
        self._hide_suggestions()

    def show_issue(self, issue: CeramicIssue, rerender: bool = True) -> None:
        self._hide_suggestions()
        super().show_issue(issue, rerender=rerender)
        self._start_openalex_lookup(issue=issue, query_text=self.search_var.get().strip())

    def run_search(self, _event=None) -> None:
        self._hide_suggestions()
        super().run_search(_event=_event)
        query_text = self.search_var.get().strip()
        if query_text and not self.current_results:
            candidate_issue = _query_candidate_issue(query_text)
            self._start_openalex_lookup(issue=candidate_issue, query_text=query_text, query_only=True)

    def _start_openalex_lookup(self, issue: CeramicIssue | None, query_text: str, query_only: bool = False) -> None:
        if not issue and not query_text.strip():
            return

        cache_key = f"{issue.issue_id if issue else 'query'}::{query_text.strip().casefold()}"
        self._openalex_request_token += 1
        request_token = self._openalex_request_token

        if issue and not query_only:
            self._write_text(
                self.reference_text,
                self._build_quick_summary(issue) + "\n\nجاري تشغيل بحث OpenAlex الهجين للمشكلة الحالية...",
            )
            self._set_status(f"جاري تحليل المشكلة عبر OpenAlex: {issue.title}")
        else:
            self._set_current_issue_title(f"تحليل OpenAlex: {query_text}")
            self._write_text(self.detail_text, "جاري تنفيذ بحث هجين على OpenAlex مع توسيع المصطلحات...")
            self._write_text(self.reference_text, "جاري تجهيز حلول كثيرة مختصرة من الأبحاث...")
            self._set_status(f"جاري تحليل عبارة البحث عبر OpenAlex: {query_text}")

        cached_result = self._openalex_cache.get(cache_key)
        if cached_result is not None:
            self._apply_openalex_result(request_token, issue, query_text, cached_result, query_only)
            return

        threading.Thread(
            target=self._lookup_worker,
            args=(request_token, cache_key, issue, query_text, query_only),
            daemon=True,
        ).start()

    def _lookup_worker(
        self,
        request_token: int,
        cache_key: str,
        issue: CeramicIssue | None,
        query_text: str,
        query_only: bool,
    ) -> None:
        result = self._openalex_client.search(query_text=query_text, issue=issue)
        self._openalex_cache[cache_key] = result
        self._openalex_pending_updates.put((request_token, issue, query_text, result, query_only))

    def _poll_async_updates(self) -> None:
        try:
            while True:
                request_token, query_text, suggestions = self._suggestion_pending_updates.get_nowait()
                if request_token == self._suggestion_request_token:
                    self._suggestion_cache[query_text.casefold()] = suggestions
                    if self.search_var.get().strip().casefold() == query_text.casefold():
                        merged = self._merge_suggestions(_build_local_suggestions(query_text), suggestions)
                        self._show_suggestions(merged)
        except queue.Empty:
            pass

        try:
            while True:
                request_token, issue, query_text, result, query_only = self._openalex_pending_updates.get_nowait()
                self._apply_openalex_result(request_token, issue, query_text, result, query_only)
        except queue.Empty:
            pass

        try:
            self.root.after(120, self._poll_async_updates)
        except tk.TclError:
            return

    def _apply_openalex_result(
        self,
        request_token: int,
        issue: CeramicIssue | None,
        query_text: str,
        result: OpenAlexResearchResult,
        query_only: bool,
    ) -> None:
        if request_token != self._openalex_request_token:
            return

        if issue and not query_only:
            self._write_text(self.detail_text, self._build_issue_detail(issue, result))
            self._write_text(self.reference_text, self._build_issue_reference_summary(issue, result))
            suffix = result.confidence_label if result.papers else "بدون دعم بحثي كاف"
            self._set_status(f"التشخيص الحالي: {issue.title} - ثقة {suffix}")
            return

        self._write_text(self.detail_text, self._build_query_only_detail(query_text, result))
        self._write_text(self.reference_text, self._build_query_only_summary(query_text, result))
        if result.papers:
            self._set_status(f"تم إعداد تحليل OpenAlex لعبارة: {query_text} - ثقة {result.confidence_label}")
        else:
            self._set_status(f"تعذر دعم العبارة بحثيًا من OpenAlex: {query_text}")

    def _build_quick_summary(self, issue: CeramicIssue) -> str:
        lines = [
            f"ملخص سريع: {issue.title}",
            "",
            f"العرض: {issue.symptom}",
            f"النوع: {issue.category} | المرحلة: {issue.stage}",
            "",
            "الأسباب الأقرب:",
        ]
        lines.extend(f"- {cause}" for cause in issue.causes[:3])
        return "\n".join(lines)

    def _build_issue_detail(self, issue: CeramicIssue, result: OpenAlexResearchResult) -> str:
        evidence_lines = _top_evidence_lines(list(result.papers), issue)
        lines = [
            issue.title,
            "",
            f"نوع المشكلة: {issue.category}",
            f"المرحلة: {issue.stage}",
            f"التشخيص الأقرب: {issue.symptom}",
            f"ثقة OpenAlex: {result.confidence_label} ({int(result.confidence_score)}/100)",
            "",
            "لماذا تحدث غالبًا؟",
        ]
        lines.extend(f"- {cause}" for cause in issue.causes[:4])
        lines.extend(["", "حلول كثيرة ومباشرة:"])
        lines.extend(f"- {point}" for point in result.solution_points[:9])

        if evidence_lines:
            lines.extend(["", "ما الذي دعمه OpenAlex؟"])
            lines.extend(f"- {line}" for line in evidence_lines)

        if result.article_summaries:
            lines.extend(["", "اختصار المقالات:"])
            for index, summary in enumerate(result.article_summaries[:4], start=1):
                lines.append(f"{index}. {summary}")

        if result.error and not result.papers:
            lines.extend(["", f"ملاحظة OpenAlex: {result.error}"])

        return "\n".join(lines)

    def _build_issue_reference_summary(self, issue: CeramicIssue, result: OpenAlexResearchResult) -> str:
        lines = [
            f"ملخص سريع: {issue.title}",
            "",
            f"النوع: {issue.category} | المرحلة: {issue.stage}",
            f"الثقة: {result.confidence_label} ({int(result.confidence_score)}/100)",
            "",
            "أقوى الحلول:",
        ]
        lines.extend(f"- {point}" for point in result.solution_points[:4])

        if result.strategy_labels:
            lines.extend(["", f"استراتيجيات البحث: {', '.join(result.strategy_labels[:4])}"])

        if result.papers:
            lines.extend(["", "أقوى الأوراق المختصرة:"])
            for index, paper in enumerate(result.papers[:4], start=1):
                line = f"{index}. {paper.title}"
                if paper.year:
                    line += f" ({paper.year})"
                lines.append(line)
                lines.append(f"   الخلاصة: {paper.summary}")
                if paper.source_name:
                    lines.append(f"   المصدر: {paper.source_name}")
                lines.append(f"   الاستشهادات: {paper.cited_by_count}")
                if paper.url:
                    lines.append(f"   الرابط: {paper.url}")
        elif result.error:
            lines.extend(["", f"حالة OpenAlex: {result.error}"])

        if result.matched_terms:
            lines.extend(["", f"مصطلحات البحث: {', '.join(result.matched_terms[:6])}"])

        return "\n".join(lines)

    def _build_query_only_detail(self, query_text: str, result: OpenAlexResearchResult) -> str:
        candidate_issue = _query_candidate_issue(query_text)
        lines = [f"تحليل OpenAlex لعبارة: {query_text}", ""]

        if candidate_issue:
            lines.extend(
                [
                    f"أقرب نوع مشكلة: {candidate_issue.title}",
                    f"التصنيف: {candidate_issue.category}",
                    f"المرحلة الأقرب: {candidate_issue.stage}",
                    f"ثقة OpenAlex: {result.confidence_label} ({int(result.confidence_score)}/100)",
                    "",
                    "السبب الأقرب:",
                ]
            )
            lines.extend(f"- {cause}" for cause in candidate_issue.causes[:4])
        else:
            lines.extend(
                [
                    "أقرب نوع مشكلة: تحليل بحثي مباشر لعبارة المستخدم.",
                    f"ثقة OpenAlex: {result.confidence_label} ({int(result.confidence_score)}/100)",
                    "",
                    "ما الذي أراجعه أولًا؟",
                ]
            )

        lines.extend(["", "حلول كثيرة ومختصرة:"])
        lines.extend(f"- {point}" for point in result.solution_points[:9])

        if result.article_summaries:
            lines.extend(["", "اختصار المقالات:"])
            for index, summary in enumerate(result.article_summaries[:4], start=1):
                lines.append(f"{index}. {summary}")

        if result.error and not result.papers:
            lines.extend(["", f"ملاحظة OpenAlex: {result.error}"])

        return "\n".join(lines)

    def _build_query_only_summary(self, query_text: str, result: OpenAlexResearchResult) -> str:
        lines = [
            f"خلاصة مختصرة لعبارة: {query_text}",
            "",
            f"الثقة: {result.confidence_label} ({int(result.confidence_score)}/100)",
            "",
            "أقوى الإجراءات:",
        ]
        lines.extend(f"- {point}" for point in result.solution_points[:4])

        if result.papers:
            lines.extend(["", "أفضل المقالات بعد الاختصار:"])
            for index, paper in enumerate(result.papers[:4], start=1):
                line = f"{index}. {paper.title}"
                if paper.year:
                    line += f" ({paper.year})"
                lines.append(line)
                lines.append(f"   الخلاصة: {paper.summary}")
                lines.append(f"   الاستشهادات: {paper.cited_by_count}")
                if paper.url:
                    lines.append(f"   الرابط: {paper.url}")
        elif result.error:
            lines.extend(["", f"حالة OpenAlex: {result.error}"])

        if result.strategy_labels:
            lines.extend(["", f"بحث OpenAlex استخدم: {', '.join(result.strategy_labels[:4])}"])

        if result.matched_terms:
            lines.extend(["", f"الاستعلام الأوسع: {result.search_expression}"])

        return "\n".join(lines)


@dataclass(frozen=True)
class SearchSuggestion:
    label: str
    value: str
    subtitle: str
    source: str


@dataclass(frozen=True)
class OpenAlexPaper:
    paper_id: str
    title: str
    year: int | None
    url: str
    topic: str
    source_name: str
    abstract: str
    keywords: tuple[str, ...]
    cited_by_count: int
    relevance_score: float
    is_open_access: bool
    summary: str
    action_points: tuple[str, ...]
    origins: tuple[str, ...]


@dataclass(frozen=True)
class OpenAlexResearchResult:
    search_expression: str
    matched_terms: tuple[str, ...]
    papers: tuple[OpenAlexPaper, ...]
    strategy_labels: tuple[str, ...]
    confidence_label: str
    confidence_score: float
    solution_points: tuple[str, ...]
    article_summaries: tuple[str, ...]
    error: str | None = None


def _build_local_suggestions(query_text: str) -> list[SearchSuggestion]:
    scored_matches: list[tuple[float, SearchSuggestion]] = []
    for issue in all_issues():
        score = _local_issue_match_score(query_text, issue)
        if score <= 0:
            continue
        scored_matches.append(
            (
                score,
                SearchSuggestion(
                    label=issue.title,
                    value=issue.title,
                    subtitle=f"{issue.category} | {issue.stage}",
                    source="local",
                ),
            )
        )

    scored_matches.sort(key=lambda item: item[0], reverse=True)
    return [suggestion for _, suggestion in scored_matches[:LOCAL_SUGGESTION_LIMIT]]


class OpenAlexClient:
    def __init__(self, config_path: Path) -> None:
        config = _safe_json_load(config_path)
        self.api_key = os.getenv("OPENALEX_API_KEY") or str(config.get("api_key", "")).strip()
        self.email = os.getenv("OPENALEX_EMAIL") or str(config.get("email", "")).strip()
        self.per_page = max(5, min(int(config.get("per_page", 8) or 8), 12))
        self.timeout_seconds = max(8, min(int(config.get("timeout_seconds", 15) or 15), 40))
        self.enable_semantic = bool(config.get("enable_semantic", True))
        self._last_semantic_request_at = 0.0

    def _request_json(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query_params = dict(params or {})
        if self.email:
            query_params.setdefault("mailto", self.email)
        if self.api_key:
            query_params.setdefault("api_key", self.api_key)

        request_url = url
        if query_params:
            separator = "&" if "?" in request_url else "?"
            request_url = f"{request_url}{separator}{urllib.parse.urlencode(query_params)}"

        request = urllib.request.Request(
            request_url,
            headers={"User-Agent": "CeramicSolutionsStudio-OpenAlex/2026"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)

    def _query_works(self, params: dict[str, str]) -> tuple[list[dict[str, Any]], str | None]:
        try:
            payload = self._request_json(OPENALEX_URL, params)
            return payload.get("results", []), None
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                return [], "OpenAlex رفض الطلب. أضف api_key داخل openalex_config.json لو أردت استخدامًا أطول."
            if error.code == 429:
                return [], "OpenAlex طلب تهدئة عدد الطلبات. خففت الحمل وأكملت بأفضل ما توفر."
            if error.code >= 500:
                return [], f"OpenAlex أعاد خطأ داخليًا مؤقتًا (HTTP {error.code})."
            return [], f"تعذر جلب OpenAlex (HTTP {error.code})."
        except (OSError, TimeoutError):
            return [], "انقطع الاتصال بـ OpenAlex أو انتهت مهلة الطلب."

    def _query_related_works(self, related_ids: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        if not related_ids:
            return [], None

        filter_value = f"openalex_id:{'|'.join(related_ids)},{DEFAULT_OPENALEX_FILTER}"
        return self._query_works({"filter": filter_value, "per-page": str(len(related_ids))})

    def _merge_work(self, collected: dict[str, dict[str, Any]], work: dict[str, Any], origin: str) -> None:
        paper_id = _strip_openalex_id(str(work.get("id", "")))
        if not paper_id:
            return

        existing = collected.get(paper_id)
        if existing is None:
            merged = dict(work)
            merged["_origins"] = {origin}
            collected[paper_id] = merged
            return

        existing.setdefault("_origins", set()).add(origin)
        if (work.get("relevance_score") or 0.0) > (existing.get("relevance_score") or 0.0):
            for key, value in work.items():
                if value not in (None, "", [], {}):
                    existing[key] = value

    def _composite_score(self, work: dict[str, Any], matched_terms: tuple[str, ...], issue: CeramicIssue | None) -> float:
        origins = work.get("_origins") or set()
        score = _score_work(work, list(matched_terms), issue)
        score += min(float(work.get("relevance_score") or 0.0) / 120.0, 10.0)
        score += min(int(work.get("cited_by_count") or 0), 400) / 90.0
        if (work.get("open_access") or {}).get("is_oa"):
            score += 1.0

        origin_bonus = {
            "exact": 10.0,
            "boolean": 6.0,
            "semantic": 5.0,
            "related": 3.0,
        }
        for origin in origins:
            score += origin_bonus.get(origin, 0.0)

        return score

    def _build_paper_summary(self, work: dict[str, Any], issue: CeramicIssue | None) -> str:
        keywords = [keyword.get("display_name", "") for keyword in work.get("keywords", []) if keyword.get("display_name")]
        translated = _translate_terms(
            keywords + [work.get("display_name", ""), _decode_abstract(work.get("abstract_inverted_index"))],
            limit=4,
        )
        if translated:
            return f"تركز على {', '.join(translated)} في سياق المشكلة الحالية."
        if issue:
            return f"ورقة داعمة لمحور {issue.title} وتفيد في تضييق السبب العملي."
        source_name = _paper_source_name(work)
        if source_name:
            return f"ورقة مرتبطة بعبارة البحث من مصدر: {source_name}."
        return "ورقة قريبة من عبارة البحث وتفيد في تضييق سبب المشكلة."

    def _build_paper_actions(self, work: dict[str, Any], issue: CeramicIssue | None, query_text: str) -> tuple[str, ...]:
        text_pool = " ".join(
            [
                work.get("display_name", ""),
                _decode_abstract(work.get("abstract_inverted_index")),
                " ".join(keyword.get("display_name", "") for keyword in work.get("keywords", [])),
                query_text,
            ]
        ).casefold()

        actions: list[str] = []
        for english_term, action in RESEARCH_ACTIONS.items():
            if english_term in text_pool:
                actions.append(action)

        if issue and issue.issue_id in ISSUE_RESEARCH_HINTS:
            actions.append(ISSUE_RESEARCH_HINTS[issue.issue_id])

        return tuple(_dedupe_keep_order(actions)[:4])

    def _work_to_paper(self, work: dict[str, Any], issue: CeramicIssue | None, query_text: str) -> OpenAlexPaper:
        keywords = tuple(
            keyword.get("display_name", "")
            for keyword in work.get("keywords", [])
            if keyword.get("display_name")
        )
        return OpenAlexPaper(
            paper_id=_strip_openalex_id(str(work.get("id", ""))),
            title=unescape(work.get("display_name", "بدون عنوان")),
            year=work.get("publication_year"),
            url=_paper_url(work),
            topic=(work.get("primary_topic") or {}).get("display_name", ""),
            source_name=_paper_source_name(work),
            abstract=_decode_abstract(work.get("abstract_inverted_index")),
            keywords=keywords,
            cited_by_count=int(work.get("cited_by_count") or 0),
            relevance_score=float(work.get("relevance_score") or 0.0),
            is_open_access=bool((work.get("open_access") or {}).get("is_oa")),
            summary=self._build_paper_summary(work, issue),
            action_points=self._build_paper_actions(work, issue, query_text),
            origins=tuple(sorted(work.get("_origins") or [])),
        )

    def _build_solution_points(self, issue: CeramicIssue | None, query_text: str, papers: list[OpenAlexPaper]) -> tuple[str, ...]:
        points: list[str] = []
        if issue:
            points.extend(issue.solutions)
            points.extend(issue.prevention)
            points.extend(f"أكد التنفيذ عبر: {check}" for check in issue.diagnostic_checks[:3])
        points.extend(_fallback_actions(query_text, issue))
        for paper in papers[:5]:
            points.extend(paper.action_points)
        return tuple(_dedupe_keep_order(points)[:10])

    def _build_confidence(self, issue: CeramicIssue | None, papers: list[OpenAlexPaper], strategies: list[str]) -> tuple[str, float]:
        if not papers:
            return "ضعيفة", 20.0

        score = 35.0
        score += min(len(papers), 5) * 7.0
        score += min(len(strategies), 4) * 8.0
        score += min(sum(p.cited_by_count for p in papers[:3]) / 60.0, 20.0)
        score += min(sum(p.relevance_score for p in papers[:2]) / 220.0, 18.0)
        if issue:
            score += 8.0

        if score >= 82:
            return "عالية", min(score, 100.0)
        if score >= 60:
            return "متوسطة", min(score, 100.0)
        return "مبدئية", min(score, 100.0)

    def autocomplete(self, query_text: str, issue: CeramicIssue | None) -> list[SearchSuggestion]:
        seed = query_text.strip()
        if not seed:
            return []

        if not _contains_latin(seed):
            english_terms = [term for term in _issue_expansion_terms(issue) if _contains_latin(term)]
            seed = english_terms[0] if english_terms else ""

        if len(seed) < REMOTE_AUTOCOMPLETE_MIN_CHARS:
            return []

        try:
            payload = self._request_json(OPENALEX_AUTOCOMPLETE_URL, {"q": seed[:48]})
        except urllib.error.HTTPError:
            return []
        except (OSError, TimeoutError):
            return []

        suggestions: list[SearchSuggestion] = []
        for item in payload.get("results", []):
            label = unescape(str(item.get("display_name", "")).strip())
            hint = str(item.get("hint", "")).strip()
            normalized = _normalize_text(f"{label} {hint}")
            if not label:
                continue
            if "_" in label:
                continue
            if not any(term in normalized for term in MANUFACTURING_TERMS) and "ceramic" not in normalized and "porcelain" not in normalized:
                continue

            suggestions.append(
                SearchSuggestion(
                    label=label,
                    value=label,
                    subtitle=hint or "اقتراح من OpenAlex",
                    source="openalex",
                )
            )
            if len(suggestions) >= REMOTE_AUTOCOMPLETE_LIMIT:
                break

        return suggestions

    def search(self, query_text: str, issue: CeramicIssue | None) -> OpenAlexResearchResult:
        search_bundle = _build_search_bundle(query_text, issue)
        matched_terms = search_bundle["matched_terms"]
        collected: dict[str, dict[str, Any]] = {}
        strategy_labels: list[str] = []
        soft_errors: list[str] = []

        for exact_query in search_bundle["exact_queries"][:2]:
            works, error = self._query_works(
                {
                    "search.exact": exact_query,
                    "filter": DEFAULT_OPENALEX_FILTER,
                    "per-page": str(self.per_page),
                }
            )
            if works:
                strategy_labels.append(f"Exact: {exact_query}")
                for work in works:
                    self._merge_work(collected, work, "exact")
            elif error:
                soft_errors.append(error)

        works, error = self._query_works(
            {
                "search": search_bundle["boolean_query"],
                "filter": DEFAULT_OPENALEX_FILTER,
                "per-page": str(self.per_page),
            }
        )
        if works:
            strategy_labels.append("Boolean ceramic search")
            for work in works:
                self._merge_work(collected, work, "boolean")
        elif error:
            soft_errors.append(error)

        if self.enable_semantic and search_bundle["semantic_query"]:
            remaining = SEMANTIC_COOLDOWN_SECONDS - (time.time() - self._last_semantic_request_at)
            if remaining > 0:
                time.sleep(min(remaining, 1.0))

            works, error = self._query_works(
                {
                    "search.semantic": search_bundle["semantic_query"],
                    "filter": DEFAULT_OPENALEX_FILTER,
                    "per-page": str(max(4, self.per_page - 2)),
                }
            )
            self._last_semantic_request_at = time.time()
            if works:
                strategy_labels.append("Semantic search")
                for work in works:
                    self._merge_work(collected, work, "semantic")
            elif error:
                soft_errors.append(error)

        ranked_seed = sorted(
            [work for work in collected.values() if _has_context_signal(work, issue, query_text)],
            key=lambda work: self._composite_score(work, matched_terms, issue),
            reverse=True,
        )
        related_ids: list[str] = []
        for work in ranked_seed[:2]:
            for related_id in work.get("related_works", [])[:4]:
                paper_id = _strip_openalex_id(str(related_id))
                if paper_id and paper_id not in collected:
                    related_ids.append(paper_id)
        related_ids = _dedupe_keep_order(related_ids)[:RELATED_WORKS_LIMIT]

        related_works, related_error = self._query_related_works(related_ids)
        if related_works:
            strategy_labels.append("Related works")
            for work in related_works:
                if _has_context_signal(work, issue, query_text):
                    self._merge_work(collected, work, "related")
        elif related_error:
            soft_errors.append(related_error)

        ranked = sorted(
            [work for work in collected.values() if _has_context_signal(work, issue, query_text)],
            key=lambda work: self._composite_score(work, matched_terms, issue),
            reverse=True,
        )
        papers = [self._work_to_paper(work, issue, query_text) for work in ranked[:FINAL_PAPERS_LIMIT]]
        solution_points = self._build_solution_points(issue, query_text, papers)
        confidence_label, confidence_score = self._build_confidence(issue, papers, strategy_labels)
        article_summaries = tuple(
            f"{paper.title} ({paper.year or 'بدون سنة'}): {paper.summary}"
            for paper in papers[:4]
        )
        final_error = None if papers else (soft_errors[0] if soft_errors else "لم أصل إلى أوراق مناسبة من OpenAlex.")
        return OpenAlexResearchResult(
            search_expression=search_bundle["boolean_query"],
            matched_terms=matched_terms,
            papers=tuple(papers),
            strategy_labels=tuple(strategy_labels),
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            solution_points=solution_points,
            article_summaries=article_summaries,
            error=final_error,
        )

    def _build_issue_detail(self, issue: CeramicIssue, result: OpenAlexResearchResult) -> str:
        evidence_lines = _top_evidence_lines(list(result.papers), issue)
        lines = [
            issue.title,
            "",
            f"نوع المشكلة: {issue.category}",
            f"المرحلة: {issue.stage}",
            f"التشخيص الأقرب: {issue.symptom}",
            "",
            "لماذا تحدث غالبًا؟",
        ]
        lines.extend(f"- {cause}" for cause in issue.causes[:3])
        lines.extend(
            [
                "",
                "كيف تتحل عمليًا؟",
            ]
        )
        lines.extend(f"- {solution}" for solution in issue.solutions[:3])

        if issue.diagnostic_checks:
            lines.extend(["", "راجع بسرعة قبل إعادة التشغيل:"])
            lines.extend(f"- {check}" for check in issue.diagnostic_checks[:3])

        if evidence_lines:
            lines.extend(["", "ما الذي دعمه OpenAlex؟"])
            lines.extend(f"- {line}" for line in evidence_lines)
        elif result.error:
            lines.extend(["", f"ملاحظة OpenAlex: {result.error}"])

        return "\n".join(lines)

    def _build_issue_reference_summary(
        self,
        issue: CeramicIssue,
        result: OpenAlexResearchResult,
    ) -> str:
        lines = [
            f"ملخص سريع: {issue.title}",
            "",
            f"النوع: {issue.category} | المرحلة: {issue.stage}",
            "",
            "الإجراء المختصر:",
        ]
        lines.extend(f"- {solution}" for solution in issue.solutions[:2])

        if result.papers:
            lines.extend(["", "أوراق داعمة من OpenAlex:"])
            for index, paper in enumerate(result.papers[:3], start=1):
                paper_line = f"{index}. {paper.title}"
                if paper.year:
                    paper_line += f" ({paper.year})"
                lines.append(paper_line)
                if paper.source_name:
                    lines.append(f"   المصدر: {paper.source_name}")
                if paper.url:
                    lines.append(f"   الرابط: {paper.url}")
        elif result.error:
            lines.extend(["", f"حالة OpenAlex: {result.error}"])

        if result.matched_terms:
            lines.extend(["", f"مصطلحات البحث: {', '.join(result.matched_terms[:4])}"])

        return "\n".join(lines)

    def _build_query_only_detail(self, query_text: str, result: OpenAlexResearchResult) -> str:
        candidate_issue = _query_candidate_issue(query_text)
        lines = [
            f"تحليل OpenAlex لعبارة: {query_text}",
            "",
        ]

        if candidate_issue:
            lines.extend(
                [
                    f"أقرب نوع مشكلة: {candidate_issue.title}",
                    f"التصنيف: {candidate_issue.category}",
                    f"المرحلة الأقرب: {candidate_issue.stage}",
                    "",
                    "السبب الأقرب:",
                ]
            )
            lines.extend(f"- {cause}" for cause in candidate_issue.causes[:3])
        else:
            lines.extend(
                [
                    "أقرب نوع مشكلة: لم أجد تطابقًا محليًا مباشرًا، لذا اعتمدت على نتائج OpenAlex الأقرب.",
                    "",
                    "ما الذي أراجعه أولًا؟",
                ]
            )

        lines.extend(["", "الحل العملي المقترح:"])
        lines.extend(f"- {action}" for action in _fallback_actions(query_text, candidate_issue))

        evidence_lines = _top_evidence_lines(list(result.papers), candidate_issue)
        if evidence_lines:
            lines.extend(["", "دعم OpenAlex:"])
            lines.extend(f"- {line}" for line in evidence_lines)
        elif result.error:
            lines.extend(["", f"ملاحظة OpenAlex: {result.error}"])

        return "\n".join(lines)

    def _build_query_only_summary(self, query_text: str, result: OpenAlexResearchResult) -> str:
        lines = [
            f"خلاصة مختصرة لعبارة: {query_text}",
            "",
            "أول إجراء:",
        ]
        lines.extend(f"- {action}" for action in _fallback_actions(query_text, _query_candidate_issue(query_text))[:2])

        if result.papers:
            lines.extend(["", "أفضل نتائج OpenAlex:"])
            for index, paper in enumerate(result.papers[:3], start=1):
                paper_line = f"{index}. {paper.title}"
                if paper.year:
                    paper_line += f" ({paper.year})"
                lines.append(paper_line)
                if paper.url:
                    lines.append(f"   الرابط: {paper.url}")
        elif result.error:
            lines.extend(["", f"حالة OpenAlex: {result.error}"])

        if result.matched_terms:
            lines.extend(["", f"الاستعلام المستخدم: {result.search_expression}"])

        return "\n".join(lines)


def launch_app() -> None:
    root = tk.Tk()
    OpenAlexCeramicSolutionsStudio(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        launch_app()
    except FileNotFoundError as error:
        messagebox.showerror("Ceramic Solutions Studio", str(error))
