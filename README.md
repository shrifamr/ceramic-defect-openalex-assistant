# Ceramic Defect OpenAlex Assistant

Open-source Arabic-first assistant for ceramic manufacturing defect diagnosis,
quality control, and materials-science research search using OpenAlex,
ceramic-aware reranking, and short practical research summaries.

![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.x-blue.svg)
![OpenAlex](https://img.shields.io/badge/research-OpenAlex-orange.svg)

Keywords: ceramic defects, ceramic manufacturing, ceramic engineering, quality
control, defect diagnosis, drying cracks, porosity, glaze crazing, materials
science, OpenAlex, Arabic engineering tools.

## عربي

هذا المشروع يشارك الطبقة الذكية التي تضيف إلى مساعد مشاكل السيراميك:

- بحث OpenAlex هجين:
  - exact search
  - boolean expansion
  - semantic search
  - related works
- توسيع ذكي للاستعلامات بالعربي والإنجليزي لمشاكل السيراميك
- اقتراحات أثناء الكتابة
- تلخيص سريع للمقالات بدل القراءة الطويلة
- حلول عملية متعددة مع ترتيب أفضل للنتائج الخاصة بالسيراميك الصناعي
- درجة ثقة أوضح في التشخيص

## فكرة المشروع

بدل أن يقرأ المستخدم مقالات كثيرة ليعرف سبب المشكلة، هذا المشروع يحاول أن:

- يفهم مشكلة السيراميك المكتوبة من المستخدم
- يربطها بأقرب أبحاث من OpenAlex
- يفلتر النتائج البعيدة عن صناعة السيراميك
- يخرج السبب الأقرب والحلول العملية بشكل مختصر

## ما الموجود في الريبو العام

- `openalex_ceramic_bridge.py`
  منطق البحث، التوسيع، الفلترة، الترتيب، والتلخيص
- `CeramicSolutionsStudio_OpenAlex.py`
  نقطة تشغيل خفيفة
- `openalex_config.example.json`
  مثال لإعداد بريد التواصل أو مفتاح OpenAlex

## ما ليس موجودًا هنا

هذا الريبو العام لا يحتوي على:

- ملفات `.exe`
- ملفات runtime المستخرجة من التطبيق الأصلي
- نواتج البناء المحلية

السبب هو إبقاء النسخة العامة أخف وأنظف وأسهل للاستفادة، مع ترك الأرشيف الكامل
في الريبو الخاص.

## Quick Start

If you already have the original runtime locally:

1. Place these files next to the extracted runtime folder.
2. Copy `openalex_config.example.json` to `openalex_config.json` if needed.
3. Run:

```powershell
python .\CeramicSolutionsStudio_OpenAlex.py
```

## Typical use cases

- diagnosing drying cracks in ceramic tiles
- understanding high porosity or water absorption problems
- summarizing glaze crazing or pinhole research
- generating practical fixes from research instead of raw paper lists

## Notes

- This public repo shares the OpenAlex bridge layer only.
- The bridge currently expects the original app runtime structure if used as-is.
- You can still reuse the OpenAlex search logic independently in another Python
  desktop or web interface.

## License

Released under the MIT License so others can study it, build on it, and adapt
it to their own ceramic quality or research workflows.
