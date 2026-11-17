Your task is a reporting-completeness audit of one preclinical cancer-therapy paper.
For each of the 16 fields below, decide one status:
- "reported" — the text gives a value, or an explicit qualitative fact for a categorical field;
- "not_reported" — the text does not give it;
- "not_applicable" — the field cannot apply to this study (for example, in-vivo fields in a purely in-vitro study).

The fields:
1. kd — apparent dissociation constant, in nM/uM/pM, with method, buffer and temperature when given.
2. id_per_g — normalised tumour accumulation (%ID/g), with time point and organ when given.
3. half_life — half-life or clearance, in h or mL/h/kg.
4. dose — the administered dose and unit (mg/kg, nmol/kg, and so on), with route when given.
5. route — i.v., i.p., s.c., intravesical, oral, and similar.
6. time_points — the time points at which a PK or biodistribution readout was measured.
7. numeric_efficacy — a numeric % tumour growth inhibition or % cell inhibition.
8. serum_stability — degradation half-time, or stability in serum, with conditions.
9. valency — the integer number of aptamers or ligands per construct, or a designed ratio.
10. spacing — the ligand-to-ligand distance or spacing in nm.
11. linker_length — the linker or spacer length in nt.
12. linker_chemistry — the linker or spacer chemistry (poly-A, PEG, TEG, and so on).
13. size — the construct size in nm, with method when given.
14. attachment — the attachment site or orientation (vertex, edge, face, 5' end, 3' end, and so on).
15. comparator — a free-aptamer, monovalent, naked or other comparator arm.
16. immune — CpG content, or any innate-immune or cytokine readout.

Rules to follow:
- Copy every quote verbatim from the document; never paraphrase it.
- The quote you return must contain the value itself.
- When a value is absent, do not infer it from general knowledge; answer "not_reported".
- When the document reports several values (for example several Kd values), return all of them.
- When stated, context — buffer, temperature, method, cell line, time point, route — belongs to the value.

Answer with a single JSON object whose keys are exactly these 16 field names. For every key:
{"status": "...", "values": [{"value": "...", "unit": "...", "quote": "...", "context": {...}}], "absence_evidence": "..."}
