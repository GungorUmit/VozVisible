@app.route("/api/whatsapp")
def get_whatsapp():
    # Simulador (Mock) del Canal Oficial de WhatsApp para Cercanías Madrid
    import time
    now = int(time.time())
    messages = [
        {
            "id": "wa_1",
            "texto": "🚆 Línea C5\n\n🟡 Los trenes, sentido Fuenlabrada-Humanes, están sufriendo demoras, detenciones y pueden ver variado su recorrido habitual.\n\n⚠️ Avería de un tren en la estación de Doce de Octubre.",
            "timestamp": now - 300,
            "es_madrid": True
        },
        {
            "id": "wa_2",
            "texto": "📢 ACTUALIZACIÓN\n\n🚆 Línea C-5\n\n✅ Una vez retirado el tren de la estación de Doce de Octubre. Los trenes recuperan sus frecuencias de paso de forma progresiva.",
            "timestamp": now - 1800,
            "es_madrid": True
        },
        {
            "id": "wa_3",
            "texto": "🚆 Líneas C-2 / C-7 / C-8\n\n🟡 Los trenes, sentido Atocha-Chamartín, sufren demoras, detenciones y pueden ver modificado su recorrido habitual.\n\n⚠️ Avería de un tren en la estación de Vallecas.",
            "timestamp": now - 3600,
            "es_madrid": True
        },
        {
            "id": "wa_4",
            "texto": "🚆 Línea C-1\n\n🔴 Tren con salida de Chamartín a las 17:28h y llegada a Aeropuerto T4 a las 17:35h, hoy, no circula.\n\nℹ️ Próximo tren con origen Chamartín y destino Aeropuerto T4, tiene prevista su salida a las 17:35h, aproximadamente.\n\n⚠️ Reajuste del servicio.",
            "timestamp": now - 7200,
            "es_madrid": True
        }
    ]
    return jsonify({"messages": messages})

@app.route('/api/metro_x')
def get_metro_x():
    """Mock for Metro de Madrid X (Twitter) channel feed."""
    now = time.time()
    # Simulate some realistic Metro de Madrid tweets
    messages = [
        {
            "id": "x_1",
            "texto": "🔴 Circulación interrumpida en L6 entre las estaciones de Sainz de Baranda y Pacífico, en ambos sentidos, por asistencia sanitaria. Tiempo estimado de solución más de 15 minutos.",
            "timestamp": now - 600,
            "es_madrid": True
        },
        {
            "id": "x_2",
            "texto": "✅ Restablecido el servicio en L6 entre Sainz de Baranda y Pacífico. Los trenes vuelven a circular con normalidad.",
            "timestamp": now - 3600,
            "es_madrid": True
        },
        {
            "id": "x_3",
            "texto": "⚠️ Circulación lenta en L10 entre Tres Olivos y Begoña, sentido Puerta del Sur, por incidencia en las instalaciones.",
            "timestamp": now - 7200,
            "es_madrid": True
        }
    ]
    return jsonify({"messages": messages})

