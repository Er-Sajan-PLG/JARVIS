## v0.1

Created JARVIS
-Learned about architecture, system design, future proof(upgradability, localized debug)
-created virtual environment, 
-created core files and folders
-written core code for main.py for running JARVIS, importing model, created client.py in model for ollama
-edited settings.py
-git setup and commited and pushed


## v0.2

Built CLI loop for Jarvis.

Key learning:
- while loops are better for open-ended interaction
- client should be created once, not inside loop
- input/output flow must be sequential (input → process → output)

Mistakes:
- initially tried mixing assignment inside while condition
- confused loop condition with loop body logic