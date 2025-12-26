Especificación de Desarrollo: SolarPool AI (Home Assistant Custom Component)

1. Contexto y Objetivo

Desarrollar una Integración Personalizada (Custom Component) para Home Assistant que automatice la climatización de una piscina con colectores solares.
El sistema debe actuar como un agente autónomo que:

Controla la bomba de la piscina.

Realiza ciclos de "barrido" para obtener lecturas precisas de temperatura.

Consulta una IA (Google Gemini o Anthropic Claude) para decidir si mantener la calefacción activa basándose en eficiencia térmica y clima.

Expone su razonamiento y estado en el Dashboard de Home Assistant.

2. Stack Tecnológico

Lenguaje: Python 3.10+ (Tipado estricto mypy).

Framework: Home Assistant Core (Arquitectura de componentes).

Comunicación HTTP: aiohttp (Nativo de HA) para llamadas a APIs de IA. NO usar SDKs externos (como google-generativeai o anthropic) para mantener el componente ligero y evitar conflictos de dependencias. Usar llamadas REST directas.

Manejo de Datos: DataUpdateCoordinator para la gestión centralizada del estado.

3. Arquitectura del Componente

3.1 Estructura de Archivos Requerida

custom_components/solarpool_ai/
├── __init__.py           # Setup inicial y descarga de plataformas
├── manifest.json         # Metadatos
├── const.py              # Constantes globales
├── config_flow.py        # UI de configuración (Inputs y Selectores)
├── coordinator.py        # LÓGICA CENTRAL (Máquina de estados)
├── ai_client.py          # Clase abstracta + Implementaciones (Gemini/Anthropic)
├── sensor.py             # Sensores de estado y temperatura objetivo
├── binary_sensor.py      # Sensor de error
├── switch.py             # Switch maestro (Activar/Desactivar sistema)
├── text.py               # Entidad para mostrar el "Razonamiento" de la IA
└── services.yaml         # (Opcional) Servicios extra si fueran necesarios


3.2 Config Flow (Configuración de Usuario)

El usuario debe configurar lo siguiente mediante la UI de Home Assistant:

Paso 1: Configuración de IA

ai_provider: Selector (Gemini | Anthropic).

api_key: String (Password).

model_name: String (Default: "gemini-1.5-flash" o "claude-3-haiku").

Paso 2: Mapeo de Entidades (Entity Selectors)

pump_entity_id: Selector de switch (La bomba real).

pool_sensor_id: Selector de sensor (Temp. Agua).

return_sensor_id: Selector de sensor (Temp. Retorno colectores).

weather_entity_id: Selector de weather (Para nubes, viento, temp ext).

Paso 3: Parámetros

sweep_duration: Int (Segundos, default 180). Tiempo de barrido.

max_temp: Float (Grados, default 32.0). Corte de seguridad.

4. Lógica de Negocio (Coordinator)

El SolarPoolCoordinator debe implementar una Máquina de Estados Asíncrona. NO usar polling simple.

Estados

IDLE: Esperando el siguiente ciclo (ej. cada 30 min) o cambio de estado solar (día/noche).

SWEEPING (Barrido):

Problema: El sensor de retorno está a nivel de suelo. Si la bomba está apagada, mide frío aunque el techo esté caliente.

Acción: Encender bomba por sweep_duration segundos. Ignorar lecturas térmicas durante este tiempo.

MEASURING (Muestreo): Al terminar el barrido, tomar lecturas de los sensores mapeados.

CONSULTING (IA): Enviar JSON a la API seleccionada.

EXECUTING (Decisión):

Si IA = ON: Mantener bomba encendida.

Si IA = OFF: Apagar bomba.

COOLDOWN/SAFETY: Si T_Piscina > T_Max, forzar apagado.

Lógica de Disparo

El ciclo debe iniciarse automáticamente cada X minutos (configurable internamente, ej. 30 min) SOLO si el sol está sobre el horizonte (sun.sun).

5. Módulo de IA (ai_client.py)

Implementar una clase base AIClient y dos subclases: GeminiClient y AnthropicClient.

Método principal:
async def get_decision(self, context: dict) -> dict

Input Context (JSON):

{
  "t_pool": 26.5,
  "t_return": 31.2,
  "weather_state": "partlycloudy",
  "temperature_ext": 28.0,
  "wind_speed": 15.0,
  "uv_index": 5
}


System Prompt (Inyectado en cada llamada):
"Eres un controlador térmico de piscinas inteligente.
Objetivo: Maximizar ganancia térmica vs costo eléctrico.
Reglas:

Si (t_return - t_pool) < 2.0: ACTION=OFF (Ineficiente).

Si nubes > 80% o lluvia: ACTION=OFF.

Si viento alto (>25kmh) y ganancia baja: ACTION=OFF (Pérdida por convección).

Respuesta estricta JSON: {'action': 'ON'|'OFF', 'reason': 'Texto breve', 'target_delta': float}."

6. Entidades a Exponer

switch.solarpool_master:

Permite al usuario apagar toda la automatización manualmente.

sensor.solarpool_status:

Valor: Estado actual de la máquina (Idle, Sweeping, AI_Thinking, Heating).

text.solarpool_reasoning:

Valor: El campo reason devuelto por la IA (ej: "Viento alto y baja delta T, apagando para ahorrar").

Importante: Esto permite mostrar la explicación en el Dashboard.

sensor.solarpool_target_delta:

Valor: El delta T mínimo que la IA decidió exigir para este ciclo.

7. Manejo de Errores y Seguridad (Watchdogs)

Fallo de API: Si la llamada a la IA falla (Timeout/500), el sistema debe hacer un fallback a lógica simple: SI (Retorno - Piscina) > 4°C ENTONCES ON.

Reinicio de HA: En el __init__, verificar si la bomba quedó encendida por el sistema y apagarla si es necesario para reiniciar el estado a IDLE.

Protección de Ciclos Cortos: No apagar la bomba si lleva menos de 5 min encendida (excepto emergencia).

8. Instrucciones de Implementación para la IA Generativa

Comienza creando el manifest.json y const.py.

Implementa el config_flow.py usando homeassistant.helpers.selector.

Desarrolla ai_client.py usando aiohttp.

Implementa el núcleo coordinator.py con la lógica de barrido (Sweep).

Finalmente crea las entidades en sensor.py, switch.py, text.py.