from filesdsl import execute_fdsl

code = """
docs = Directory(".")
pdfs = docs.search(".*\\.pdf$", scope="name")
filename="presentation_generale_rbpp_sante_mineurs_jeunes_majeurs.pdf"
file = File(filename)
print(file.search("santé"))
"""

history = execute_fdsl(code, cwd="data", sandbox_root=".", timeout_s=30)
print(history)
print(len(history))
