<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: CC0-1.0 -->

# Urkunden-Serienbrief — Einrichtung & Bedienung

Sieger-Urkunden (Platz 1–3) werden auf **vorgedruckte** Urkunden gedruckt. Nur
vier Felder kommen aufs Papier: **Vorname, Nachname, Platzierung, Klasse**.

Arbeitsteilung:

- **edv** baut die Datenquelle `temp/exports/urkunden.xlsx` (Knopf „Urkunden…"
  im Generierungs-Screen → fertige Klassen wählen → Exportieren).
- **LibreOffice** druckt sie über die hier liegende Vorlage per Ein-Klick-Makro.

Die Datenquelle und das Layout sind bewusst **entkoppelt**: edv erzeugt nur die
Zeilen, die Feldpositionen kalibrierst du in der Vorlage — ohne Code.

Dateien in diesem Ordner:

| Datei | Zweck |
|---|---|
| `urkunden_vorlage.fodt` | Writer-Starter-Vorlage mit den 4 Seriendruckfeldern |
| `UrkundenSerienbrief.bas` | LibreOffice-Basic-Makro (Druck / Vorschau) |
| `README.md` | diese Anleitung |

Spalten der Datenquelle (= Feldnamen): `vorname`, `nachname`, `platz`
(`1.`/`2.`/`3.`), `klasse` (`U13 -40kg weiblich`), `verein`. Tabellenblatt heißt
`urkunden`.

---

## Einmalige Einrichtung

### 1. Datenquelle registrieren

Die Vorlagen-Felder erwarten eine registrierte Datenbank namens **`Urkunden`**.

1. In edv einmal „Urkunden…" → eine Klasse → Exportieren, damit
   `temp/exports/urkunden.xlsx` existiert.
2. LibreOffice: **Extras ▸ Optionen ▸ LibreOffice Base ▸ Datenbanken ▸ Neu…**
3. Registrierte Datenbank durchsuchen → die `urkunden.xlsx` wählen.
4. Als **registrierter Name** exakt `Urkunden` eintragen → OK.

> Fester Pfad heißt: einmal registrieren reicht. edv überschreibt dieselbe
> Datei bei jedem Export — die Registrierung bleibt gültig.

### 2. Vorlage öffnen und Felder prüfen

`urkunden_vorlage.fodt` öffnen. Wenn die Datenquelle registriert ist, zeigen die
Felder bei aktivem Datensatz die Werte. Bleibt ein Feld leer:

- Feld löschen und neu einfügen: **Einfügen ▸ Feldbefehl ▸ Mehr Feldbefehle… ▸
  Datenbank ▸ Serienbrieffeld**, Datenquelle `Urkunden`, Tabelle `urkunden`,
  Spalte wählen (`vorname` …) → Einfügen.

Speichere die Vorlage nach dem ersten Anpassen als **`.odt`** (nicht `.fodt`) ab,
falls du Makro + Symbolleiste mitspeichern willst.

### 3. Makro installieren

1. **Extras ▸ Makros ▸ Makros bearbeiten** → im Baum dein Dokument (oder
   „Meine Makros") → ein Modul anlegen.
2. Inhalt von `UrkundenSerienbrief.bas` hineinkopieren.
3. Bei Bedarf oben `DATASOURCE_NAME` / `TABLE_NAME` anpassen (Default passt).

### 4. Knopf zuweisen (Ein-Klick)

**Extras ▸ Anpassen ▸ Symbolleisten** → einen Knopf hinzufügen → Kategorie
„LibreOffice-Makros" → `UrkundenDrucken` zuweisen. (Optional ein zweiter Knopf
für `UrkundenVorschau`.)

### 5. Am echten Vordruck kalibrieren

Das ist der einzige Handarbeit-Teil — Code nimmt ihn dir nicht ab.

1. Lege ein **leeres** Blatt (gleiches Format wie die Urkunde) in den Drucker.
2. `UrkundenVorschau` → ein Testblatt drucken.
3. Testblatt **gegen die vorgedruckte Urkunde** halten (gegen Licht).
4. Felder im Writer verschieben, bis sie sitzen. Für millimetergenaue Position
   die Felder in **Textrahmen** legen (Einfügen ▸ Textrahmen, „Verankerung an
   der Seite", feste Position in cm) und das jeweilige Feld hineinziehen.
5. Schritte 2–4 wiederholen, bis die Ausrichtung stimmt. Vorlage speichern.

---

## Am Turniertag (Ablauf)

1. Klasse fertig → in edv „Urkunden…" → **Aktualisieren** → die neue Klasse ist
   als `●` vorausgewählt (Default = alle neuen sammeln) → **Exportieren**.
2. Vorgedruckte Urkunden dieser Klasse in den Drucker legen.
3. In der Vorlage **Druck-Knopf** (`UrkundenDrucken`) drücken.
4. Vor dem ersten Lauf einer Sitzung lieber einmal `UrkundenVorschau` zur
   Sichtkontrolle.

> **Bewusst kein vollautomatischer Druck.** Du prüfst Papier/Ausrichtung und
> löst den Druck selbst aus — sonst feuert der Drucker auf eine verschobene
> Lage. „Automatisch" ist nur das Erzeugen der Datenquelle.

### Nachdruck / schon gedruckte Klassen

Der `●`/`✓`-Marker ist **weich** (lokale `temp/exports/urkunden_printed.json`,
kein DB-Status). Eine bereits exportierte Klasse (`✓`) einfach wieder anhaken und
erneut exportieren — Nachdruck ist jederzeit möglich. Kompletter Reset: die
`urkunden_printed.json` löschen.

---

## Problemlösung

| Symptom | Ursache / Lösung |
|---|---|
| Felder bleiben leer | Datenquelle nicht als `Urkunden` registriert oder XLSX fehlt → Schritt 1. Feld ggf. neu einfügen (Schritt 2). |
| „Druck fehlgeschlagen" | XLSX nicht vorhanden (in edv exportieren) oder Tabellenname ≠ `urkunden`. |
| Falscher Drucker | LibreOffice nutzt den Standarddrucker — vorher unter Datei ▸ Drucken den richtigen wählen/als Standard setzen. |
| Doppelpool: 4 Urkunden statt 3 | Korrekt — zwei dritte Plätze, keine Bronze-Medaille. |
| Ausrichtung verschoben | Felder in Textrahmen mit fester Seitenposition legen (Schritt 5). |
