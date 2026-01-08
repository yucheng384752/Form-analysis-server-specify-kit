import re

pattern = re.compile(r'(\d{7}_\d{2})|(\d{9})')
test_str = "2507313 02 19"
test_str_modified = "2507313_02 19"

print(f"Original '{test_str}': {bool(pattern.search(test_str))}")
print(f"Modified '{test_str_modified}': {bool(pattern.search(test_str_modified))}")
