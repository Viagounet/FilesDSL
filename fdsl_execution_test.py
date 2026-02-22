from filesdsl import execute_fdsl

code = """
docs = Directory(".")
print(docs.semantic_search("Au-delà  des  ressources  directement  mobilisées  par  les  laboratoires  participants,  les  International Research Programmes bénéficient de la part du CNRS de crédits spécifiques principalement dédiés à la mobilité entre équipes et l’organisation de rencontres et missions de terrain d’un montant total se situant  entre  50 000  et  75 000  euros  sur  leur  durée."))
"""

history = execute_fdsl(code, cwd="data", sandbox_root=".", timeout_s=30)
print(history)
print(len(history))
