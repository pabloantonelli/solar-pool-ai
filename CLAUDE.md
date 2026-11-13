# SolarPool AI — memoria técnica

Integración custom de Home Assistant (HACS) que maneja la bomba de una pileta con colectores solares.
**La misma bomba filtra y calienta**: SolarPool nunca apaga una bomba que no prendió él (ownership).
Todo es local: no usa APIs externas ni dependencias (`requirements: []`, sin numpy desde v0.1.0).

## Mapa de archivos (`custom_components/solarpool_ai/`)
| Archivo | Rol |
|---|---|
| `coordinator.py` | **Núcleo.** Máquina de estados, timers, control de la bomba, persistencia (Store), protecciones y detección de problemas. |
| `rl_agent.py` | Bandit contextual WAIT/SWEEP ("¿vale la pena barrer ahora?") + °C/h aprendido por estado. Python puro, testeable sin HA. |
| `explanation_templates.py` | Textos de razonamiento (elige el template según el contexto). |
| `translations.py` | Lee `messages/<idioma>.json` (clave `solarpool.*`) con fallback de idioma. |
| `const.py` | Todas las claves de config, defaults, estados, modos, códigos de problema y parámetros de ajuste. |
| `config_flow.py` | Alta (entidades + parámetros) y options flow. `VERSION 1`, `MINOR_VERSION 2`. |
| `entity.py` | `SolarPoolEntity` (base con `has_entity_name` + `translation_key`) y `solarpool_device_info`. |
| `sensor.py`, `binary_sensor.py`, `switch.py`, `number.py`, `select.py`, `button.py` | Entidades. |
| `messages/*.json` | Textos propios (estados, status, templates, problemas). |
| `translations/*.json` | Solo lo estándar de HA: `config`, `options`, `entity`. |

## Flujo de control (v0.1.0)
```
tick lento (cada scan_interval, default 10 min)          tick rápido (cada 60 s, siempre)
  ├─ si estado ∈ ACTIVE_PUMP_STATES → no hace nada         ├─ problemas (sensores caídos, bomba que no responde)
  ├─ prerequisitos: sol ≥ 5°, pileta < max_temp            ├─ HEATING → _async_check_heating (ΔT con histéresis)
  ├─ modo vacaciones → IDLE                                ├─ antiheladas (_async_handle_frost)
  ├─ decisión: force / boost / bomba ya prendida → SWEEP   └─ enfriamiento nocturno (_async_handle_night_cooling)
  │            si no, rl_agent.get_action(contexto clima)
  │            WAIT pero >60 min sin barrer → SWEEP
  ├─ WAIT → estado WAITING
  └─ SWEEP → _async_start_sweep
```
- **Barrido** (`_async_check_sweep_stability`): primer chequeo a los 30 s, después cada 15 s. Es estable si, con ≥60 s y ≥3 lecturas, el rango (máx − mín) del retorno es < 0.2 °C. Timeout: `sweep_duration`.
- **Evaluación** (`_async_evaluate_sweep`): ΔT = retorno − pileta. Si ΔT ≥ `delta_on` (2.0), pasa a HEATING sin duración fija. Si no, cierra la sesión como `low_delta` y libera la bomba.
- **HEATING**: cada 60 s toma la mediana de las últimas 3 lecturas de ΔT. Corta tras 3 lecturas seguidas < `delta_off` (1.0; siempre ≥0.2 por debajo de `delta_on`). También corta por `max_temp`, sol bajo o modo vacaciones.
- **Liberar la bomba** (`_async_release_pump`): respeta `DEFAULT_MIN_RUN_TIME` (10 min desde que la prendimos), usando `_off_timer`.
- **Sesión** (`self._session`, persistida) = barrido + calentamiento. `_async_end_session` calcula la recompensa y llama a `rl_agent.update(state, action, reward)` con el estado/acción **guardados en la sesión** (atribución explícita). Outcomes posibles: `heated` / `low_delta` / `aborted` (no se aprende).
- **Recompensa**: barrido sin calentar = −0.1; calentó = ganancia real (pileta al cerrar − pileta al empezar a calentar) − 0.05 por hora de bomba. Las sesiones con la bomba ya prendida por filtrado no se aprenden (`learn=False`).
- **Estados**: idle, waiting, sweeping, measuring, heating, cooldown (pileta ≥ máx), cooling (enfriamiento nocturno), frost (antiheladas), error.

## Ownership de la bomba (crítico: la bomba también filtra)
- `_async_pump(True)`: si ya estaba ON, la usa **sin** tomar propiedad. Si estaba OFF, la prende y queda `_pump_started_by_us=True`.
- `_async_pump(False)`: solo apaga si `_pump_started_by_us`.
- `pump_owned` se persiste. Al reiniciar (`_async_resume_after_restart`): si era nuestra y seguimos de día calentando, se retoma; si no, se apaga.
- Listener del estado de la bomba (`_async_pump_changed`): si alguien la apaga mientras la usamos, la sesión pasa a `aborted` y se vuelve a IDLE sin pelear. `_expected_pump_state` distingue nuestros comandos de los externos.
- Al descargar o recargar la entry (`async_stop`): se cancelan todos los timers, se apaga la bomba si es nuestra y se guarda el Store.

## Persistencia — dónde vive cada dato
| Dato | Dónde |
|---|---|
| Entidades (bomba, sensores, weather) | `entry.data` (alta) |
| Parámetros (max_temp, sweep, intervalo, idioma, sensores opcionales, delta_on/off, antiheladas, enfriamiento) | `entry.options` (options flow, entidades number/switch). **Leer siempre con `coordinator._conf(key, default)`** (options → data → default; un `None` explícito en options = borrado). |
| RL (Q 108×2, counts, gain_rate, episodios), historial (50 sesiones), sesión en curso, pump_owned, modo, seguimiento diario, last_sweep | `Store` → `.storage/solarpool_ai.<entry_id>` (`async_delay_save`, 5 s) |
| Switch Master | `RestoreEntity` |

El options flow **mergea** con las options existentes, para no pisar lo que escriben los numbers y switches.
Los cambios de options llegan por `update_listener` → `coordinator.async_options_updated()` (intervalo e idioma, sin recargar).

## Contexto climático (`_gather_context`)
- UV: sensor → atributo `uv_index` del weather → estimación `12·sin(elevación)`. Un 0 real es válido.
- Penalización por nubes (salvo si el UV es estimado): `uv × max(0.15, 1 − 0.85·nubes/100)`.
- Viento y temperatura ambiente: sensor → atributo del weather.
- `solar_hour_offset`: horas respecto del mediodía solar, a partir de `sun.sun.next_noon` (fallback: `rising`).
- Estado RL = UV(4) × viento(3) × elevación(3) × hora solar(3). ΔT no entra, porque no se conoce antes de barrer.

## Modos y protecciones
- `select mode`: `auto` | `boost` (barre en cada tick; vuelve a auto al atardecer, en `_on_night`) | `vacation` (no calienta; las protecciones siguen activas).
- Switch Master OFF = apagado total, incluidas las protecciones.
- Antiheladas (switch config, OFF por defecto): si el ambiente baja de `frost_threshold`, circula 10 min cada 30. Sale con umbral + 1 °C.
- Enfriamiento nocturno (switch config, OFF por defecto): de noche, si la pileta supera máx + 1 y el ambiente está por debajo de pileta − 3, circula en bloques de 30 min hasta que la pileta llega a ≤ máx.
- `binary_sensor problem`: códigos `PROBLEM_*` en `const.py`, con textos en `messages/*/problems`. Cada problema nuevo dispara el evento `solarpool_ai_problem`.
- Evento `solarpool_ai_session_ended` (gain, heating_minutes, pump_minutes, daily_gain) al terminar cada sesión que calentó.

## Gotchas
- **`translations/` lo valida HA**: solo puede tener `config`, `options` y `entity`. Nada de listas ni claves propias, porque si no la integración no carga (bug de la v0.0.9). Los textos propios van en `messages/`.
- Las entidades originales tienen nombres fijos (`_attr_name`) para no cambiar los entity_id de instalaciones existentes. Las nuevas usan `translation_key`, así que hay que agregarlas en `translations/*.json` → `entity`, en los 5 idiomas.
- Ícono: `brand/icon.png` + `icon@2x.png` (HA 2026.3+).
- Para agregar un texto visible: tiene que ir en los 5 idiomas (`es`, `en`, `pt-BR`, `fr`, `de`). `es-ar` y `es-es` usan `es.json`.
- `daily_gain` se actualiza solo con lecturas tomadas con la bomba en marcha (con la bomba apagada, el sensor in-line no es confiable).

## Tests
```bash
uv venv --python 3.13 .venv-test && uv pip install --python .venv-test/bin/python -r requirements_test.txt
.venv-test/bin/python -m pytest tests -q
```
(`.venv` es otro entorno del usuario, Python 3.9: no tocarlo.) En los tests, la bomba es un `input_boolean` con servicios simulados, porque el componente `switch` real pisaría los mocks. Para el tiempo se usa el fixture `advance` (freezer + `async_fire_time_changed` en pasos de 15 s).

## Release
- Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`. No tocar la versión de `manifest.json` en commits normales.
- Release (solo cuando lo pida el usuario): `./release.sh X.Y.Z "descripción"`. El script actualiza el manifest, commitea, pushea, crea el tag y el GitHub release.
- Antes del release: actualizar el historial de versiones del README y este archivo si cambió la arquitectura.
