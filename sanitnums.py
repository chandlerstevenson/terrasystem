def sanitize_phone_number(phone_number: str) -> str:
    """Remove the +1 prefix from US phone numbers"""
    if phone_number.startswith("+1"):
        return phone_number[2:]
    return phone_number

# Test cases to validate the function
test_numbers = [
    "+14047133808",
    "+16787085808",
    "+19178610479",
    "4047133808",
    "6787085808",
    "9178610479"
]

for number in test_numbers:
    print(f"Original: {number} -> Sanitized: {sanitize_phone_number(number)}")
