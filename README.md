# Reviewer Code Package for Multilingual Clinical Evaluation

This folder is a reviewer-facing, cleaned-up subset of the full project.

Its goal is to show, in one place, how the project works end to end:

1. source data preparation
2. forward translation into target languages
3. native-language model answering or summarization
4. back-translation into English
5. answer generation on back-translated content
6. evaluation against benchmark references or real-world clinical answers

The code here is intentionally simpler than the production repository. It keeps the same study logic and case identities, but removes most path-specific, resume-specific, and plotting-specific details so reviewers can read the workflow quickly.

For reviewer readability, a few outputs are normalized into a single inspection-friendly format. The main example is `DoctorPeng`: the reviewer script keeps the original `medical_record` and adds `predicted_medical_record`, while the production summary scripts in the full repository write a separate file where `medical_record` itself is replaced by the model summary. The field-level comparison script in this folder supports both layouts when the reference and prediction are already in the same language.

## Included Workflows

### 1. `HealthBench`

Text-only multilingual benchmark.

- source: English multi-turn prompts
- forward translation: prompt -> Chinese / Malay / Thai / Persian
- model inference: answer in the translated language
- back-translation: translated prompt -> English
- pivot inference: answer the back-translated English prompt

### 2. `MIMIC-III` extubation prediction

Vision-language workflow over time-series monitoring figures.

- source: ICU monitoring figure plus metadata
- language adaptation: multilingual figure text / prompts
- model inference: two-step extraction and re-intubation prediction
- back-translation pivot: English figure regenerated from translated content, then answered again in English

### 3. `DoctorPeng`

Real-world outpatient dialogue summarization.

- source: Chinese clinic dialogues with reference medical-record fields
- forward translation: dialogue -> English / Thai
- model inference: summarize dialogue into structured clinical fields
- back-translation: translated dialogue -> Chinese
- pivot inference: summarize the back-translated Chinese dialogue
- reviewer evaluation: doctors score model summaries against the original dialogue and reference record using a 7-dimension rubric

## Why This Folder Exists

The full repository contains multiple datasets, many result directories, logs, evaluation exports, and exploratory analyses. That is useful for research, but it is not the best shape for peer review.

This folder gives reviewers a compact package with:

- minimal scripts for each major stage
- a mapping back to the original repository files
- a few real examples extracted from this repository

## Folder Layout

```text
.
├── README.md
├── MAPPING.md
├── SCORING_GUIDE.md
├── requirements.txt
├── examples/
│   ├── README.md
│   ├── healthbench/
│   ├── mimic_iii/
│   └── doctorpeng/
└── scripts/
    ├── common.py
    ├── 01_translate_records.py
    ├── 02_back_translate_records.py
    ├── 03_answer_healthbench.py
    ├── 04_summarize_doctorpeng.py
    ├── 05_answer_mimic_extubation.py
    ├── 06_compare_real_world.py
    ├── 07_build_doctorpeng_scoring_table.py
    ├── 08_aggregate_doctorpeng_scores.py
    └── build_examples_from_repo.py
```

## Minimal Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
export BASE_URL=https://openrouter.ai/api/v1
```

## Example Usage

Forward translation:

```bash
python scripts/01_translate_records.py \
  --input Healthbench/dataset/hard_2025-05-08-21-00-10_english_only_sample_100.jsonl \
  --output examples/tmp_healthbench_translation.jsonl \
  --field prompt \
  --field-type messages \
  --target-language Chinese
```

Back-translation:

```bash
python scripts/02_back_translate_records.py \
  --input examples/tmp_healthbench_translation.jsonl \
  --output examples/tmp_healthbench_back_translation.jsonl \
  --field translation \
  --field-type messages \
  --source-language Chinese
```

HealthBench answering:

```bash
python scripts/03_answer_healthbench.py \
  --input examples/tmp_healthbench_translation.jsonl \
  --output examples/tmp_healthbench_answers.jsonl \
  --language-label ZH
```

DoctorPeng summarization and scoring:

```bash
python scripts/01_translate_records.py \
  --input doctorpeng/data/dialogue_quality_sample_50.jsonl \
  --output examples/tmp_doctorpeng_english_dialogue.jsonl \
  --field conversation_turns \
  --field-type turns \
  --target-language English \
  --output-field conversation_turns

python scripts/04_summarize_doctorpeng.py \
  --input examples/tmp_doctorpeng_english_dialogue.jsonl \
  --output examples/tmp_doctorpeng_english_summary.jsonl \
  --target-language English

python scripts/07_build_doctorpeng_scoring_table.py \
  --reference-input doctorpeng/data/dialogue_quality_sample_50.jsonl \
  --predicted-input examples/tmp_doctorpeng_english_summary.jsonl \
  --output examples/tmp_doctorpeng_scoring.csv
```

After doctors fill the 7 dimension columns and recommendation fields:

```bash
python scripts/08_aggregate_doctorpeng_scores.py \
  --inputs examples/tmp_doctorpeng_scoring.csv \
  --output examples/tmp_doctorpeng_score_summary.json
```

Optional same-language field comparison for Chinese outputs:

```bash
python scripts/06_compare_real_world.py \
  --reference-input doctorpeng/data/dialogue_quality_sample_50.jsonl \
  --predicted-input doctorpeng/result/summary_back/qwen_qwen3-vl-235b-a22b-thinking/english_back_to_chinese_summary.jsonl \
  --output examples/tmp_doctorpeng_back_zh_comparison.jsonl
```

To make the reviewer scripts write closer to the production layout, use:

- `01_translate_records.py --output-field <source_field>`
- `02_back_translate_records.py --output-field <source_field>`
- `04_summarize_doctorpeng.py --predicted-field medical_record`

Reviewer scoring rubric:

- See [SCORING_GUIDE.md](./SCORING_GUIDE.md) for the 7 dimensions and 1/3/5 anchors.

Build reviewer examples directly from this repository:

```bash
python scripts/build_examples_from_repo.py --repo-root .
```

## Notes

- This package is for transparency and inspection. Some reviewer examples are normalized so one case can be read end to end without jumping between files, but the stage ordering and source artifacts stay aligned with the full repository.
- For `DoctorPeng`, the primary reviewer-facing evaluation is the 7-dimension doctor scoring table, not raw cross-language string similarity. The reviewer package therefore includes scripts to build score sheets and aggregate completed scores.
- The lightweight `06_compare_real_world.py` script is a field-level inspection aid for same-language outputs such as Chinese summaries and back-translated Chinese summaries.
- The original repository still contains the full experimental code, logs, figures, and evaluation outputs.
- The exported MIMIC-III example is a single coherent case: `fig_idx = 113`, `patient_id = 3824`. The response example paths are rewritten to valid repository-relative image paths so reviewers can reuse them directly.
- `MIMIC-CXR-Xray` and `OphthalmologyEHRglaucoma` follow the same forward-translation / multilingual inference / back-translation pattern, but they are not duplicated here to keep the reviewer package compact. Their original locations are listed in [MAPPING.md](./MAPPING.md).
