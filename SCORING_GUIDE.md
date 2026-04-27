# DoctorPeng Scoring Guide

This rubric is the reviewer-facing version of the 7-dimension doctor scoring table used in the full repository.

## What Is Scored

Review each case by comparing:

1. the original Chinese dialogue
2. the translated or back-translated dialogue shown for that condition
3. the original reference medical record
4. the model summary report

## Seven Dimensions

### 1. Chief Complaint Fidelity

- `1`: The main complaint is wrong or missing.
- `3`: The complaint is mostly correct but incomplete or overly generic.
- `5`: The complaint is complete, accurate, and clinically central.

### 2. Information Completeness

- `1`: Major history elements are missing.
- `3`: Core information is present, but important details are omitted.
- `5`: Key clinical elements are comprehensively covered.

### 3. Medical Accuracy

- `1`: The summary contains clear medical errors or implausible statements.
- `3`: It is broadly usable but contains some imprecise wording.
- `5`: Medical content is accurate and terminology is appropriate.

### 4. Temporal And Logical Consistency

- `1`: The timeline is confused or contradictory.
- `3`: It is mostly consistent but has local jumps or ambiguities.
- `5`: The timeline and causal structure are clear and coherent.

### 5. Safety And Risk Awareness

- `1`: The summary introduces misleading risk information or misses obvious risk.
- `3`: No major unsafe statement is present, but risk awareness is limited.
- `5`: Safety is well preserved and key risks are recognized appropriately.

### 6. Clinical Actionability

- `1`: The report is not clinically useful.
- `3`: It is partly usable but still requires substantial correction.
- `5`: It is directly useful for clinical communication or documentation support.

### 7. Clarity And Structure

- `1`: The text is difficult to read or poorly structured.
- `3`: It is readable but loosely organized.
- `5`: It is clear, well structured, and easy to scan.

## Score Summary

- Each dimension is scored from `1` to `5`.
- Total score range: `7` to `35`.
- Recommendation field: `采纳`, `需修改`, or `不采纳`.
- Main issue field: briefly note the most important error, such as chief complaint drift, missing surgery history, or timeline inconsistency.

## Related Reviewer Scripts

- `scripts/07_build_doctorpeng_scoring_table.py`: build the doctor scoring CSV.
- `scripts/08_aggregate_doctorpeng_scores.py`: summarize completed score sheets.
