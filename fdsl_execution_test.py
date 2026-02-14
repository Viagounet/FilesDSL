from filesdsl import execute_fdsl

code = """
docs = Directory("data")
files = docs.search(".*\\.pdf$", scope="name")
for file in files:
    print(file.head())
count = len(files)
print(count)
"""

history = execute_fdsl(code, cwd=".", sandbox_root=".")
print(history)
