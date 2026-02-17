# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

#!/bin/bash

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Dieses Skript muss als root ausgeführt werden."
  echo "Bitte starten mit: sudo $0"
  exit 1
fi

echo "Entferne alte Docker Pakete..."
apt remove -y docker.io docker-doc docker-compose docker-compose-plugin || true
apt autoremove -y

echo "Installiere Abhängigkeiten..."
apt update
apt install -y ca-certificates curl gnupg

echo "Erstelle Keyring Verzeichnis..."
install -m 0755 -d /etc/apt/keyrings

echo "Füge offiziellen Docker GPG Key hinzu..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

echo "Füge Docker Repository hinzu..."
UBUNTU_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" \
> /etc/apt/sources.list.d/docker.list

echo "Installiere Docker CE, CLI, Containerd, Buildx und Compose Plugin..."
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Aktiviere Docker Dienst..."
systemctl enable docker
systemctl start docker

echo "Installation abgeschlossen."
echo "Version prüfen mit:"
echo "  docker --version"
echo "  docker compose version"
