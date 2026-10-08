# PrivGate - an India-aware privacy gateway for LLM APIs

Companies want to use LLMs on customer messages, but those messages contain **Aadhaar numbers, PAN, phone numbers, UPI IDs, bank accounts and names**. Sending them to a third-party API is a privacy risk.

**PrivGate sits in front of the LLM.** It finds personal data *on your own machine*, replaces it with placeholders, sends only the safe text to the LLM, and puts the real values back into the answer.

```
Customer message                    What the LLM sees                         What you get back
"I am Priya Nair, call me   ->      "I am [PERSON_1], call me      ->        "Dear Priya Nair, we will
 on +91 98765 43210"                 on [PHONE_1]"                             call you on +91 98765 43210"
```

## What makes it different from a basic "find phone numbers with regex" script

| Idea | Why it matters |
|---|---|
| **Checksum validation** | An Aadhaar number must pass the Verhoeff check, a card must pass Luhn, a PAN must have a valid holder-type letter. A 12-digit *order ID* is **not** flagged. |
| **Context rules** | A bare 9-18 digit number is ambiguous, but `A/C no. 5010...`, `PIN 302001` and `my name is ...` are clear. |
| **Name linking** | If "Priya Nair" is found, the signature line "Priya" is redacted too, with the same placeholder. |
| **Fail-closed** | Before the API call, the code checks that no original value is still in the outgoing text. If one is, the request is **blocked**. |
| **Privacy-safe audit log** | Logs contain counts only (e.g. `PHONE: 1`), never text or values. |
| **Measured** | `python -m evaluation.run_eval` shows what each idea adds, on a labelled dataset. |

> **Honest scope:** this is a technical safeguard, not legal compliance (for example with India's DPDP Act, 2023) and not a guarantee that *all* personal data is found. Names without any context are the hardest case (see Limitations).

## Quick start (about 5 minutes)

Requires Python 3.10+.

```bash
# 1. virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell   (macOS/Linux: source .venv/bin/activate)

# 2. install
pip install -r requirements-dev.txt

# 3. add your key
copy .env.example .env              # macOS/Linux: cp .env.example .env
# open .env, delete the "#" in front of ONE setup (A, B or C) and paste your key. Save with Ctrl+S.
```

If PowerShell refuses to activate the environment: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Run it

```bash
# Web demo (best for presenting)
streamlit run ui/app.py

# Command line - redaction only (works without an API key)
python -m privgate.cli redact --file samples/complaint_1.txt

# Command line - full flow with the LLM
python -m privgate.cli chat --task draft_reply --file samples/complaint_1.txt

# REST API (docs at http://localhost:8000/docs)
uvicorn privgate.main:app --reload
```

### Which key do I have?

| Your key looks like | Use setup | In `.env` |
|---|---|---|
| `AQ....` or `AIza...` (from aistudio.google.com/apikey, free) | **A: Gemini** | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`, `LLM_MODEL=gemini-2.5-flash` |
| `sk-...` (from platform.openai.com, needs billing credit) | **B: OpenAI** | `OPENAI_API_KEY=sk-...` |
| none (run a model on your own PC with Ollama) | **C: Ollama** | see `.env.example` |

Google's newer AI Studio keys start with `AQ.`. They work with the native Gemini API (`LLM_PROVIDER=gemini`); an older route through an OpenAI-compatible URL may reject them, which is why the project has a native Gemini client.

## Project files the teacher may ask about

| File | What it is |
|---|---|
| `prompts/system_prompt.txt` | The system prompt: tells the LLM how to treat placeholders |
| `prompts/tasks/*.txt` | One prompt file per task (draft a reply, summarize, extract details) |
| `config.yaml` | All settings: model, which data types to detect, checksums on/off, fail-closed, audit log |
| `privgate/llm.py` | The LLM API call (OpenAI-compatible client) |
| `privgate/detectors.py` | The detection rules |
| `privgate/validators.py` | Verhoeff, Luhn and PAN checks |

## Tests and evaluation (no API key needed)

```bash
pytest -q                          # 73 tests
ruff check .                       # lint
python -m evaluation.run_eval      # detection quality + ablation table
python -m evaluation.make_dataset  # regenerate the synthetic dataset (seeded)
python -m evaluation.run_utility   # needs an API key: does redaction break the answers?
```

### Results on the included dataset

300 synthetic messages, 903 personal values, 124 look-alike decoys (order IDs, tracking numbers, product codes):

| configuration | precision | recall | F1 | decoy false-alarm rate |
|---|---|---|---|---|
| 1. plain regex | 0.733 | 0.529 | 0.615 | 0.806 |
| 2. + checksums | 0.970 | 0.529 | 0.685 | 0.008 |
| 3. + context rules | 0.999 | 0.938 | 0.967 | 0.008 |
| 4. + spaCy names (optional) | 0.961 | 0.967 | 0.964 | 0.040 |

Read it like this: checksums fix **precision** (stop flagging order IDs), context rules fix **recall** (find account numbers, PIN codes and names). spaCy finds more bare names but also mislabels a few order IDs as names, so it trades precision for recall.

**Caveat:** the data is synthetic and was written by the same author as the rules, so these numbers are optimistic. Before quoting them, test on realistic messages that were not used to design the rules.

## Optional: better name detection with spaCy

```bash
pip install -r requirements-optional.txt
python -m spacy download en_core_web_sm
```

Then set `use_spacy_ner: true` in `config.yaml` (or use the toggle in the web demo).

## Limitations

* **Names without context** ("Ankit Verma called yesterday") are only found with spaCy, and even spaCy misses some Indian names.
* **Addresses, dates of birth and free-text identifiers** are not detected yet.
* The LLM still sees the *rest* of the message. A very distinctive sentence could identify someone even without their name.
* A 12-digit number that happens to pass the Verhoeff check is treated as an Aadhaar number (and is redacted - the safe direction).
* English and Latin-script text only.

## Push to GitHub

```bash
git init
git add .
git status                  # make sure .env is NOT listed
git commit -m "Initial commit: PrivGate PII redaction gateway for LLMs"
git branch -M main
git remote add origin https://github.com/<your-username>/privgate.git
git push -u origin main
```

## License

MIT
