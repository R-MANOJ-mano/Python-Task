import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

INPUT_FILE = "input.csv"
CLEANED_FILE = "cleaned.csv"
REPORT_FILE = "report.json"

VALID_STATUSES = ["paid", "pending", "cancelled", "refund"]

STATUS_ALIASES = {
    "canceled": "cancelled",
    "refunded": "refund",
    "completed": "paid",
}

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]


def clean_name(name):
    # remove extra spaces and fix capitals: " meera   NAIR " -> "Meera Nair"
    return " ".join(name.split()).title()


def clean_date(value):
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def clean_amount(value):
    # When both separators occur, the last one is the decimal separator:
    # "1,470.00" -> "1470.00" and "1.470,00" -> "1470.00".
    value = value.strip()
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        grouping_separator = "," if decimal_separator == "." else "."
        value = value.replace(grouping_separator, "").replace(decimal_separator, ".")
    else:
        value = value.replace(",", "")
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def clean_status(value):
    value = value.strip().lower()
    value = STATUS_ALIASES.get(value, value)
    if value in VALID_STATUSES:
        return value
    return None


def main():
    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    cleaned_rows = []
    seen_ids = {}       # transaction_id -> line where we first saw it
    seen_payments = {}  # (name, date, amount, status) -> line where we first saw it

    for line, row in enumerate(rows, start=2):  # line 1 is the header
        issues = []

        tx_id = row["transaction_id"].strip()
        name = clean_name(row["customer_name"])
        date = clean_date(row["transaction_date"])
        amount = clean_amount(row["amount"])
        status = clean_status(row["status"])

        if not name:
            issues.append("missing customer name")

        if date is None:
            issues.append("bad date: " + row["transaction_date"])

        if row["amount"].strip() in ("", "N/A"):
            issues.append("missing amount")
        elif amount is None:
            issues.append("amount is not a number: " + row["amount"])
        elif amount <= 0:
            issues.append("amount must be more than 0")

        if status is None:
            issues.append("unknown status: " + row["status"].strip())
        duplicate = ""
        if tx_id in seen_ids:
            duplicate = "repeated id"
            issues.append(f"duplicate id (first seen on line {seen_ids[tx_id]})")
        else:
            seen_ids[tx_id] = line

        if not duplicate and name and date and amount:
            key = (name, date, amount, status)
            if key in seen_payments:
                duplicate = "same transaction"
                issues.append(f"duplicate of line {seen_payments[key]}")
            else:
                seen_payments[key] = line

        cleaned_rows.append({
            "line": line,
            "transaction_id": tx_id,
            "original_name": row["customer_name"],
            "customer_name": name,
            "original_amount": row["amount"],
            "amount": amount if amount is not None else "",
            "original_date": row["transaction_date"],
            "date": date or "",
            "original_status": row["status"],
            "status": status or "unknown",
            "order_id": row["order_id"].strip(),
            "valid": "no" if issues else "yes",
            "duplicate": duplicate,
            "issues": "; ".join(issues),
        })

    
    with open(CLEANED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cleaned_rows[0].keys())
        writer.writeheader()
        writer.writerows(cleaned_rows)

    valid_rows = [r for r in cleaned_rows if r["valid"] == "yes"]
    repeated_ids = [r for r in cleaned_rows if r["duplicate"] == "repeated id"]
    same_txn = [r for r in cleaned_rows if r["duplicate"] == "same transaction"]
    revenue = sum(r["amount"] for r in valid_rows if r["status"] == "paid")

    report = {
        "input_rows": len(cleaned_rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(cleaned_rows) - len(valid_rows),
        "duplicates": {
            "repeated_transaction_id": len(repeated_ids),
            "same_transaction_entered_twice": len(same_txn),
            "total": len(repeated_ids) + len(same_txn),
        },
        "total_revenue": float(revenue),
        "revenue_rule": "sum of amount for valid rows with status 'paid'",
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
