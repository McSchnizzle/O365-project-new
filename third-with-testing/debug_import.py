# debug_import.py
import os
import sys

print("Current working directory:", os.getcwd())
print("Location of debug_import.py:", __file__)
print("\nsys.path:")
for p in sys.path:
    print(" -", p)

print("\nAttempting to import 'utils'...")
try:
    import utils
    print("Successfully imported 'utils'!")
except Exception as e:
    print("Error importing 'utils':", e)
