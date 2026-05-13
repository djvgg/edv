#!/usr/bin/env bash
# build_portable.sh
# Builds a portable version of Combat Control for a USB stick (macOS/Linux).

set -euo pipefail

echo "--- Building Combat Control Portable ---"

# 1. Install dependencies
echo "Installing build dependencies..."
pip install pyinstaller pandas openpyxl sqlalchemy python-dotenv psycopg2-binary

# 2. Prepare build directory
rm -rf dist_usb
mkdir -p dist_usb

# 3. Determine OS-specific PyInstaller path separator
#    PyInstaller uses ";" on Windows, ":" on macOS/Linux
SEP=":"

# 4. Create PyInstaller executable
echo "Running PyInstaller..."
pyinstaller --noconsole --onefile \
    --name "CombatControl" \
    --add-data "config${SEP}config" \
    --add-data "backend${SEP}backend" \
    --add-data "frontend${SEP}frontend" \
    --add-data "utils${SEP}utils" \
    --hidden-import "openpyxl.cell._writer" \
    --hidden-import "sqlalchemy.sql.default_comparator" \
    main.py

# 5. Final organization
echo "Organizing files for USB..."
cp dist/CombatControl dist_usb/

cat > dist_usb/README.txt << 'EOF'
# Combat Control - Portable Tournament Management

To run the system:
1. Plug in the USB stick.
2. Run ./CombatControl (macOS/Linux) or CombatControl.exe (Windows).

The system will automatically create a tournament.db file in this folder to store match data.
Configuration can be found in the config folder if you need to adjust bracket rules.

DESIGNED FOR OFFLINE USE.
EOF

echo "DB_TYPE=sqlite" > dist_usb/.env

echo "Done! Copy the contents of 'dist_usb' to your USB stick."
