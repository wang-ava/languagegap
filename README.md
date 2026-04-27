# Reviewer Code Package for Multilingual Clinical Evaluation

This folder is a reviewer-facing, cleaned-up subset of the full project.

Its goal is to show, in one place, how the project works end to end:

1. source data preparation
2. forward translation into target languages
3. native-language model answering or summarization
4. back-translation into English or Chinese
5. answer generation on back-translated content
6. evaluation against benchmark references or doctor-reviewed real-world summaries

The code here is intentionally simpler than the production repository. It keeps the same study logic and case identities, but removes most path-specific, resume-specific, and plotting-specific details so reviewers can read the workflow quickly.

For reviewer readability, a few outputs are normalized into a single inspection-friendly format. The main real-world example keeps the original `medical_record` and adds `predicted_medical_record`, while the full repository writes standalone summary files where `medical_record` itself is replaced by the model output. The lightweight field-comparison script in this folder supports both layouts when the reference and prediction are already in the same language.

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

### 3. `Real-World Clinical Dialogue`

Real-world outpatient dialogue summarization.

- source: Chinese clinic dialogues with reference medical-record fields
- forward translation: dialogue -> English / Thai
- model inference: summarize dialogue into structured clinical fields
- back-translation: translated dialogue -> Chinese
- pivot inference: summarize the back-translated Chinese dialogue
- primary evaluation: doctors revise the model summary and the project computes modification score / modification rate from the edited fields

The formal doctor review in the full repository is run on Chinese-normalized summary files. This reviewer package does not duplicate that normalization script, but it keeps the same downstream review-file schema and the same modification-score definition.

## Why This Folder Exists

The full repository contains multiple datasets, many result directories, logs, evaluation exports, and exploratory analyses. That is useful for research, but it is not the best shape for peer review.

This folder gives reviewers a compact package with:

- minimal scripts for each major stage
- a mapping back to the original repository workflow stages
- a few real examples extracted from this repository

## Folder Layout

```text
.
├── README.md
├── MAPPING.md
├── REALWORLD_REVIEW_GUIDE.md
├── requirements.txt
├── examples/
│   ├── README.md
│   ├── healthbench/
│   ├── mimic_iii/
│   └── realworld/
└── scripts/
    ├── common.py
    ├── 01_translate_records.py
    ├── 02_back_translate_records.py
    ├── 03_answer_healthbench.py
    ├── 04_summarize_realworld.py
    ├── 05_answer_mimic_extubation.py
    ├── 06_compare_real_world.py
    ├── 07_build_realworld_review_file.py
    ├── 08_evaluate_realworld_modification.py
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

Real-world dialogue summarization:

```bash
python scripts/01_translate_records.py \
  --input path/to/realworld_dialogue_sample_50.jsonl \
  --output examples/tmp_realworld_english_dialogue.jsonl \
  --field conversation_turns \
  --field-type turns \
  --target-language English \
  --output-field conversation_turns

python scripts/04_summarize_realworld.py \
  --input examples/tmp_realworld_english_dialogue.jsonl \
  --output examples/tmp_realworld_english_summary.jsonl \
  --target-language English \
  --predicted-field medical_record
```

Doctor-review file generation:

```bash
python scripts/07_build_realworld_review_file.py \
  --input path/to/normalized_english_summary.jsonl \
  --output examples/tmp_realworld_english_review.json \
  --source-id table2_english_summary
```

After doctors finish editing and export a JSON file in the same schema:

```bash
python scripts/08_evaluate_realworld_modification.py \
  --inputs path/to/exported_review_edits.json \
  --output examples/tmp_realworld_modification_summary.json \
  --markdown-output examples/tmp_realworld_modification_report.md
```

Optional same-language field comparison against the reference record:

```bash
python scripts/06_compare_real_world.py \
  --reference-input path/to/realworld_dialogue_sample_50.jsonl \
  --predicted-input path/to/back_translated_chinese_summary.jsonl \
  --output examples/tmp_realworld_back_zh_comparison.jsonl
```

To make the reviewer scripts write closer to the production layout, use:

- `01_translate_records.py --output-field <source_field>`
- `02_back_translate_records.py --output-field <source_field>`
- `04_summarize_realworld.py --predicted-field medical_record`

Review details:

- See [REALWORLD_REVIEW_GUIDE.md](./REALWORLD_REVIEW_GUIDE.md) for the editable fields, exported JSON schema, and modification-score formula.

Build reviewer examples directly from this repository:

```bash
python scripts/build_examples_from_repo.py --repo-root .
```

## Notes

- This package is for transparency and inspection. Some reviewer examples are normalized so one case can be read end to end without jumping between files, but the stage ordering and source artifacts stay aligned with the full repository.
- For the real-world dialogue workflow, the primary evaluation is doctor edit burden: doctors revise the summary, and the project reports modification score and modification rate over 6 editable fields.
- The lightweight `06_compare_real_world.py` script is only an auxiliary same-language inspection aid. It is useful for quick field-level comparisons against the reference record, but it is not the formal doctor-review metric used in the paper workflow.
- In the full repository, non-Chinese summaries are normalized into Chinese before doctor review. This package only exposes the downstream review and modification-score steps.
- The exported MIMIC-III example is a single coherent case: `fig_idx = 113`, `patient_id = 3824`. The response example paths are rewritten to valid repository-relative image paths so reviewers can reuse them directly.
- `MIMIC-CXR-Xray` and `OphthalmologyEHRglaucoma` follow the same forward-translation / multilingual inference / back-translation pattern, but they are not duplicated here to keep the reviewer package compact. Their original locations are summarized in [MAPPING.md](./MAPPING.md).
