# Real-World Evaluation Guide

This reviewer package follows the same real-world evaluation idea as the full clinical-dialogue workflow:

1. generate a structured model summary from the dialogue
2. normalize non-Chinese summaries into Chinese in the full repository
3. let doctors revise the model summary field by field
4. compute edit burden from the doctor-exported JSON

## Formal Metric

The real metric is not a rubric score. It is the doctor modification burden.

- `modification_score = changed_field_count / total_editable_field_slots`
- `modification_rate = changed_sample_count / total_samples`

Here `total_editable_field_slots = N samples x 6 editable fields`.

A modification score of `50%` means that, on average, doctors changed `3 / 6` editable fields per sample.

## Editable Fields

The editable schema matches the full doctor-review tables:

- `chief_complaint`
- `history_of_present_illness`
- `past_history`
- `personal_history`
- `allergy_history`
- `genetic_history`

The upstream model summaries often only contain the first 4 fields. In the real review workflow, the last 2 fields are still exposed as editable blanks, so doctors can add missing information if needed.

## Review JSON Schema

The exported doctor-review files use records like:

```json
{
  "uid": "table2_english_summary:1",
  "row_index": 1,
  "patient_id": "1",
  "patient_label": "患者 1",
  "source_id": "table2_english_summary",
  "source_jsonl": "path/to/english_summary.jsonl",
  "source_line_number": 1,
  "source_sha256": "...",
  "reviewed": true,
  "edited_report_language": "zh",
  "edited_report_text": "主诉：...",
  "edited_report": {
    "chief_complaint": "...",
    "history_of_present_illness": "...",
    "past_history": "...",
    "personal_history": "...",
    "allergy_history": "...",
    "genetic_history": "..."
  },
  "original_current_report_text": "主诉：...",
  "original_current_report": {
    "chief_complaint": "...",
    "history_of_present_illness": "...",
    "past_history": "...",
    "personal_history": "",
    "allergy_history": "...",
    "genetic_history": ""
  },
  "original_report_text_from_raw_lines": "...",
  "original_dialogue_from_raw_lines": "...",
  "current_dialogue": "...",
  "raw_record": { "...": "..." }
}
```

The formal comparison is always:

- `edited_report` versus `original_current_report`

It is not a direct string-similarity comparison against the gold medical record.

## Reviewer Scripts in This Folder

- `scripts/07_build_realworld_review_file.py`
Creates a starter JSON file in the same schema as the full doctor-review exports.

- `scripts/08_evaluate_realworld_modification.py`
Computes modification score and modification rate from one or more doctor-edited JSON files.

- `scripts/06_compare_real_world.py`
Only a quick same-language inspection helper against the reference record. It is not the formal real-world evaluation metric.
