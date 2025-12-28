---
description: Proceso de desarrollo y release para SolarPool AI
---

# Workflow de Desarrollo - SolarPool AI

## 1. Durante el Desarrollo

### Código
- [ ] Documentar funciones con docstrings claros (qué hace, args, returns)
- [ ] Usar type hints en Python
- [ ] Loguear decisiones importantes con `_LOGGER`

### Traducciones
- [ ] Si agregás texto visible al usuario → agregarlo a TODOS los archivos en `translations/`
  - `translations/en.json` (obligatorio)
  - `translations/es.json`
  - `translations/pt-BR.json`
  - `translations/fr.json`
  - `translations/de.json`
- [ ] Config flow labels van en `config.step.*` y `options.step.*`
- [ ] Textos del sistema van en `solarpool.*`

---

## 2. Antes de Commitear

### Checklist Pre-Commit
- [ ] ¿Todas las traducciones están actualizadas?
- [ ] ¿Las funciones tienen docstrings?
- [ ] ¿El código tiene type hints?

### Commit (SIN crear versión nueva)
// turbo
```bash
git add -A && git status
```

```bash
git commit -m "feat: Descripción concisa del cambio"
```

> ⚠️ NO modificar `manifest.json` version ni crear tags todavía

---

## 3. Antes del Release

### Revisar README.md
- [ ] ¿Hay que documentar nuevas funcionalidades?
- [ ] ¿Hay que actualizar la sección de Configuración?
- [ ] ¿Hay que agregar entrada en el Historial de Versiones?

### Verificar archivos modificados
// turbo
```bash
git log --oneline -5
git diff --stat HEAD~3
```

---

## 4. Crear Release (cuando el usuario lo pida)

### Ejecutar script de release
```bash
./release.sh X.Y.Z "Descripción breve del release"
```

**Ejemplo:**
```bash
./release.sh 0.0.7 "Agregado soporte para sensor de humedad"
```

El script automáticamente:
1. Actualiza la versión en `manifest.json`
2. Hace commit y push
3. Crea el tag
4. Crea el GitHub Release (si `gh` está instalado)

---

## Estructura de Archivos Clave

```
custom_components/solarpool_ai/
├── manifest.json          # Versión del componente
├── const.py               # Constantes y configuración
├── config_flow.py         # UI de configuración
├── coordinator.py         # Lógica principal
├── translations.py        # Helper para leer traducciones
├── translations/          # Archivos JSON de traducción
│   ├── en.json
│   ├── es.json
│   ├── pt-BR.json
│   ├── fr.json
│   └── de.json
└── ...
```

---

## Convenciones de Commits

| Prefijo | Uso |
|---------|-----|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de bug |
| `docs:` | Solo documentación |
| `refactor:` | Refactorización sin cambio funcional |
| `chore:` | Mantenimiento (deps, configs) |
