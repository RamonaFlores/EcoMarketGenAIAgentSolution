# scripts/agent_cli.py
from dotenv import load_dotenv
load_dotenv()

from src.agent.graph import run_agent

print("EcoMarket Agent • CLI")
print("Escribe tu mensaje (Ctrl+C para salir)\n")

while True:
    q = input("> ")
    out = run_agent(q)
    print("\nRespuesta:\n", out["answer"])
    if out.get("label_url"):
        print("Etiqueta:", out["label_url"])
    print("-"*60)