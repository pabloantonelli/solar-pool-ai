"""Translations and internationalization for SolarPool AI."""
from __future__ import annotations

from typing import Any
from .const import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

TRANSLATIONS: dict[str, dict[str, Any]] = {
    "es-ar": {
        "states": {
            "idle": "Inactivo",
            "sweeping": "Barriendo",
            "measuring": "Midiendo",
            "consulting": "Consultando",
            "heating": "Calentando",
            "cooldown": "Enfriando",
            "error": "Error",
        },
        "rl_phases": {
            "bootstrap": "Bootstrap (Reglas Seguras)",
            "training": "Entrenamiento (Aprendiendo)",
            "production": "Producción (Optimizado)",
        },
        "status_messages": {
            "initializing": "Inicializando...",
            "waiting_ha": "Esperando inicio de Home Assistant...",
            "sun_below_horizon": "Sol bajo el horizonte, sistema en reposo",
            "sun_too_low": "Sol muy bajo ({elevation:.1f}°), radiación insuficiente",
            "max_temp_reached": "Temp. pileta ({temp}°C) >= Máx ({max_temp}°C)",
            "sweep_starting": "Iniciando barrido para lectura de sensores...",
            "sweep_forced": "Iniciando barrido forzado...",
            "measuring_sensors": "Tomando medidas de sensores...",
            "consulting_ai": "Consultando IA para decisión térmica...",
            "sensor_error": "Error al recopilar datos de los sensores",
            "heating_complete": "Ciclo de calentamiento completado",
            "safety_override": "[Anulación] Delta real ({delta:.1f}°C) insuficiente (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Sol fuerte y viento calmo. ¡Aprovechamos al máximo!",
                "🔥 Condiciones perfectas para calentar. ¡Vamos con todo!",
                "💪 El techo está radiante, aprovechamos el calor.",
                "☀️ Día ideal: UV alto, poco viento. A calentar.",
            ],
            "on_marginal": [
                "🌤️ Condiciones regulares, vale intentar un rato.",
                "⚡ Hay algo de viento, pero el sol compensa. Probamos.",
                "🌤️ Nubes parciales, pero aún hay ganancia térmica.",
                "🤔 No es ideal, pero debería rendir algo.",
            ],
            "on_learning": [
                "🤖 Probando nueva estrategia. Después te cuento cómo salió.",
                "🧪 Explorando condiciones nuevas para aprender.",
                "📊 Recopilando datos para mejorar decisiones futuras.",
            ],
            "off_wind": [
                "💨 Viento de {wind:.0f}km/h enfría los colectores.",
                "🌬️ Mucho viento ({wind:.0f}km/h). Los colectores pierden calor.",
                "💨 El viento se lleva el calor más rápido de lo que entra.",
            ],
            "off_clouds": [
                "☁️ Muy nublado. La bomba gastaría más de lo que ganamos.",
                "🌧️ Día gris. Sin sol, no hay magia que hacer.",
                "☁️ Cielo cubierto. Mejor esperar a que despeje.",
            ],
            "off_delta": [
                "📉 Solo {delta:.1f}°C de diferencia. Necesitamos al menos 2°C.",
                "🌡️ Delta T muy bajo ({delta:.1f}°C). No rinde encender.",
                "📉 El agua del techo apenas está más caliente. No vale.",
            ],
            "off_low_sun": [
                "🌅 Sol muy bajo ({elevation:.0f}°). Radiación insuficiente.",
                "🌇 Atardecer. Ya no hay suficiente radiación.",
                "🌅 Sol bajo en el horizonte. Mejor mañana.",
            ],
            "off_low_uv": [
                "📉 UV muy bajo ({uv}). No hay suficiente radiación.",
                "🌫️ Radiación solar insuficiente (UV={uv}).",
            ],
            "warmup": [
                "🏋️ Sistema en fase de aprendizaje. Usando reglas seguras.",
                "📚 Aprendiendo patrones. Decisión conservadora por ahora.",
            ],
        },
    },
    "es-es": {
        "states": {
            "idle": "Inactivo",
            "sweeping": "Barriendo",
            "measuring": "Midiendo",
            "consulting": "Consultando",
            "heating": "Calentando",
            "cooldown": "Enfriando",
            "error": "Error",
        },
        "rl_phases": {
            "bootstrap": "Iniciación (Reglas Seguras)",
            "training": "Entrenamiento (Aprendiendo)",
            "production": "Producción (Optimizado)",
        },
        "status_messages": {
            "initializing": "Inicializando...",
            "waiting_ha": "Esperando el inicio de Home Assistant...",
            "sun_below_horizon": "Sol bajo el horizonte, sistema en reposo",
            "sun_too_low": "Sol muy bajo ({elevation:.1f}°), radiación insuficiente",
            "max_temp_reached": "Temp. piscina ({temp}°C) >= Máx ({max_temp}°C)",
            "sweep_starting": "Iniciando barrido para lectura de sensores...",
            "sweep_forced": "Iniciando barrido forzado...",
            "measuring_sensors": "Tomando medidas de sensores...",
            "consulting_ai": "Consultando IA para decisión térmica...",
            "sensor_error": "Error al recopilar datos de los sensores",
            "heating_complete": "Ciclo de calentamiento completado",
            "safety_override": "[Anulación] Delta real ({delta:.1f}°C) insuficiente (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Sol fuerte y viento calmado. ¡Aprovechemos al máximo!",
                "🔥 Condiciones perfectas para calentar. ¡Vamos a por ello!",
                "💪 El tejado está radiante, aprovechamos el calor.",
                "☀️ Día ideal: UV alto, poco viento. Hora de calentar.",
            ],
            "on_marginal": [
                "🌤️ Condiciones regulares, vale la pena intentarlo.",
                "⚡ Hay algo de viento, pero el sol compensa. Probamos.",
                "🌤️ Nubes parciales, pero aún hay ganancia térmica.",
                "🤔 No es ideal, pero debería rendir algo.",
            ],
            "on_learning": [
                "🤖 Probando nueva estrategia. Luego os cuento cómo ha ido.",
                "🧪 Explorando condiciones nuevas para aprender.",
                "📊 Recopilando datos para mejorar decisiones futuras.",
            ],
            "off_wind": [
                "💨 Viento de {wind:.0f}km/h enfria los colectores.",
                "🌬️ Mucho viento ({wind:.0f}km/h). Los colectores pierden calor.",
                "💨 El viento se lleva el calor más rápido de lo que entra.",
            ],
            "off_clouds": [
                "☁️ Muy nublado. La bomba gastaría más de lo que ganamos.",
                "🌧️ Día gris. Sin sol, no hay nada que hacer.",
                "☁️ Cielo cubierto. Mejor esperar a que despeje.",
            ],
            "off_delta": [
                "📉 Solo {delta:.1f}°C de diferencia. Necesitamos al menos 2°C.",
                "🌡️ Delta T muy bajo ({delta:.1f}°C). No compensa encender.",
                "📉 El agua del tejado apenas está más caliente. No vale la pena.",
            ],
            "off_low_sun": [
                "🌅 Sol muy bajo ({elevation:.0f}°). Radiación insuficiente.",
                "🌇 Atardecer. Ya no hay suficiente radiación.",
                "🌅 Sol bajo en el horizonte. Mejor mañana.",
            ],
            "off_low_uv": [
                "📉 UV muy bajo ({uv}). No hay suficiente radiación.",
                "🌫️ Radiación solar insuficiente (UV={uv}).",
            ],
            "warmup": [
                "🏋️ Sistema en fase de aprendizaje. Usando reglas seguras.",
                "📚 Aprendiendo patrones. Decisión conservadora por ahora.",
            ],
        },
    },
    "en": {
        "states": {
            "idle": "Idle",
            "sweeping": "Sweeping",
            "measuring": "Measuring",
            "consulting": "Consulting",
            "heating": "Heating",
            "cooldown": "Cooling down",
            "error": "Error",
        },
        "rl_phases": {
            "bootstrap": "Bootstrap (Safe Rules)",
            "training": "Training (Learning)",
            "production": "Production (Optimized)",
        },
        "status_messages": {
            "initializing": "Initializing...",
            "waiting_ha": "Waiting for Home Assistant to start...",
            "sun_below_horizon": "Sun below horizon, system resting",
            "sun_too_low": "Sun too low ({elevation:.1f}°), insufficient radiation",
            "max_temp_reached": "Pool temp ({temp}°C) >= Max ({max_temp}°C)",
            "sweep_starting": "Starting sweep for sensor readings...",
            "sweep_forced": "Starting forced sweep...",
            "measuring_sensors": "Taking sensor measurements...",
            "consulting_ai": "Consulting AI for thermal decision...",
            "sensor_error": "Error gathering sensor data",
            "heating_complete": "Heating cycle completed",
            "safety_override": "[Override] Actual delta ({delta:.1f}°C) insufficient (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Strong sun, calm wind. Let's heat up!",
                "🔥 Perfect conditions. Going full power!",
                "💪 Roof is radiating. Capturing the heat.",
                "☀️ Ideal day: high UV, low wind. Heating time.",
            ],
            "on_marginal": [
                "🌤️ Fair conditions, worth a try.",
                "⚡ Some wind, but sun compensates. Let's try.",
                "🌤️ Partial clouds, but still some thermal gain.",
                "🤔 Not ideal, but should get some gain.",
            ],
            "on_learning": [
                "🤖 Testing new strategy. I'll report back.",
                "🧪 Exploring new conditions to learn.",
                "📊 Gathering data to improve future decisions.",
            ],
            "off_wind": [
                "💨 {wind:.0f}km/h wind cools the collectors.",
                "🌬️ Too much wind ({wind:.0f}km/h). Heat escapes.",
                "💨 Wind carries heat away faster than it comes in.",
            ],
            "off_clouds": [
                "☁️ Too cloudy. Pump would waste more than we gain.",
                "🌧️ Gray day. No sun, no magic.",
                "☁️ Sky covered. Better wait for clear skies.",
            ],
            "off_delta": [
                "📉 Only {delta:.1f}°C difference. Need at least 2°C.",
                "🌡️ Delta T too low ({delta:.1f}°C). Not worth it.",
                "📉 Roof water barely warmer. Not worth running.",
            ],
            "off_low_sun": [
                "🌅 Sun too low ({elevation:.0f}°). Insufficient radiation.",
                "🌇 Sunset approaching. Not enough radiation left.",
                "🌅 Sun low on horizon. Better tomorrow.",
            ],
            "off_low_uv": [
                "📉 UV too low ({uv}). Not enough radiation.",
                "🌫️ Solar radiation insufficient (UV={uv}).",
            ],
            "warmup": [
                "🏋️ System in learning phase. Using safe rules.",
                "📚 Learning patterns. Conservative decision for now.",
            ],
        },
    },
    "pt-br": {
        "states": {
            "idle": "Inativo",
            "sweeping": "Limpando",
            "measuring": "Medindo",
            "consulting": "Consultando",
            "heating": "Aquecendo",
            "cooldown": "Resfriando",
            "error": "Erro",
        },
        "rl_phases": {
            "bootstrap": "Bootstrap (Regras Seguras)",
            "training": "Treinamento (Aprendendo)",
            "production": "Produção (Otimizado)",
        },
        "status_messages": {
            "initializing": "Inicializando...",
            "waiting_ha": "Aguardando início do Home Assistant...",
            "sun_below_horizon": "Sol abaixo do horizonte, sistema em repouso",
            "sun_too_low": "Sol muito baixo ({elevation:.1f}°), radiação insuficiente",
            "max_temp_reached": "Temp. piscina ({temp}°C) >= Máx ({max_temp}°C)",
            "sweep_starting": "Iniciando limpeza para leitura dos sensores...",
            "sweep_forced": "Iniciando limpeza forçada...",
            "measuring_sensors": "Coletando dados dos sensores...",
            "consulting_ai": "Consultando IA para decisão térmica...",
            "sensor_error": "Erro ao coletar dados dos sensores",
            "heating_complete": "Ciclo de aquecimento concluído",
            "safety_override": "[Substituir] Delta real ({delta:.1f}°C) insuficiente (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Sol forte e vento calmo. Vamos aproveitar ao máximo!",
                "🔥 Condições perfeitas para aquecer. Vamos com tudo!",
                "💪 O telhado está radiante, aproveitando o calor.",
                "☀️ Dia ideal: UV alto, pouco vento. Hora de aquecer.",
            ],
            "on_marginal": [
                "🌤️ Condições regulares, vale a pena tentar.",
                "⚡ Um pouco de vento, mas o sol compensa. Vamos testar.",
                "🌤️ Nuvens parciais, mas ainda há ganho térmico.",
                "🤔 Não é o ideal, mas deve render algo.",
            ],
            "on_learning": [
                "🤖 Testando nova estratégia. Depois conto como foi.",
                "🧪 Explorando novas condições para aprender.",
                "📊 Coletando dados para melhorar decisões futuras.",
            ],
            "off_wind": [
                "💨 Vento de {wind:.0f}km/h resfria os coletores.",
                "🌬️ Muito vento ({wind:.0f}km/h). Os coletores perdem calor.",
                "💨 O vento leva o calor mais rápido do que ele entra.",
            ],
            "off_clouds": [
                "☁️ Muito nublado. A bomba gastaria mais do que ganharíamos.",
                "🌧️ Dia cinzento. Sem sol, sem mágica.",
                "☁️ Céu coberto. Melhor esperar limpar.",
            ],
            "off_delta": [
                "📉 Apenas {delta:.1f}°C de diferença. Precisamos de pelo menos 2°C.",
                "🌡️ Delta T muito baixo ({delta:.1f}°C). Não vale a pena ligar.",
                "📉 A água do telhado mal está mais quente. Não compensa.",
            ],
            "off_low_sun": [
                "🌅 Sol muito baixo ({elevation:.0f}°). Radiação insuficiente.",
                "🌇 Entardecer. Não há mais radiação suficiente.",
                "🌅 Sol baixo no horizonte. Melhor amanhã.",
            ],
            "off_low_uv": [
                "📉 UV muito baixo ({uv}). Não há radiação suficiente.",
                "🌫️ Radiação solar insuficiente (UV={uv}).",
            ],
            "warmup": [
                "🏋️ Sistema em fase de aprendizado. Usando regras seguras.",
                "📚 Aprendendo padrões. Decisão conservadora por enquanto.",
            ],
        },
    },
    "fr": {
        "states": {
            "idle": "Inactif",
            "sweeping": "Balayage",
            "measuring": "Mesure",
            "consulting": "Consultation",
            "heating": "Chauffage",
            "cooldown": "Refroidissement",
            "error": "Erreur",
        },
        "rl_phases": {
            "bootstrap": "Amorçage (Règles Sûres)",
            "training": "Entraînement (Apprentissage)",
            "production": "Production (Optimisé)",
        },
        "status_messages": {
            "initializing": "Initialisation...",
            "waiting_ha": "En attente du démarrage de Home Assistant...",
            "sun_below_horizon": "Soleil sous l'horizon, système au repos",
            "sun_too_low": "Soleil trop bas ({elevation:.1f}°), rayonnement insuffisant",
            "max_temp_reached": "Temp. piscine ({temp}°C) >= Max ({max_temp}°C)",
            "sweep_starting": "Démarrage du balayage pour la lecture des capteurs...",
            "sweep_forced": "Démarrage du balayage forcé...",
            "measuring_sensors": "Prise de mesures des capteurs...",
            "consulting_ai": "Consultation de l'IA pour la décision thermique...",
            "sensor_error": "Erreur lors de la collecte des données des capteurs",
            "heating_complete": "Cycle de chauffage terminé",
            "safety_override": "[Override] Delta réel ({delta:.1f}°C) insuffisant (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Soleil fort et vent calme. Profitons-en au maximum !",
                "🔥 Conditions parfaites pour chauffer. On y va à fond !",
                "💪 Le toit est rayonnant, on capture la chaleur.",
                "☀️ Journée idéale : UV élevé, peu de vent. C'est l'heure de chauffer.",
            ],
            "on_marginal": [
                "🌤️ Conditions moyennes, ça vaut le coup d'essayer.",
                "⚡ Un peu de vent, mais le soleil compense. On teste.",
                "🌤️ Nuages partiels, mais il y a encore un gain thermique.",
                "🤔 Pas idéal, mais ça devrait rapporter un peu.",
            ],
            "on_learning": [
                "🤖 Test d'une nouvelle stratégie. Je vous dirai ce qu'il en est.",
                "🧪 Exploration de nouvelles conditions pour apprendre.",
                "📊 Collecte de données pour améliorer les futures décisions.",
            ],
            "off_wind": [
                "💨 Un vent de {wind:.0f}km/h refroidit les collecteurs.",
                "🌬️ Trop de vent ({wind:.0f}km/h). Les collecteurs perdent de la chaleur.",
                "💨 Le vent emporte la chaleur plus vite qu'elle n'arrive.",
            ],
            "off_clouds": [
                "☁️ Trop nuageux. La pompe dépenserait plus qu'on ne gagne.",
                "🌧️ Journée grise. Pas de soleil, pas de magie.",
                "☁️ Ciel couvert. Mieux vaut attendre que ça se dégage.",
            ],
            "off_delta": [
                "📉 Seulement {delta:.1f}°C de différence. Il faut au moins 2°C.",
                "🌡️ Delta T trop bas ({delta:.1f}°C). Pas rentable d'allumer.",
                "📉 L'eau du toit est à peine plus chaude. Ça n'en vaut pas la peine.",
            ],
            "off_low_sun": [
                "🌅 Soleil trop bas ({elevation:.0f}°). Rayonnement insuffisant.",
                "🌇 Le soleil se couche. Plus assez de rayonnement.",
                "🌅 Soleil bas sur l'horizon. À demain.",
            ],
            "off_low_uv": [
                "📉 UV trop bas ({uv}). Pas assez de rayonnement.",
                "🌫️ Rayonnement solaire insuffisant (UV={uv}).",
            ],
            "warmup": [
                "🏋️ Système en phase d'apprentissage. Utilisation de règles sûres.",
                "📚 Apprentissage des modèles. Décision conservatrice pour l'instant.",
            ],
        },
    },
    "de": {
        "states": {
            "idle": "Inaktiv",
            "sweeping": "Spülen",
            "measuring": "Messen",
            "consulting": "Beraten",
            "heating": "Heizen",
            "cooldown": "Abkühlen",
            "error": "Fehler",
        },
        "rl_phases": {
            "bootstrap": "Initialisierung (Sicherheitsregeln)",
            "training": "Training (Lernen)",
            "production": "Produktion (Optimiert)",
        },
        "status_messages": {
            "initializing": "Initialisierung...",
            "waiting_ha": "Warten auf den Start von Home Assistant...",
            "sun_below_horizon": "Sonne unter dem Horizont, System im Ruhezustand",
            "sun_too_low": "Sonne zu tief ({elevation:.1f}°), unzureichende Strahlung",
            "max_temp_reached": "Pooltemp. ({temp}°C) >= Max ({max_temp}°C)",
            "sweep_starting": "Starte Spülvorgang für Sensormessungen...",
            "sweep_forced": "Starte erzwungenen Spülvorgang...",
            "measuring_sensors": "Sensormessungen werden durchgeführt...",
            "consulting_ai": "KI wird für thermische Entscheidung konsultiert...",
            "sensor_error": "Fehler beim Erfassen der Sensordaten",
            "heating_complete": "Heizzyklus abgeschlossen",
            "safety_override": "[Override] Aktuelles Delta ({delta:.1f}°C) unzureichend (<2.0°C)",
        },
        "templates": {
            "on_optimal": [
                "☀️ Starke Sonne, wenig Wind. Nutzen wir es voll aus!",
                "🔥 Perfekte Bedingungen zum Heizen. Los geht's!",
                "💪 Das Dach strahlt, wir fangen die Wärme ein.",
                "☀️ Idealer Tag: Hoher UV, wenig Wind. Zeit zum Heizen.",
            ],
            "on_marginal": [
                "🌤️ Durchschnittliche Bedingungen, einen Versuch wert.",
                "⚡ Etwas Wind, aber die Sonne gleicht es aus. Wir probieren es.",
                "🌤️ Leichte Bewölkung, aber immer noch Wärmegewinn.",
                "🤔 Nicht ideal, aber es sollte etwas bringen.",
            ],
            "on_learning": [
                "🤖 Teste neue Strategie. Ich werde berichten.",
                "🧪 Erforsche neue Bedingungen zum Lernen.",
                "📊 Sammle Daten zur Verbesserung zukünftiger Entscheidungen.",
            ],
            "off_wind": [
                "💨 {wind:.0f}km/h Wind kühlt die Kollektoren ab.",
                "🌬️ Zu viel Wind ({wind:.0f}km/h). Die Kollektoren verlieren Wärme.",
                "💨 Der Wind trägt die Wärme schneller weg, als sie reinkommt.",
            ],
            "off_clouds": [
                "☁️ Zu bewölkt. Die Pumpe würde mehr verbrauchen, als wir gewinnen.",
                "🌧️ Grauer Tag. Keine Sonne, keine Magie.",
                "☁️ Himmel bedeckt. Besser warten, bis es aufklart.",
            ],
            "off_delta": [
                "📉 Nur {delta:.1f}°C Differenz. Wir brauchen mindestens 2°C.",
                "🌡️ Delta T zu niedrig ({delta:.1f}°C). Einschalten lohnt sich nicht.",
                "📉 Das Wasser vom Dach ist kaum wärmer. Lohnt sich nicht.",
            ],
            "off_low_sun": [
                "🌅 Sonne zu tief ({elevation:.0f}°). Unzureichende Strahlung.",
                "🌇 Sonnenuntergang naht. Nicht mehr genug Strahlung.",
                "🌅 Sonne tief am Horizont. Besser morgen.",
            ],
            "off_low_uv": [
                "📉 UV zu niedrig ({uv}). Nicht genug Strahlung.",
                "🌫️ Sonnenstrahlung unzureichend (UV={uv}).",
            ],
            "warmup": [
                "🏋️ System in der Lernphase. Verwende Sicherheitsregeln.",
                "📚 Lerne Muster. Vorerst konservative Entscheidung.",
            ],
        },
    },
}


def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get a translated text string.
    
    Args:
        key: Dot-separated key path (e.g., "states.heating", "status_messages.initializing")
        language: Language code
        **kwargs: Format arguments for the string
        
    Returns:
        Translated and formatted string
    """
    if language not in SUPPORTED_LANGUAGES:
        # Check for partial matches (e.g., "es-ES" -> "es-es")
        language = language.lower()
        if language not in SUPPORTED_LANGUAGES:
            # Fallback to base language if specific variant not found
            base_lang = language.split("-")[0]
            if base_lang == "es":
                language = "es-ar" # Default Spanish
            elif base_lang in SUPPORTED_LANGUAGES:
                language = base_lang
            else:
                language = DEFAULT_LANGUAGE
    
    # Navigate the nested dictionary
    parts = key.split(".")
    value = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])
    
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part, key)
        else:
            return key
    
    # Format with kwargs if it's a string
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    
    return str(value) if value else key


def get_template(category: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get a random template from a category.
    
    Args:
        category: Template category (e.g., "on_optimal", "off_wind")
        language: Language code
        **kwargs: Format arguments for the template
        
    Returns:
        Random template from the category, formatted with kwargs
    """
    import random
    
    if language not in SUPPORTED_LANGUAGES:
        language = language.lower()
        if language not in SUPPORTED_LANGUAGES:
            base_lang = language.split("-")[0]
            if base_lang == "es":
                language = "es-ar"
            elif base_lang in SUPPORTED_LANGUAGES:
                language = base_lang
            else:
                language = DEFAULT_LANGUAGE
    
    lang_data = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])
    templates = lang_data.get("templates", {})
    category_templates = templates.get(category, [f"[{category}]"])
    
    if not category_templates:
        return f"[{category}]"
    
    template = random.choice(category_templates)
    
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    
    return template
