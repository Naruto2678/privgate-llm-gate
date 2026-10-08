Dataset: 300 synthetic samples, 903 personal values, 124 look-alike decoys.

| configuration | precision | recall | F1 | privacy recall | decoy false-alarm rate |
|---|---|---|---|---|---|
| 1. plain regex | 0.733 | 0.529 | 0.615 | 0.611 | 0.806 |
| 2. + checksums (Verhoeff, Luhn, PAN type) | 0.97 | 0.529 | 0.685 | 0.545 | 0.008 |
| 3. + context rules (A/C, PIN, names) | 0.999 | 0.938 | 0.967 | 0.938 | 0.008 |

Per type (last configuration):

| type | gold | predicted | exact matches |
|---|---|---|---|
| AADHAAR | 64 | 64 | 64 |
| BANK_ACCOUNT | 85 | 85 | 85 |
| CREDIT_CARD | 43 | 43 | 43 |
| EMAIL | 74 | 74 | 74 |
| IFSC | 52 | 52 | 52 |
| PAN | 60 | 60 | 60 |
| PERSON | 280 | 224 | 224 |
| PHONE | 126 | 127 | 126 |
| PIN_CODE | 60 | 60 | 60 |
| UPI_ID | 59 | 59 | 59 |

precision/recall/F1 need an exact span + type match. privacy recall counts a personal value as
covered if ANY detection overlaps it (what matters for privacy). The data is synthetic and written
by the same author as the rules, so treat the numbers as optimistic.
