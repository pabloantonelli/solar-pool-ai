#!/bin/bash

# Script para automatizar el lanzamiento de versiones de SolarPool AI
# Uso: ./release.sh 1.0.1 "Descripción del cambio"

VERSION=$1
MESSAGE=$2
MANIFEST_PATH="custom_components/solarpool_ai/manifest.json"

if [ -z "$VERSION" ] || [ -z "$MESSAGE" ]; then
    echo "Uso: ./release.sh [versión] [mensaje]"
    echo "Ejemplo: ./release.sh 1.0.1 'Agregado logging de IA'"
    exit 1
fi

echo "🚀 Iniciando lanzamiento de la versión v$VERSION..."

# 1. Actualizar manifest.json usando sed (compatible con macOS e Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Versión macOS
    sed -i '' "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" "$MANIFEST_PATH"
else
    # Versión Linux
    sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" "$MANIFEST_PATH"
fi

echo "✅ manifest.json actualizado a la versión $VERSION"

# 2. Git flow
git add .
git commit -m "Release v$VERSION: $MESSAGE"
git push origin main

# 3. Tagging
echo "🏷️ Creando tag v$VERSION..."
git tag -a "v$VERSION" -m "$MESSAGE"
git push origin "v$VERSION"

# 4. Create GitHub Release (requires gh CLI or manual creation)
echo "📦 Creando GitHub Release..."

if command -v gh &> /dev/null; then
    # Use GitHub CLI if available
    gh release create "v$VERSION" --title "v$VERSION" --notes "$MESSAGE"
    echo "✅ GitHub Release creado con gh CLI"
else
    echo "⚠️  GitHub CLI (gh) no está instalado."
    echo "   Para que HACS muestre la versión correctamente, crea un release manualmente:"
    echo "   https://github.com/pabloantonelli/solar-pool-ai/releases/new?tag=v$VERSION"
    echo ""
    echo "   O instala gh CLI: brew install gh && gh auth login"
fi

echo "✨ Lanzamiento completado con éxito. HACS detectará la actualización v$VERSION pronto."
