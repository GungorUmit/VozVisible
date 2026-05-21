# 🚀 Voz Visible: Traductor Automático a Lengua de Signos Española (LSE) con IA

![Voz Visible Banner](assets/vozvisible_banner.png)

## 📜 Definición del Proyecto

El **Proyecto Voz Visible (LSE)** es una solución tecnológica de vanguardia diseñada para eliminar las barreras de comunicación en el espacio público. Mediante el uso de **Inteligencia Artificial Multimodal**, el sistema automatiza la interpretación de mensajes acústicos y megafonía hacia la Lengua de Signos Española (LSE).

Nuestra misión es garantizar la accesibilidad universal y la autonomía de las personas sordas en entornos críticos como infraestructuras de transporte, edificios gubernamentales y servicios de emergencia, transformando anuncios sonoros en información visual comprensible en tiempo real.

---

## 🎯 Objetivos Estratégicos y Desarrollo

El proyecto se articula en torno a tres pilares fundamentales de desarrollo tecnológico:

### 1. Traducción Neuronal de Audio a Glosa Visual (En Integración)
* **Desarrollo:** Implementación de un motor de procesamiento de lenguaje natural (NLP) que traduzca el castellano oral a la estructura gramatical y sintáctica de la LSE (glosas). Actualmente el equipo se encuentra integrando el módulo ASR y traducción neuronal para conectar directamente el audio con nuestra base visual.
* **Hito:** Asegurar una fidelidad semántica superior al 90%, evitando traducciones literales que carezcan de sentido para la comunidad sorda.

### 2. Procesamiento en Streaming de Baja Latencia (MVP Implementado)
* **Desarrollo:** Optimización del flujo de datos (*pipeline*) que abarca desde el texto/reconocimiento hasta el renderizado de vídeo de forma asíncrona mediante **Celery**, **Redis** y **OpenCV**.
* **Hito:** Lograr un tiempo de respuesta (*delay*) inferior a 3-5 segundos para renderizar al avatar 3D, permitiendo una interpretación casi simultánea para anuncios de última hora o alertas de seguridad.

### 3. Interfaz de Comunicación Bidireccional (Visión a Futuro)
* **Desarrollo:** Evolucionar el sistema hacia un modelo interactivo capaz de procesar no solo la salida de audio, sino también la entrada gestual del usuario mediante visión artificial.
* **Hito:** Facilitar el mantenimiento de conversaciones fluidas en tiempo real, permitiendo una comunicación hombre-máquina accesible y efectiva.

---

## 📊 Evaluación y Resultados (Dataset RADIS)

Evaluar un traductor de LSE no consiste en alcanzar un 100% de similitud textual, debido a la "elipsis masiva" propia de la lengua de signos (omisión de artículos y preposiciones) y a su estructura gramatical única.

* **Sentence-BLEU:** **8.85%**
* **Evaluación Cualitativa:** El sistema tiene un **100% de éxito de generación** para todas las alertas predefinidas de transporte en el dashboard.
* Evaluado por personas nativas en LSE, el veredicto cualitativo ha sido claro: *"Cualquier sordo lo puede entender perfectamente"*. 

Este rendimiento se sitúa sólidamente dentro de los márgenes académicos (5-15% BLEU) esperables para este tipo de traducción textual-visual, validando nuestra arquitectura frente a riesgos de *overfitting*.

---

## 🌍 Impacto Social

Este proyecto se alinea con los **Objetivos de Desarrollo Sostenible (ODS)** de la Agenda 2030:
* **ODS 10 (Reducción de las desigualdades):** Fomentando la inclusión social de personas con discapacidad auditiva.
* **ODS 11 (Ciudades sostenibles):** Proporcionando acceso a sistemas de transporte e información pública seguros y accesibles para todos.

---

## 🛠️ Instrucciones de Instalación y Uso

### Prerrequisitos
- Python 3.10
- Redis (corriendo localmente en el puerto 6379, db 1)

### Despliegue del Sistema
1. **Arrancar Redis** (si usas macOS/Linux o Docker):
   ```bash
   redis-server
   ```
2. **Iniciar el Worker de Celery** (Procesa los vídeos en segundo plano):
   ```bash
   celery -A tasks worker --loglevel=info
   ```
3. **Iniciar la Interfaz Web (Flask)**:
   ```bash
   python server.py
   ```
4. Abre el navegador en `http://localhost:5002` para interactuar con Voz Visible.

---

## 👥 El Equipo (Saturdays.AI 2026)
* Alonso Campos 
* Adrián Bisquert
* Abigail Masapanta 
* Gabriel Vidal
* Umit Gungor 

*#AccesibilidadDigital #LenguaDeSignos #IA #NLP #SaturdaysAI*
