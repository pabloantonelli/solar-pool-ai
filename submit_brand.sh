#!/bin/bash

# Script para preparar el PR de branding a home-assistant/brands
# Uso: ./submit_brand.sh TU_USUARIO_GITHUB

GITHUB_USER=$1

if [ -z "$GITHUB_USER" ]; then
    echo "❌ Error: Debes proporcionar tu usuario de GitHub"
    echo "Uso: ./submit_brand.sh TU_USUARIO_GITHUB"
    exit 1
fi

BRANDS_DIR="../brands"
INTEGRATION_NAME="solarpool_ai"

echo "🚀 Preparando PR de branding para SolarPool AI..."

# 1. Clonar el fork
if [ ! -d "$BRANDS_DIR" ]; then
    echo "📥 Clonando tu fork de brands..."
    cd ..
    git clone "https://github.com/$GITHUB_USER/ha-brands.git"
    cd brands
else
    echo "📂 Directorio brands ya existe, actualizando..."
    cd "$BRANDS_DIR"
    git pull origin main
fi

# 2. Crear rama para el PR
echo "🌿 Creando rama para el PR..."
git checkout -b "add-$INTEGRATION_NAME-branding"

# 3. Crear directorio de la integración
echo "📁 Creando directorio custom_integrations/$INTEGRATION_NAME..."
mkdir -p "custom_integrations/$INTEGRATION_NAME"

# 4. Copiar archivos de branding
echo "📋 Copiando archivos de branding..."
cp ../pileta-climatizacion-ha/brands_assets/icon.png "custom_integrations/$INTEGRATION_NAME/"
cp ../pileta-climatizacion-ha/brands_assets/icon@2x.png "custom_integrations/$INTEGRATION_NAME/"
cp ../pileta-climatizacion-ha/brands_assets/logo.png "custom_integrations/$INTEGRATION_NAME/"
cp ../pileta-climatizacion-ha/brands_assets/logo@2x.png "custom_integrations/$INTEGRATION_NAME/"

# 5. Verificar archivos
echo "✅ Archivos copiados:"
ls -lh "custom_integrations/$INTEGRATION_NAME/"

# 6. Commit
echo "💾 Creando commit..."
git add "custom_integrations/$INTEGRATION_NAME/"
git commit -m "Add $INTEGRATION_NAME custom integration branding

- Add icon.png (256x256)
- Add icon@2x.png (512x512)
- Add logo.png (256x256)
- Add logo@2x.png (512x512)

Custom integration for AI-powered solar pool heating control.
Repository: https://github.com/pabloantonelli/solar-pool-ai"

# 7. Push
echo "🚀 Subiendo cambios a tu fork..."
git push -u origin "add-$INTEGRATION_NAME-branding"

echo ""
echo "✨ ¡Listo! Ahora ve a GitHub y crea el Pull Request:"
echo "   https://github.com/$GITHUB_USER/brands/compare/add-$INTEGRATION_NAME-branding"
echo ""
echo "📝 Título sugerido: Add solarpool_ai custom integration branding"
echo "📝 Descripción sugerida:"
echo "   Adds branding assets for the SolarPool AI custom integration."
echo "   Repository: https://github.com/pabloantonelli/solar-pool-ai"
