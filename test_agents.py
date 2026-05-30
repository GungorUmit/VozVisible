import os
from services.agents.orchestrator import run_multi_agent_pipeline
from server import get_encrypted_setting

def main():
    api_key = os.environ.get("GROQ_API_KEY") or get_encrypted_setting('groq_api_key')
    if not api_key:
        print("ERROR: No se encontró GROQ_API_KEY en el entorno ni en la base de datos.")
        return
        
    print("=== INICIANDO PRUEBA DE ARQUITECTURA MULTI-AGENTE ===")
    
    texto_prueba = "Ehhh, atención, fuego en la vía 2 de la estación de Sol. Evacuen inmediatamente."
    print(f"Texto original simulado (Operador estresado): '{texto_prueba}'")
    
    resultados = run_multi_agent_pipeline(texto_prueba, api_key)
    
    print("\n=== RESULTADOS FINALES ===")
    print(f"Texto Limpio (Agente Contexto): {resultados['clean_text']}")
    print(f"Glosas Aprobadas (Agente Lingüista + Auditor): {resultados['glosses']}")
    print(f"Velocidad (Agente Animador): {resultados['speed']}x")
    print("==================================================")

if __name__ == "__main__":
    main()
