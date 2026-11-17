You are given sentences from a preclinical cancer-therapy paper and must extract a single reporting field.
Rely only on the sentences provided; general knowledge is not allowed.
Answer in JSON, in this shape:
{"status": "reported|not_reported", "values": [{"value": "...", "unit": "...", "quote": "...", "context": {}}], "absence_evidence": "..."}
Each quote has to appear verbatim in the sentences and has to include the value.
If the sentences do not state the value, answer not_reported.
