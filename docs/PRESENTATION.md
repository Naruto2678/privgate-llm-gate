# Presentation guide (about 8 minutes)

## 30-second pitch

"Companies want to use LLMs on customer messages, but those messages contain Aadhaar numbers, PAN, phone numbers and bank details. PrivGate is a gateway that removes personal data on your own machine before the LLM call, then puts the real values back in the answer. I checked it against a plain-regex baseline: the baseline flags 81% of look-alike IDs such as order numbers as personal data, and PrivGate flags under 1%."

## Slide outline

1. **Title** - PrivGate: an India-aware privacy gateway for LLM APIs. Your name, course.
2. **The problem** - Customer messages contain personal data. Sending it to an external LLM is a privacy risk. India's DPDP Act, 2023 raises the stakes (say "motivated by", not "compliant with").
3. **Why a simple regex fails** - Show: `order 987654321098` is flagged as an Aadhaar number by plain regex. 12 digits is not enough.
4. **The solution (flow diagram)** - message -> detect -> redact -> safety check -> LLM -> restore. Draw it from `ARCHITECTURE.md`.
5. **Three detection ideas** - (a) checksums: Verhoeff for Aadhaar, Luhn for cards, PAN holder letter; (b) context rules: "A/C no.", "PIN", "my name is"; (c) name linking: "Priya Nair" also catches the signature "Priya".
6. **Safety by design** - Fail-closed check, counts-only audit log, vault kept in memory only, warnings if the model invents data.
7. **LLM integration** - Show `prompts/system_prompt.txt` (how placeholders are explained to the model), `prompts/tasks/`, `config.yaml`, `privgate/llm.py`.
8. **Evaluation** - Show the ablation table from the README. One sentence per row. State clearly that the data is synthetic.
9. **Live demo** - see below.
10. **Limitations and future work** - bare names, addresses, dates of birth, Hindi/Hinglish text; next steps: Indic-language NER, address detection, evaluation on real data.
11. **Questions**.

## Live demo script (3 minutes)

1. Run `streamlit run ui/app.py`. Load **Complaint 1**. Click **Redact only**. Point at the highlighted values and at the order ID and tracking number that are *not* highlighted.
2. In the sidebar, turn **Checksums off**. Click again. The order ID turns into a fake "Aadhaar" and the tracking number into a fake "card". Say: "This is what a basic regex does." Turn checksums back on.
3. Click **Redact + ask the LLM**. Show the three panels: what the LLM received (placeholders only), the answer as received, and the final answer with real values restored.
4. Optional: in a terminal run `pytest -q` and `python -m evaluation.run_eval`.

**Backup plan:** if the API or Wi-Fi fails, "Redact only" works without internet and still shows the main idea. Keep screenshots of the full flow in the slides.

## Likely questions and good answers

* **Why not ask an LLM to find the personal data?** That would send the personal data to the LLM, which is exactly what we want to avoid. Local rules are also free, fast and testable.
* **What is the Verhoeff algorithm?** A checksum used by Aadhaar numbers. It detects every single-digit typo, so most random 12-digit numbers fail it. My test suite checks this property.
* **What if the LLM changes a placeholder?** The gateway warns about placeholders that were never created, and about personal-looking data the model made up.
* **What if detection misses something?** Then it is sent. That is the main limitation. The evaluation measures recall, and the next step is more detectors (addresses, dates of birth) plus testing on real data.
* **How do you know it works?** 73 automated tests, plus an ablation on 300 labelled messages. The data is synthetic, so I treat the numbers as optimistic.
* **Is this GDPR/DPDP compliant?** No tool is compliant by itself. It is a technical safeguard that reduces what leaves the system.
* **Why placeholders instead of fake names?** They are unambiguous, easy to restore exactly, and the model cannot confuse them with real people.
* **What did the evaluation teach you?** It found real bugs: a card number partly matched as an Aadhaar number, and a safety check that blocked a request wrongly. Both are fixed and covered by tests.

## Where to point the teacher

* **Prompt file:** `prompts/system_prompt.txt` and `prompts/tasks/`
* **Config file:** `config.yaml`
* **LLM API implementation:** `privgate/llm.py` and `privgate/gateway.py`
* **Code quality:** tests in `tests/`, lint with `ruff`, GitHub Actions in `.github/workflows/ci.yml`

## Resume bullets (only after you have run the evaluation yourself and the numbers match)

* Built **PrivGate**, an India-aware PII redaction gateway for LLM APIs (Python, FastAPI, Streamlit, OpenAI-compatible API): detects Aadhaar (Verhoeff), PAN, cards (Luhn), UPI, IFSC, phone, email and names; redacts before the LLM call, restores values in the answer, and blocks requests that would leak (fail-closed).
* Benchmarked against a plain-regex baseline on a 300-message synthetic set: raised precision from 0.73 to 0.99 and cut false alarms on look-alike IDs from 81% to under 1%; 73 automated tests and GitHub Actions CI.

Keep "synthetic" in your interview answer. If asked, say the next step is testing on realistic data.
