<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: GPL-3.0-or-later -->

# Benutzerdokumentation

Diese Dokumentation erklärt die Bedienung von EDV Backend in deutscher Sprache. Sie richtet sich an Personen, die das Programm während der Turniervorbereitung oder am Wettkampftag benutzen. Die Beschreibung basiert auf dem tatsächlichen Aufbau der Anwendung im Ordner `edv_backend` und auf den vorhandenen Bildschirmfotos.

## 1. Wofür das System gedacht ist

Mit dem System können Sie:

- Teilnehmerdaten aus einer Datenbank wiederherstellen
- zwei vorbereitete JSON-Dateien aus dem Wiegeprozess neu laden
- eine Excel-Meldeliste in JSON-Dateien für männlich und weiblich aufteilen
- erzeugte Gruppen vor der Erstellung prüfen
- Teilnehmerdaten in einer Gruppe bearbeiten
- Wettkampfsysteme pro Liste zuweisen
- Listen einer Matte zuordnen
- Kampflisten nach Excel exportieren
- Kampflisten in Pool- oder KO-Ansicht anzeigen

Das Programm bildet den Ablauf von der Datenübernahme bis zur Anzeige der Kampflisten in einer Oberfläche ab.

Wichtig:

- Die Schaltflächen im Dateilader sind nicht nur alternative Varianten derselben Funktion.
- Der Excel-zu-JSON-Schritt dient dazu, Daten an die Waage beziehungsweise den Wiegeprozess zu übergeben.
- Die später wieder importierten JSON-Dateien kommen aus diesem vorgelagerten Wiegeablauf zurück.
- Das Laden aus der Datenbank ist vor allem für das Wiederherstellen eines Arbeitsstands nach einem Absturz gedacht.

## 2. Was Sie vor dem Start brauchen

Für einen reibungslosen Ablauf sollten folgende Dinge bereitstehen:

- eine Excel-Meldeliste als Ausgangspunkt des Ablaufs
- zwei JSON-Dateien, wenn die Daten bereits über die Waage oder den Wiegeprozess zurückgeliefert wurden
- eine laufende PostgreSQL-Datenbank, wenn ein gespeicherter Stand nach einem Absturz wiederhergestellt werden soll
- ein vollständig eingerichtetes Projekt mit Python 3.10 oder neuer

Wichtig:

- Der typische Ablauf beginnt fachlich mit einer Excel-Datei und führt dann über JSON-Dateien weiter.
- Die JSON-Dateien sind dabei kein Nebenweg, sondern die Rückgabe aus dem Wiegeprozess.
- Die Datenbank dient in diesem Zusammenhang vor allem dazu, einen bereits bearbeiteten Stand wieder laden zu können.
- Das Programm kann auch ohne erreichbare Datenbank starten, arbeitet dann aber nur eingeschränkt im Offline-Modus.

## 3. Programmstart

Starten Sie die Anwendung im Ordner `edv_backend` mit:

```bash
python -m edv_backend
```

Alternativ ist auch dieser Start möglich:

```bash
python main.py
```

Nach dem Start öffnet sich das Hauptfenster mit dem Dateilader als Einstieg.

## 4. Schnellstart

1. Starten Sie die Anwendung.
2. Teilen Sie bei Bedarf eine Excel-Meldeliste in JSON-Dateien für den Wiegeprozess auf.
3. Laden Sie die aus dem Wiegeprozess zurückkommenden JSON-Dateien neu.
4. Prüfen Sie die erzeugten Gruppen in der Gruppenvorschau.
5. Bearbeiten Sie bei Bedarf Teilnehmerdaten.
6. Wechseln Sie in den Bereich `Wettkampfsystem`.
7. Ordnen Sie jeder Liste ein System zu.
8. Öffnen Sie die Listenansicht und verteilen Sie Listen auf Matten.
9. Exportieren Sie bei Bedarf die Kampflisten.
10. Wechseln Sie in die Ansicht der fertigen Kampflisten.

![Dateilader](Readmesource/loader.png)
*Startansicht des Programms mit den verfügbaren Lade- und Hilfsfunktionen.*

## 5. Die Hauptoberfläche

Die Anwendung ist als mehrstufiger Ablauf aufgebaut. Im normalen Betrieb bewegen Sie sich durch diese Bereiche:

- `Dateilader`
- `Gruppenvorschau`
- `Wettkampfsystem`
- `Listenansicht`
- `Fertige Kampflisten`

Zusätzlich gibt es die Ansicht der fertigen Kampflisten, in der die einer Matte zugeordneten Listen geöffnet und angezeigt werden.

Die Oberfläche wechselt also nicht ständig in neue Hauptfenster, sondern führt Sie Schritt für Schritt durch den Turnierablauf.

## 6. Daten laden

Der Dateilader ist der Einstiegspunkt des Programms. Die dort sichtbaren Schaltflächen haben unterschiedliche Aufgaben innerhalb des Gesamtablaufs.

Sie sind nicht bloß mehrere Varianten desselben Imports, sondern decken verschiedene Arbeitsschritte ab:

- Vorbereitung der Daten für die Waage
- Rückimport der bearbeiteten Wiegedaten
- Wiederherstellung eines gespeicherten Zustands nach Absturz

### 6.1 Aus Datenbank laden

Mit `Aus Datenbank laden & Listen generieren` werden Teilnehmer aus PostgreSQL geladen und daraus Gruppen beziehungsweise Listen erzeugt.

Dieser Weg ist vor allem für den Fall gedacht, dass ein bereits vorhandener Stand wiederhergestellt werden muss, zum Beispiel nach einem Absturz oder nach einem unerwarteten Neustart.

Damit können bereits gespeicherte Daten erneut in die Anwendung geholt werden, ohne den Ablauf von vorne beginnen zu müssen.

### 6.2 JSON-Dateien neu laden

Mit `JSON-Dateien neu laden (m/w)` wählen Sie genau zwei JSON-Dateien aus. Das Programm erwartet:

- eine Datei für männlich
- eine Datei für weiblich

Diese Funktion ist dafür gedacht, die zuvor für die Waage vorbereiteten und dort weiterverarbeiteten Daten wieder in EDV Backend zurückzuholen.

Wenn nicht genau zwei Dateien ausgewählt werden, bricht der Vorgang mit einem Hinweis ab.

### 6.3 Teilnehmer nach Geschlecht trennen

Mit `Teilnehmer nach Geschlecht trennen (Excel → JSON)` können Sie eine Excel-Datei einlesen und daraus zwei JSON-Dateien erzeugen.

Diese JSON-Dateien sind für den nachgelagerten Wiegeprozess gedacht. Sie werden also nicht nur erzeugt, sondern später nach dem Wiegen wieder in das System reimportiert.

Vor dem Speichern öffnet sich ein Dialog zur Konfiguration der Toleranzen.

![Toleranzkonfiguration](Readmesource/toleranz.png)
*Vor dem Aufteilen der Excel-Daten werden Toleranzen je Alters- und Geschlechtsgruppe festgelegt.*

### 6.4 Datenbank leeren

Mit `Datenbank leeren (Alle Daten löschen)` wird der gespeicherte Turnierstand vollständig entfernt. Vorher erscheint eine Sicherheitsabfrage.

Diese Funktion sollte nur bewusst verwendet werden, zum Beispiel wenn ein neuer Turnierstand sauber aufgebaut werden soll.

## 7. Gruppenvorschau

Nach dem Laden wechselt das Programm in die Gruppenvorschau. Hier kontrollieren Sie die erzeugten Gruppen, bevor Sie das Wettkampfsystem festlegen.

Die Ansicht besteht aus zwei Bereichen:

- links: Suchfeld und Liste der vorhandenen Gruppen
- rechts: Teilnehmer der aktuell ausgewählten Gruppe

Unten finden Sie die wichtigsten Schaltflächen:

- `← Zurück zum Dateilader`
- `Weiter zur Erstellung →`

![Gruppenvorschau](Readmesource/grouppreview.png)
*In der Gruppenvorschau werden die erzeugten Gruppen vor der eigentlichen Erstellung geprüft.*

### 7.1 Was Sie hier prüfen sollten

Prüfen Sie insbesondere:

- ob die Gruppen sinnvoll gefüllt sind
- ob alle relevanten Teilnehmer vorhanden sind
- ob es Gruppen mit auffälligen oder unerwarteten Einträgen gibt
- ob zurückgestellte Teilnehmer in Quarantäne-Gruppen auftauchen

Im Code werden Quarantäne-Gruppen unter anderem für diese Fälle geführt:

- `Ungültig`
- `Unbezahlt`
- `Alter ungültig`

### 7.2 Suche in der Gruppenvorschau

Über das Suchfeld können Sie die Liste links filtern. Das ist hilfreich, wenn viele Gruppen vorhanden sind.

### 7.3 Teilnehmer bearbeiten

Per Doppelklick auf einen Teilnehmer öffnen Sie den Bearbeitungsdialog.

Wichtig:

- Teilnehmer können nicht mehr bearbeitet werden, wenn die zugehörige Liste bereits einer Matte zugewiesen wurde.
- In diesem Fall müssen Sie die Mattenzuweisung zuerst wieder entfernen.

## 8. Teilnehmer bearbeiten

Der Dialog `Teilnehmer bearbeiten` dient zur Korrektur einzelner Datensätze innerhalb einer Gruppe.

![Teilnehmer bearbeiten](Readmesource/editparticipant.png)
*Der Bearbeitungsdialog für einzelne Teilnehmer innerhalb einer Gruppe.*

Je nach Datensatz können Sie insbesondere folgende Angaben prüfen oder ändern:

- Vorname
- Nachname
- Gewicht
- Verein
- Verband
- Geburtsjahr
- Geschlecht beziehungsweise Gruppenzuordnung
- Gültigkeit
- Bezahlt-Status

Das Programm enthält Prüfungen für wichtige Eingaben:

- Namen dürfen nur zulässige Zeichen enthalten
- das Geburtsjahr muss vierstellig sein
- das Gewicht wird als Zahl geprüft

Zusätzlich können im Dialog automatische Hinweise erscheinen, zum Beispiel:

- erkannte Altersklasse auf Basis des Geburtsjahrs
- erkannte Gewichtsklasse auf Basis von Gewicht, Toleranz, Geschlecht und Altersgruppe

## 9. Wettkampfsystem zuweisen

Nach der Gruppenvorschau wechseln Sie in den Bereich `Wettkampfsystem`. Hier legen Sie fest, wie jede Liste weiterverarbeitet wird.

Die Ansicht enthält:

- links eine Liste noch nicht zugewiesener Kampflisten
- rechts vier Bereiche für die möglichen Systeme

Die im Code vorgesehenen Hauptsysteme sind:

- `Pools`
- `Doppel-Pools`
- `KO-System`
- `Sonderfälle`

### 9.1 Typische Arbeitsschritte

1. Wählen Sie links eine noch nicht zugewiesene Liste aus.
2. Ordnen Sie diese einem System zu.
3. Wiederholen Sie den Vorgang für alle offenen Listen.
4. Bestätigen Sie am Ende die Erstellung.

Wenn noch nicht alle Listen zugewiesen wurden, warnt das Programm vor dem Fortfahren.

### 9.2 Suche und automatische Verteilung

Auch in diesem Bereich gibt es eine Suche. Zusätzlich unterstützt der Bildschirm automatische Zuordnungslogik für passende Listen.

### 9.3 Export aus diesem Bereich

Schon im Bereich `Wettkampfsystem` können Sie Excel-Dateien erzeugen:

- für die aktuell ausgewählte Liste
- für alle bereits zugewiesenen Listen

Die Dateien werden im Projekt unter folgendem Ordner gespeichert:

```text
temp/exports/
```

Je nach System erzeugt das Programm unterschiedliche Exportformate:

- Pool-Listen
- Doppel-Pool-Listen mit Finale
- KO-Listen

## 10. Listenansicht und Mattenzuweisung

Nach der Zuweisung der Wettkampfsysteme geht es in die `Listenansicht`. Hier werden Listen visualisiert und Matten zugeordnet.

Die Oberfläche besteht im Wesentlichen aus:

- einer linken Liste offener Kampflisten
- Schaltflächen für die Zuordnung zu `Matte 1` bis `Matte 4`
- einer automatischen Mattenzuweisung
- einer rechten Visualisierung der ausgewählten Liste

### 10.1 Was Sie hier tun können

- nach offenen Listen suchen
- eine Liste einer Matte zuweisen
- alle Listen automatisch auf Matten verteilen
- eine Visualisierung der aktuellen Liste ansehen
- zur Erstellung zurückkehren
- in die Ansicht `Fertige Kampflisten` wechseln

Je nach zugewiesenem System sehen Sie rechts entweder:

- eine Pool-Ansicht
- eine Doppel-Pool-Ansicht
- eine KO-Ansicht

Pool-Beispiel:

![Pool-Ansicht](Readmesource/pool.png)
*Beispiel einer Listenansicht im Pool-System.*

Doppel-Pool-Beispiel:

![Doppel-Pool-Ansicht](Readmesource/doublepool.png)
*Beispiel einer Listenansicht im Doppel-Pool-System.*

KO-Beispiel:

![KO-Ansicht](Readmesource/doubleko.png)
*Beispiel einer KO-basierten Listenansicht.*

## 11. Kampflisten exportieren

Wenn die Systeme festgelegt sind, können die Kampflisten als Excel-Dateien ausgegeben werden.

Typische Verwendung:

- Ausdruck für den Kampftisch
- Kontrolle der erzeugten Paarungen
- Weitergabe an andere Bereiche der Veranstaltung

Beim Export informiert das Programm nach Abschluss darüber, wie viele Dateien erfolgreich erstellt wurden und in welchem Ordner sie abgelegt wurden.

## 12. Ansicht fertiger Kampflisten

Diese Ansicht baut auf den Mattenzuweisungen aus der Listenansicht auf. Sie dient dazu, die erzeugten Kampflisten pro Matte anzuzeigen.

Der Ablauf ist zweistufig:

1. Zuerst sehen Sie eine Übersicht der Matten.
2. Danach öffnen Sie per Klick die eigentliche Anzeige einer Kampfliste.

![Kampfüberwachung Übersicht](Readmesource/fightbracket.png)
*Übersicht der zugewiesenen Kampflisten innerhalb der Mattenansicht.*

### 12.1 Mattenübersicht

In der Mattenübersicht zeigt das Programm für `Matte 1` bis `Matte 4` die zugewiesenen Kampflisten an.

Wenn einer Matte noch nichts zugeordnet wurde, erscheint ein entsprechender Hinweis.

### 12.2 Listenansicht öffnen

Durch Klick auf eine Kampfliste in der Mattenübersicht öffnen Sie die zugehörige Ansicht. Dort wird in der Kopfzeile angezeigt, zu welcher Matte und zu welcher Kampfliste Sie gerade arbeiten.

### 12.3 Verhalten in der Listenansicht

Die Darstellung hängt vom gewählten System ab.

Wichtig:

- Diese Ansicht ist nicht interaktiv.
- Sie dient nur dazu, die erzeugte Kampfliste beziehungsweise deren Aufbau anzuzeigen.
- In diesem Bereich werden keine Ergebnisse eingetragen.

Je nach zugewiesenem System sehen Sie zum Beispiel:

- eine Pool-Ansicht
- eine Doppel-Pool-Ansicht
- eine KO-Ansicht

![Kampfansicht](Readmesource/fightscreen.png)
*Die Ansicht zeigt die erzeugte Kampfliste in ihrer jeweiligen Form.*

### 12.4 Navigation in der Ansicht fertiger Kampflisten

Die Zurück-Navigation ist kontextabhängig:

- aus einer Listenansicht zurück zur Mattenübersicht
- aus der Mattenübersicht zurück zur Listenansicht

## 13. Typische Hinweise und Grenzen

### Datenbank nicht erreichbar

Wenn PostgreSQL beim Start nicht erreichbar ist, startet das Programm im Offline-Modus.

Folge:

- die Oberfläche kann zwar starten
- der reguläre Betrieb mit persistierten Daten ist aber nicht vollständig nutzbar

### Falsche Anzahl an JSON-Dateien

Beim JSON-Import erwartet das Programm genau zwei Dateien. Wenn nur eine oder mehr als zwei Dateien gewählt werden, wird der Vorgang abgebrochen.

### Teilnehmerbearbeitung gesperrt

Wenn eine Liste bereits einer Matte zugeordnet wurde, lässt sich ein Teilnehmer aus dieser Liste nicht mehr direkt bearbeiten. Entfernen Sie in diesem Fall zuerst die Mattenzuweisung.

### Keine Exportziele vorhanden

Wenn noch keine Listen einem Wettkampfsystem zugewiesen wurden, können keine Exportdateien erstellt werden.

## 14. Empfohlener Arbeitsablauf

1. Anwendung starten.
2. Datenbank oder zwei JSON-Dateien laden.
3. Falls nötig eine Excel-Datei zunächst in JSON-Dateien aufteilen.
4. Gruppen in der Gruppenvorschau prüfen.
5. Einzelne Teilnehmer nur dort korrigieren, wo es fachlich nötig ist.
6. Alle Listen einem passenden Wettkampfsystem zuweisen.
7. In der Listenansicht Mattenzuweisungen vornehmen.
8. Kampflisten exportieren.
9. In die Ansicht der fertigen Kampflisten wechseln und die erzeugten Kampflisten kontrollieren.

## 15. Beenden

Beenden Sie das Programm über das Hauptfenster. Beim nächsten Start beginnt der Ablauf wieder im Dateilader.