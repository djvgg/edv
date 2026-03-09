# Zusammenfassung der Backend-Änderungen (Backend & Database)

Diese Datei dokumentiert die heute durchgeführten Änderungen am Backend, um den "Freilos-Bug" zu beheben und die Datenbank als "Single Source of Truth" zu einbeziehen.

---

## 1. Datenbank-Modelle (`backend/data/models.py`)
*   **Änderung**: `participant1_id` und `participant2_id` in der `Fight`-Klasse wurden von `nullable=False` auf `nullable=True` geändert.
*   **Grund**: Ein Freilos (Bye) hat keine ID in der Datenbank. Wenn wir ein Freilos speichern wollen, muss eine der Teilnehmer-Spalten `NULL` (None) sein dürfen. Vorher wurde als Notlösung zweimal dieselbe Teilnehmer-ID eingetragen (z.B. 124 vs 124).

## 2. Datenbank-Migration (`backend/data/database.py`)
*   **Änderung**: Neue Migration (`Migration 5/5`) hinzugefügt.
*   **Grund**: Die App erkennt beim Start automatisch, ob die Spalten `participant1_id` und `participant2_id` in der PostgreSQL-Tabelle noch auf `NOT NULL` stehen und ändert sie per `ALTER TABLE` Befehl auf `NULLABLE`. So musst du die Datenbank nicht neu aufsetzen.

## 3. Backend-Logik (`backend/services/tournament_service.py`)
*   **Änderung**: Logik in `open_bracket_for_monitoring` angepasst. 
*   **Details**: Wenn ein Freilos erkannt wird, wird jetzt nur noch die ID des **echten** Kämpfers gesetzt, der andere Slot bleibt `None` (NULL). 
*   **Verbesserung**: Das automatische Vorrücken des Siegers (Winner ID) wird weiterhin sofort in die Datenbank geschrieben, aber das Pairing (Teilnehmer-Spalten) ist jetzt mathematisch korrekt.

## 4. Single Source of Truth (`frontend/services/data_loader_service.py`)
*   **Änderung**: Nach dem Laden von XLSX- oder JSON-Dateien werden die Teilnehmer nun direkt wieder aus der Datenbank geladen (`participants = self.db_service.fetch_participants()`).
*   **Grund**: Die Datenbank sortiert Duplikate automatisch aus (Check auf Vorname, Nachname, Jahrgang). Durch das Neuladen aus der DB wird sichergestellt, dass das UI (der Bildschirm) keine Klone anzeigt, selbst wenn sie in der JSON doppelt vorhanden waren.

## 5. Teilnehmer-Repository (`backend/data/repositories/participant_repository.py`)
*   **Änderung**: Erweiterung von `get_all_as_dicts`.
*   **Grund**: Damit die "Single Source of Truth" (Punkt 4) funktioniert, muss das Datenbank-Format exakt dem Format der JSON-Dateien entsprechen (alle Felder wie ID, Firstname, Weight, Paid etc. müssen im Dictionary vorhanden sein).

---

**Status**: Alle Änderungen gespeichert und erfolgreich mit (psycopg2) getestet.
**Nächster Schritt**: Falls du den versehentlichen Commit in `main` noch in einen Branch verschieben willst, gib mir Bescheid!
