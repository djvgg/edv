' SPDX-FileCopyrightText: 2026 TOP Team Combat Control
' SPDX-License-Identifier: GPL-3.0-or-later
'
' Urkunden-Serienbrief — Ein-Klick-Druck.
'
' Druckt die aktuelle Writer-Vorlage als Serienbrief gegen die registrierte
' Datenquelle "Urkunden" (= temp/exports/urkunden.xlsx aus edv) direkt auf den
' Drucker. Siehe README.md im selben Ordner für die Einrichtung.
'
' Installation: Extras ▸ Makros ▸ Makros verwalten ▸ Basic ▸ Verwalten ▸
' Bibliotheken ▸ Importieren … ODER den Inhalt in ein Modul der Vorlage kopieren.
' Anschließend "UrkundenDrucken" einem Symbolleisten-Knopf zuweisen
' (Extras ▸ Anpassen ▸ Symbolleisten).

' --- Konfiguration (bei Bedarf anpassen) -----------------------------------
Const DATASOURCE_NAME = "Urkunden"   ' Name, unter dem die XLSX registriert ist
Const TABLE_NAME      = "urkunden"   ' Tabellenblatt-Name in der XLSX
' ---------------------------------------------------------------------------


' Druckt jede Urkunde direkt auf den Standarddrucker.
Sub UrkundenDrucken
    Dim oMM As Object
    Dim sUrl As String

    sUrl = ThisComponent.getURL()
    If sUrl = "" Then
        MsgBox "Bitte dieses Vorlagen-Dokument zuerst speichern, " & _
               "dann erneut drucken.", 48, "Urkunden"
        Exit Sub
    End If

    oMM = createUnoService("com.sun.star.text.MailMerge")
    oMM.DataSourceName = DATASOURCE_NAME
    oMM.CommandType    = com.sun.star.sdb.CommandType.TABLE
    oMM.Command        = TABLE_NAME
    oMM.DocumentURL    = sUrl
    oMM.OutputType     = com.sun.star.text.MailMergeType.PRINTER

    On Error GoTo Fehler
    oMM.execute(Array())
    MsgBox "Serienbrief an den Drucker gesendet.", 64, "Urkunden"
    Exit Sub

Fehler:
    MsgBox "Druck fehlgeschlagen: " & Error$ & Chr(10) & _
           "Ist die Datenquelle '" & DATASOURCE_NAME & "' registriert " & _
           "und die XLSX vorhanden?", 16, "Urkunden"
End Sub


' Vorschau: erzeugt EIN gesammeltes Dokument (alle Urkunden) zur Sichtkontrolle,
' OHNE zu drucken. Empfohlen vor dem ersten echten Druck.
Sub UrkundenVorschau
    Dim oMM As Object
    Dim sUrl As String

    sUrl = ThisComponent.getURL()
    If sUrl = "" Then
        MsgBox "Bitte dieses Vorlagen-Dokument zuerst speichern.", 48, "Urkunden"
        Exit Sub
    End If

    oMM = createUnoService("com.sun.star.text.MailMerge")
    oMM.DataSourceName = DATASOURCE_NAME
    oMM.CommandType    = com.sun.star.sdb.CommandType.TABLE
    oMM.Command        = TABLE_NAME
    oMM.DocumentURL    = sUrl
    oMM.OutputType     = com.sun.star.text.MailMergeType.SHELL  ' öffnet Ergebnis

    On Error GoTo Fehler
    oMM.execute(Array())
    Exit Sub

Fehler:
    MsgBox "Vorschau fehlgeschlagen: " & Error$, 16, "Urkunden"
End Sub
