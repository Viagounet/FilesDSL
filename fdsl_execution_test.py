from filesdsl import execute_fdsl

code = """
docs = Directory("office_samples")
pdfs = docs.search(".*\\.pdf$", scope="name")
print(len(docs))
print("=== LLM PAPER SEARCH + SHORT SUMMARY ===")
terms = ["a",
    "b", 
    "c", 
    "d"]
print(docs.tree())
for term in terms:
    print(term)
for file in pdfs:
    print(file.semantic_search("LLM"))
#     if file.contains("\\bLLM(s)?\\b|large language model(s)?", ignore_case=true):
#         print("")
#         print("FILE:", file)
#         print("SUMMARY_HINT_TOPICS:")
#         print(file.table(max_items=6))
#         print("SUMMARY_HINT_SNIPPET:")
#         print(file.snippets("\\bLLM(s)?\\b|large language model(s)?", max_results=1, ignore_case=true))
print(File("another_folder/2405.00332v3.pdf").read(pages=[1:10]))
"""

history = execute_fdsl(code, cwd="data", sandbox_root=".")
print(history)
