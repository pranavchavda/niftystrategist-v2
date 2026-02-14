
def format_inr(amount):
    try:
        s, *d = str(amount).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return "".join([r] + d)
    except:
        return str(amount)

# Test cases
cases = [
    (1000000, "10,00,000"),
    (1234567.89, "12,34,567.89"),
    (1000, "1,000"),
    (100, "100"),
    (10000000, "1,00,00,000")
]

all_passed = True
for val, expected in cases:
    # Handle float partition slightly differently in test vs implementation if not careful with string conversion
    # Implementation uses str(amount)
    
    # For float test cases, ensure we're testing the logic correctly
    if isinstance(val, float):
        result = format_inr(val)
    else:
        result = format_inr(val)
        
    if result == str(expected):
        print(f"PASS: {val} -> {result}")
    else:
        print(f"FAIL: {val} -> {result} (Expected {expected})")
        all_passed = False

if all_passed:
    print("\nAll formatting tests passed!")
else:
    print("\nSome tests failed.")
