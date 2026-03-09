# Bug Analysis: Quarantine List Routing

Die Ursache des von dir beschriebenen Fehlers liegt in zwei spezifischen Programmstellen:

1. **`quarantine_service.py` (Methode `resort_brackets`)**
Wenn jemand, der bereits in Quarantäne ist, bearbeitet wird, durchläuft er `resort_brackets`. Dort wird zwar korrekt berechnet, WARUM die Person in Quarantäne bleiben muss (z.B. neu errechnetes `invalid_reason = "unpaid"`), aber die Person wird am Ende einfach wieder blind in die **ursprüngliche** Quarantäneliste (z.B. `QUARANTINE_age_out_of_bounds`) zurückgesteckt. Der Code überprüft nicht, ob sich der Grund geändert hat, und verschiebt die Person folglich auch nicht in die richtige Liste.

2. **`edit_participant_dialog.py` (Methode `_save_changes`)**
Wenn jemand aus einer normalen Gruppe in Quarantäne verschoben wird, ruft das Skript `create_quarantine_bracket` auf. Dabei wird jedoch vergessen, dem `moved_fighter`-Dictionary das Feld `rejection_reason` hinzuzufügen. Das Service-Script greift dann auf den Fallback `'unknown'` zurück (oder auf den Grund, der noch von vorherrschenden Fehlern im Cache hing).

---

## Proposed Changes

### Backend/Services Layer

#### [MODIFY] `quarantine_service.py`(file:///c:/Users/Acer/Desktop/Hochschule_Worms/TOP/Judo/edv_backend/frontend/services/quarantine_service.py)
In `resort_brackets` muss die Logik erweitert werden, um Personen, deren Quarantäne-Grund sich ändert, in die richtige Liste zu migrieren:
```python
# ... IN resort_brackets ...

moved_to_different_quarantine = []

for quarantine_key in quarantine_keys:
    # Aktuelle Liste
    current_quarantine_reason = quarantine_key.replace('QUARANTINE_', '')
    quarantine_fighters = brackets[quarantine_key].get('fighters', [])
    still_invalid_same_reason = []
    
    for base_fighter in quarantine_fighters:
        # [... Code, der is_valid und invalid_reason bestimmt ...]
        
        if is_valid:
            valid_from_quarantine.append(fighter)
        else:
            # NEU: Hat sich der Grund geändert?
            if invalid_reason != current_quarantine_reason:
                fighter['RejectionReason'] = invalid_reason
                fighter['rejection_reason'] = invalid_reason
                moved_to_different_quarantine.append((fighter, invalid_reason))
            else:
                still_invalid_same_reason.append(fighter)
                
    brackets[quarantine_key]['fighters'] = still_invalid_same_reason

# ... NACH der Schleife ...
# Migriere die verschobenen Fighter in ihre neuen Quarantäne-Listen
for fighter, new_reason in moved_to_different_quarantine:
    new_key = f"QUARANTINE_{new_reason}"
    if new_key not in brackets:
        brackets[new_key] = {
            'fighters': [],
            'bracket': [],
            'pool_size': None,
            'is_quarantine': True,
            'rejection_reason': new_reason,
        }
    brackets[new_key]['fighters'].append(fighter)
```

### Frontend/Views Layer

#### [MODIFY] `edit_participant_dialog.py`(file:///c:/Users/Acer/Desktop/Hochschule_Worms/TOP/Judo/edv_backend/frontend/views/edit_participant_dialog.py)
In `_save_changes` (im elif-Block für `should_be_quarantined`) muss vor dem Aufruf von `create_quarantine_bracket` der `rejection_reason` explizit nach der festgelegten Priorität gesetzt werden:
```python
elif should_be_quarantined:
    old_fighters = self.parent.brackets[self.bracket_key].get('fighters', [])
    if 0 <= self.fighter_idx < len(old_fighters):
        moved_fighter = old_fighters.pop(self.fighter_idx)
        self.parent.brackets[self.bracket_key]['bracket'] = []
        
        # NEU: Manuelles Setzen des Quarantäne-Grunds
        if not self.paid_var.get():
            moved_fighter['rejection_reason'] = 'unpaid'
        elif not self.valid_var.get():
            moved_fighter['rejection_reason'] = 'marked_invalid'
        else:
            birth_year_raw = self.birth_year_entry.get().strip()
            _, _, _, reason = validate_age_from_birthyear(birth_year_raw)
            moved_fighter['rejection_reason'] = reason
            
        if self.parent.quarantine_service:
            quarantine_result = self.parent.quarantine_service.create_quarantine_bracket(self.parent.brackets, [moved_fighter])
            # ... Rest bleibt gleich
```

## Verification Plan

### Manual Verification
1. Öffne die App und wechsle in den Gruppen-Preview-Screen.
2. Doppelklick auf eine existierende Quarantäne-Liste (z.B. `QUARANTINE_age_out_of_bounds`).
3. Wähle einen Nutzer aus und bearbeite ihn. Entferne das Häkchen bei Valid oder Paid (aber lasse das falsche Alter stehen).
4. Speichere. Der Nutzer sollte nun verschwinden und in der Liste `QUARANTINE_unpaid` oder `QUARANTINE_marked_invalid` auftauchen.
5. Verschiebe einen komplett validen Nutzer aus einer regulären Gruppe, indem du Paid=False oder Valid=False machst. Speichere. Er sollte nun einwandfrei in der exakt richtigen Quarantäne-Liste landen.
