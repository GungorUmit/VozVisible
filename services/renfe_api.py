import json
import re
from urllib.request import urlopen

RENFE_ALERTS_URL = "https://gtfsrt.renfe.com/alerts.json"

def get_renfe_alerts_data():
    """Obtiene y procesa las alertas GTFS-RT de Renfe en tiempo real."""
    try:
        with urlopen(RENFE_ALERTS_URL, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        alerts = []
        for entity in data.get("entity", []):
            alert = entity.get("alert", {})
            translations = alert.get("descriptionText", {}).get("translation", [])
            texto = ""
            for t in translations:
                if t.get("language") == "es":
                    texto = t.get("text", "")
                    break
            if not texto and translations:
                texto = translations[0].get("text", "")

            if not texto:
                continue

            # Detectar si es de Madrid
            es_madrid = "#Mad" in texto or "Madrid" in texto

            # Extraer línea(s) afectadas
            lineas = re.findall(r'#Mad(C\d+[a-z]?)', texto)

            # Limpiar hashtags del texto visible
            texto_limpio = re.sub(r'#\S+\s*', '', texto).strip()

            alerts.append({
                "id": entity.get("id", ""),
                "texto": texto_limpio,
                "lineas": lineas,
                "es_madrid": es_madrid,
                "timestamp": alert.get("activePeriod", [{}])[0].get("start", ""),
            })

        # Ordenar: Madrid primero
        alerts.sort(key=lambda x: (not x["es_madrid"], x["id"]))

        return {
            "success": True,
            "total": len(alerts),
            "timestamp": data.get("header", {}).get("timestamp", ""),
            "alerts": alerts
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "alerts": []
        }
