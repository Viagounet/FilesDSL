from filesdsl import execute_fdsl

code = """
docs = Directory("data")
files = docs.search(".*\\.pdf$", scope="name")
count = len(files)
"""

result = execute_fdsl(code, cwd=".", sandbox_root=".")
print(result["count"])
