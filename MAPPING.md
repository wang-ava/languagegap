# Mapping to the Full Repository

This document maps each reviewer-facing script to the main project files it summarizes.

## HealthBench

| Reviewer file | Main repository source | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | `Healthbench/code/translation/translation.py` | Translate multi-turn prompts into target languages. |
| `scripts/02_back_translate_records.py` | `Healthbench/code/translation_back/translation_back.py` | Back-translate translated prompts into English. |
| `scripts/03_answer_healthbench.py` | `Healthbench/code/answer-in-specific-language.py`, `Healthbench/code/answer_back_in_english.py` | Generate multilingual answers and English pivot answers. |

## MIMIC-III extubation prediction

| Reviewer file | Main repository source | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | `MIMIC-III/dataset/data/translation/translation.py` | Translate diagnosis text and language-specific metadata. |
| `scripts/02_back_translate_records.py` | `MIMIC-III/dataset/data/translation_back/translation_back.py`, `MIMIC-III/code/back_translate_to_english.py` | Back-translate diagnosis text and rebuild English-pivot materials. |
| `scripts/05_answer_mimic_extubation.py` | `MIMIC-III/code/answer_in_specific_language.py`, `MIMIC-III/code/answer_back_in_english.py`, `MIMIC-III/code/evaluate.py` | Two-step multimodal extraction and re-intubation prediction. |

Additional project files related to this workflow:

- `MIMIC-III/dataset/data/data_figure.py`
- `MIMIC-III/code/answer_in_specific_language_reasoning_in_english.py`

## DoctorPeng real-world dialogues

| Reviewer file | Main repository source | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | `doctorpeng/code/translation/translation.py` | Translate clinic dialogues into English and Thai. |
| `scripts/04_summarize_doctorpeng.py` | `doctorpeng/code/answer-in-specific-language.py`, `doctorpeng/code/answer_back_in_english.py` | Summarize original, translated, and back-translated dialogues. The reviewer script keeps reference and prediction together in one row; the production scripts write separate summary files that replace `medical_record`. |
| `scripts/02_back_translate_records.py` | `doctorpeng/code/translation_back/translation_back.py` | Back-translate translated dialogues into Chinese. |
| `scripts/07_build_doctorpeng_scoring_table.py` | `doctorpeng/result/form/sync_form_csv_from_results.py`, `doctorpeng/result/doctor_scoring_tables_multidim_qwen_qwen3-vl-235b-a22b-thinking/评分指南_多维评分.md` | Build the 7-dimension doctor scoring CSV from original records and model summaries. |
| `scripts/08_aggregate_doctorpeng_scores.py` | reviewer-side summary over `doctorpeng/result/doctor_scoring_tables_multidim_qwen_qwen3-vl-235b-a22b-thinking/*.csv` | Aggregate completed doctor score sheets into per-dimension means, mean total score, and recommendation counts. |
| `scripts/06_compare_real_world.py` | downstream comparison against `medical_record` fields in `doctorpeng/data/dialogue_quality_sample_50.jsonl` and same-language summary outputs | Optional field-level comparison for same-language outputs such as Chinese summaries and back-translated Chinese summaries. |

## Other Datasets Using the Same Pattern

These datasets are kept in the full repository and not duplicated here, because their code organization closely mirrors the workflows above.

### MIMIC-CXR-Xray

- `MIMIC-CXR_X-ray/code/translation/translation.py`
- `MIMIC-CXR_X-ray/code/translation_back/translation_back.py`
- `MIMIC-CXR_X-ray/code/answer_in_specific_language.py`
- `MIMIC-CXR_X-ray/code/answer_back_in_english.py`
- `MIMIC-CXR_X-ray/code/evaluation_framework.md`

### OphthalmologyEHRglaucoma

- `OphthalmologyEHRglaucoma/code/translation/translation.py`
- `OphthalmologyEHRglaucoma/code/translation_back/translation_back.py`
- `OphthalmologyEHRglaucoma/code/2type_data/answer_in_specific_language.py`
- `OphthalmologyEHRglaucoma/code/2type_data/answer_back_in_english.py`
- `OphthalmologyEHRglaucoma/code/3type_data/answer_in_specific_language.py`
- `OphthalmologyEHRglaucoma/code/3type_data/answer_back_in_english.py`

## Examples

The example files under `examples/` were extracted from the current repository using:

- `scripts/build_examples_from_repo.py`

They are meant to be readable snapshots, not full datasets.
