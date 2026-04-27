# Mapping to the Full Repository

This document maps each reviewer-facing script to the corresponding stage in the main project workflow.

## HealthBench

| Reviewer file | Full-repository stage | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | prompt translation stage | Translate multi-turn prompts into target languages. |
| `scripts/02_back_translate_records.py` | prompt back-translation stage | Back-translate translated prompts into English. |
| `scripts/03_answer_healthbench.py` | multilingual answering and English-pivot answering stages | Generate multilingual answers and English pivot answers. |

## MIMIC-III extubation prediction

| Reviewer file | Full-repository stage | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | diagnosis translation stage | Translate diagnosis text and language-specific metadata. |
| `scripts/02_back_translate_records.py` | diagnosis back-translation stage | Back-translate diagnosis text and rebuild English-pivot materials. |
| `scripts/05_answer_mimic_extubation.py` | multilingual inference and evaluation stages | Two-step multimodal extraction and re-intubation prediction. |

Additional project files related to this workflow:

- figure-building utilities
- English-reasoning variants of the multilingual inference script

## Real-World Clinical Dialogues

| Reviewer file | Full-repository stage | Purpose |
| --- | --- | --- |
| `scripts/01_translate_records.py` | dialogue translation stage | Translate clinic dialogues into English and Thai. |
| `scripts/04_summarize_realworld.py` | multilingual summarization stage | Summarize original, translated, and back-translated dialogues. The reviewer script can either keep the summary in `predicted_medical_record` for inspection or write it into `medical_record` to mimic the production layout. |
| `scripts/02_back_translate_records.py` | dialogue back-translation stage | Back-translate translated dialogues into Chinese. |
| `scripts/07_build_realworld_review_file.py` | doctor-review table preparation stage | Build the doctor-review JSON schema that mirrors the exported edit files used in the full repository. |
| `scripts/08_evaluate_realworld_modification.py` | doctor-edit evaluation stage | Compute modification score and modification rate from doctor-edited summaries. |
| `scripts/06_compare_real_world.py` | auxiliary same-language comparison stage | Auxiliary field-level comparison for same-language outputs such as Chinese summaries and back-translated Chinese summaries. |

Related full-repository step:

- normalization of non-Chinese summaries into Chinese before doctor review

This reviewer package does not duplicate that normalization step, but it keeps the downstream review-file and modification-score logic aligned with it.

## Other Datasets Using the Same Pattern

These datasets are kept in the full repository and not duplicated here, because their code organization closely mirrors the workflows above.

### MIMIC-CXR-Xray

- translation stage
- back-translation stage
- multilingual answering stage
- English-pivot answering stage
- evaluation framework notes

### OphthalmologyEHRglaucoma

- translation stage
- back-translation stage
- multilingual answering stages for the different data layouts
- English-pivot answering stages for the different data layouts

## Examples

The example files under `examples/` were extracted from the current repository using:

- `scripts/build_examples_from_repo.py`

They are meant to be readable snapshots, not full datasets.
