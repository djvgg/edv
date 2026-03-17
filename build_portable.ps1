# build_portable.ps1
# This script builds a portable version of Combat Control for a USB stick.

echo "--- Building Combat Control Portable ---"

# 1. Install dependencies
echo "Installing build dependencies..."
pip install pyinstaller pandas openpyxl sqlalchemy python-dotenv psycopg2-binary

# 2. Prepare build directory
if (Test-Path "dist_usb") { Remove-Item -Recurse -Force "dist_usb" }
New-Item -ItemType Directory -Path "dist_usb"

# 3. Create PyInstaller executable
# --noconsole: Don't show terminal window
# --onefile: Bundle everything into a single EXE (easier for users)
# --add-data: Include config and assets
echo "Running PyInstaller..."
pyinstaller --noconsole --onefile `
    --name "CombatControl" `
    --add-data "config;config" `
    --add-data "backend;backend" `
    --add-data "frontend;frontend" `
    --add-data "utils;utils" `
    --hidden-import "openpyxl.cell._writer" `
    --hidden-import "sqlalchemy.sql.default_comparator" `
    main.py

# 4. Final organization
echo "Organizing files for USB..."
Copy-Item "dist/CombatControl.exe" "dist_usb/"

# Create a README for the USB
@"
# Combat Control - Portable Tournament Management

To run the system:
1. Plug in the USB stick.
2. Double-click `CombatControl.exe`.

The system will automatically create a `tournament.db` file in this folder to store match data.
Configuration can be found in the `config` folder if you need to adjust bracket rules.

DESIGNED FOR OFFLINE USE.
"@ | Out-File -FilePath "dist_usb/README.txt"

# Create an .env for the USB to force SQLite
"DB_TYPE=sqlite" | Out-File -FilePath "dist_usb/.env"

echo "Done! Copy the contents of 'dist_usb' to your USB stick."
