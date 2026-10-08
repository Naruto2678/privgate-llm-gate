"""Generate the labelled evaluation set (synthetic, seeded, reproducible).

    python -m evaluation.make_dataset            # writes evaluation/data/eval_set.jsonl

Every sample is built from templates; the exact character span of each personal value is recorded
as gold. "Decoys" are look-alike numbers/codes (order IDs, tracking numbers, product codes) that
are NOT personal data and must NOT be redacted. All values are synthetic.
"""

from __future__ import annotations

import json
import random
import re
import string
from pathlib import Path

from privgate.validators import PAN_HOLDER_TYPES, luhn_check_digit, luhn_valid, verhoeff_check_digit, verhoeff_valid

OUT = Path(__file__).resolve().parent / "data" / "eval_set.jsonl"
FIRST = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Karan", "Meera", "Arjun", "Kavya", "Ishaan", "Neha",
         "Rahul", "Pooja", "Siddharth", "Divya", "Amit", "Riya", "Nikhil", "Tanvi", "Manish", "Aditi"]  # fmt: skip
LAST = ["Sharma", "Verma", "Nair", "Iyer", "Mehta", "Kapoor", "Singh", "Reddy", "Gupta", "Joshi", "Patel", "Rao",
        "Chatterjee", "Bose", "Thakur", "Menon", "Saxena", "Bhatt"]  # fmt: skip
UPI = ["okaxis", "ybl", "paytm", "oksbi", "okicici"]
BANKS = ["HDFC", "SBIN", "ICIC", "UTIB", "KKBK", "PUNB"]
MAIL = ["gmail.com", "outlook.com", "yahoo.co.in", "company.in"]


def digits(rng: random.Random, n: int, first: str = "0123456789") -> str:
    return rng.choice(first) + "".join(rng.choice(string.digits) for _ in range(n - 1))


def gen_aadhaar(rng):
    body = digits(rng, 11, "23456789")
    n = body + verhoeff_check_digit(body)
    return rng.choice([f"{n[:4]} {n[4:8]} {n[8:]}", n, f"{n[:4]}-{n[4:8]}-{n[8:]}"])


def gen_pan(rng):
    letters = string.ascii_uppercase
    return "".join(rng.choice(letters) for _ in range(3)) + rng.choice(sorted(PAN_HOLDER_TYPES)) + rng.choice(letters) \
        + digits(rng, 4) + rng.choice(letters)  # fmt: skip


def gen_phone(rng):
    n = digits(rng, 10, "6789")
    return rng.choice([n, f"{n[:5]} {n[5:]}", f"+91 {n[:5]} {n[5:]}", f"+91-{n}", f"0{n[:5]}-{n[5:]}"])


def gen_card(rng):
    body = rng.choice("45") + digits(rng, 14)
    n = body + luhn_check_digit(body)
    return rng.choice([f"{n[:4]} {n[4:8]} {n[8:12]} {n[12:]}", f"{n[:4]}-{n[4:8]}-{n[8:12]}-{n[12:]}"])


def gen_ifsc(rng):
    return rng.choice(BANKS) + "0" + "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(6))


def gen_decoy_order(rng):  # 12 digits, NOT a valid Aadhaar
    while True:
        n = digits(rng, 12, "23456789")
        if not verhoeff_valid(n):
            return n


def gen_decoy_track(rng):  # 14 digits, NOT Luhn-valid
    while True:
        n = digits(rng, 14, "123456789")
        if not luhn_valid(n):
            return n


def gen_decoy_code(rng):  # looks like a PAN but the 4th letter is not a holder type
    bad = [c for c in string.ascii_uppercase if c not in PAN_HOLDER_TYPES]
    letters = string.ascii_uppercase
    return "".join(rng.choice(letters) for _ in range(3)) + rng.choice(bad) + rng.choice(letters) + digits(rng, 4) \
        + rng.choice(letters)  # fmt: skip


def person(rng, ctx):
    if "first" not in ctx:
        ctx["first"], ctx["last"] = rng.choice(FIRST), rng.choice(LAST)
    return ctx["first"], ctx["last"]


def make_generators(rng, ctx):
    def email():
        f, l = person(rng, ctx)
        return f"{f.lower()}.{l.lower()}{rng.randint(1, 99)}@{rng.choice(MAIL)}"

    def upi():
        f, _ = person(rng, ctx)
        return f"{f.lower()}{rng.randint(10, 999)}@{rng.choice(UPI)}"

    return {
        "PERSON": lambda: " ".join(person(rng, ctx)),
        "FIRSTNAME": lambda: person(rng, ctx)[0],
        "AADHAAR": lambda: gen_aadhaar(rng), "PAN": lambda: gen_pan(rng), "PHONE": lambda: gen_phone(rng),
        "EMAIL": email, "UPI_ID": upi, "IFSC": lambda: gen_ifsc(rng), "CREDIT_CARD": lambda: gen_card(rng),
        "BANK_ACCOUNT": lambda: digits(rng, rng.randint(11, 16), "123456789"),
        "PIN_CODE": lambda: digits(rng, 6, "123456789"),
        "DECOY_ORDER": lambda: gen_decoy_order(rng), "DECOY_TRACK": lambda: gen_decoy_track(rng),
        "DECOY_PHONELIKE": lambda: digits(rng, 10, "12345"), "DECOY_CODE": lambda: gen_decoy_code(rng),
        "DECOY_TICKET": lambda: digits(rng, 6, "123456789"),
    }  # fmt: skip


GOLD_TYPE = {"FIRSTNAME": "PERSON"}

PII_TEMPLATES = [
    "Hello, my name is {PERSON}. Please call me on {PHONE}.",
    "Mr. {PERSON} reported that his card {CREDIT_CARD} was charged twice.",
    "KYC check: Aadhaar {AADHAAR} belongs to the applicant. Contact {EMAIL}.",
    "Please refund to A/C no. {BANK_ACCOUNT}, IFSC {IFSC}, UPI {UPI_ID}.",
    "Customer Name: {PERSON}\nPAN: {PAN}",
    "Ship the parcel to PIN {PIN_CODE} and call {PHONE} on arrival.",
    "I am {PERSON}. My PAN is {PAN} and my email is {EMAIL}.",
    "The loan applicant {PERSON} submitted Aadhaar {AADHAAR}.",
    "Dr. {PERSON} will call you from {PHONE} tomorrow.",
    "Account number {BANK_ACCOUNT} is linked to UPI {UPI_ID}.",
    "Please verify PAN {PAN} and Aadhaar {AADHAAR} before approval.",
    "Send the invoice to {EMAIL} and keep the card {CREDIT_CARD} on file.",
    "{PERSON} asked us to update the phone number to {PHONE}.",
    "Mrs. {PERSON} lives at PIN code {PIN_CODE}. Her IFSC is {IFSC}.",
    "My name is {PERSON} and my account no. {BANK_ACCOUNT} was debited by mistake.",
]
DECOY_TEMPLATES = [
    "Your order {DECOY_ORDER} has shipped. Track it with {DECOY_TRACK}.",
    "Complaint ID {DECOY_ORDER} was logged; call our helpline {DECOY_PHONELIKE}.",
    "Product code {DECOY_CODE} is out of stock. Ticket {DECOY_TICKET} is open.",
    "Hello, my name is {PERSON}. Reference {DECOY_ORDER}, please call {PHONE}.",
    "Invoice {DECOY_TRACK} is pending for {EMAIL}.",
    "Mr. {PERSON}, your shipment {DECOY_TRACK} is delayed. Code {DECOY_CODE}.",
]
PLAIN = [
    "The app crashes when I open settings after version 4.2.1.",
    "Please share the meeting notes by Friday and confirm the budget of 25000 rupees.",
    "We shipped 120 units in September and expect 150 in October.",
]
SIGN_OFFS = ["\nThanks,\n{FIRSTNAME}", "\nRegards, {FIRSTNAME}"]


def render(template: str, gens: dict, base: int) -> tuple[str, list[dict], list[dict]]:
    text, gold, decoys = "", [], []
    for part in re.split(r"(\{[A-Z_]+\})", template):
        slot = part[1:-1] if part.startswith("{") and part.endswith("}") else None
        if slot is None:
            text += part
            continue
        value = gens[slot]()
        span = {"start": base + len(text), "end": base + len(text) + len(value)}
        if slot.startswith("DECOY"):
            decoys.append({"kind": slot, **span})
        else:
            gold.append({"type": GOLD_TYPE.get(slot, slot), **span})
        text += value
    return text, gold, decoys


def build(n: int = 300, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        ctx: dict = {}
        gens = make_generators(rng, ctx)
        roll = rng.random()
        if roll < 0.62:
            templates = rng.sample(PII_TEMPLATES, rng.choice([1, 2]))
            if rng.random() < 0.3:
                templates.append(rng.choice(SIGN_OFFS))
        elif roll < 0.9:
            templates = [rng.choice(DECOY_TEMPLATES), rng.choice(PII_TEMPLATES)]
        else:
            templates = [rng.choice(PLAIN)]
        text, gold, decoys = "", [], []
        for t in templates:
            sep = "" if not text else ("\n" if t.startswith("\n") or t.startswith("Customer Name") else " ")
            if sep:
                text += sep
            piece, g, d = render(t, gens, len(text))
            text += piece
            gold += g
            decoys += d
        rows.append({"id": f"s{i:03d}", "text": text, "entities": gold, "decoys": decoys})
    return rows


if __name__ == "__main__":
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} samples, {sum(len(r['entities']) for r in rows)} gold entities, "
          f"{sum(len(r['decoys']) for r in rows)} decoys -> {OUT}")
