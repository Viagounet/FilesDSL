from filesdsl import execute_fdsl

code = """
docs = Directory("data")
pdfs = docs.search(".*\\.pdf$", scope="name")

print("=== LLM PAPER SEARCH + SHORT SUMMARY ===")
for file in pdfs:
    if file.contains("\\bLLM(s)?\\b|large language model(s)?", ignore_case=true):
        print("")
        print("FILE:", file)
        print("SUMMARY_HINT_TOPICS:")
        print(file.table(max_items=6))
        print("SUMMARY_HINT_SNIPPET:")
        print(file.snippets("\\bLLM(s)?\\b|large language model(s)?", max_results=1, ignore_case=true))
"""

history = execute_fdsl(code, cwd=".", sandbox_root=".")
print(history)
