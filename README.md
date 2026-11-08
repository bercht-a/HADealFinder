# Deal Finder für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/bercht-a/HADealFinder/actions/workflows/validate.yml/badge.svg)](https://github.com/bercht-a/HADealFinder/actions/workflows/validate.yml)

Pflege eine **Wunschliste** in Home Assistant. Deal Finder sucht regelmässig im Web den **tiefsten Preis**
für jedes Produkt, zeigt ihn als Sensor an und **benachrichtigt dich**, sobald dein Zielpreis unterschritten wird.

## Funktionen

- **Eigene Seite „Wunschliste“ in der linken Seitenleiste**: alle Produkte als Karten mit bestem Preis, Shop-Link,
  Abstand zum Zielpreis, Allzeit-Tief und den günstigsten Angeboten. Produkte lassen sich dort hinzufügen, bearbeiten,
  löschen und sofort suchen. Die Seite aktualisiert sich live, auch während einer laufenden Suche.
  Bearbeiten dürfen nur Admins, alle anderen sehen die Liste.
- **Unpassende Angebote ausblenden**: Mit ✕ neben einem Angebot verschwindet es sofort und taucht bei späteren Suchen
  nicht mehr auf. Erkannt wird es an der URL (ohne Tracking-Parameter) oder an Shop plus Titel. Die KI bekommt die
  abgelehnten Angebote mitgeteilt und sucht nach anderen. Unter „Ausgeblendet“ lassen sie sich wiederherstellen.
  Per ✕ → **„Ganzer Shop“** lassen sich auch alle Angebote eines Shops für ein Produkt sperren. Erkannt wird der Shop
  am Namen oder an der Domain, z.B. „Digitec“, „digitec.ch“ oder „Digitec Galaxus AG“.
- Alternativ: **Einstellungen → Geräte & Dienste → Deal Finder → „Produkt hinzufügen“**
- Pro Produkt ein Gerät mit:
  - `sensor.<produkt>_bester_preis`: aktueller Tiefstpreis (mit Shop, Link und den 10 günstigsten Angeboten als Attribute)
  - `sensor.<produkt>_allzeit_tiefstpreis`: der tiefste je gefundene Preis
  - `binary_sensor.<produkt>_unter_zielpreis`
  - `number.<produkt>_zielpreis`: Zielpreis direkt im Dashboard ändern (0 = kein Ziel)
  - `button.<produkt>_jetzt_suchen`
  - `sensor.<produkt>_zuletzt_gepruft`
- Übersichtssensor `sensor.deal_finder_deals_unter_zielpreis` mit allen Produkten im Attribut `products`
- Benachrichtigungen bei Unterschreitung des Zielpreises (optional auch bei jeder Preissenkung):
  HA-Benachrichtigung, beliebige `notify.*`-Dienste (z.B. Companion-App, mit klickbarem Link)
  und Event `deal_finder_price_alert` für eigene Automationen
- Preise bleiben bei einem Neustart erhalten. Gesucht wird erst wieder, wenn das Intervall abgelaufen ist.
  Das spart API-Kosten.

## Preisquellen

| Quelle | Benötigt | Beschreibung |
|---|---|---|
| **Produkt-URLs** | nichts | Shop- oder Preisvergleichsseiten (toppreise.ch, geizhals, digitec, galaxus …). Der Preis wird aus den strukturierten Daten der Seite gelesen (schema.org JSON-LD / Meta-Tags). Auf Vergleichsportalen ist das meist direkt der tiefste Preis aller Shops. |
| **KI-Websuche: Google Gemini** | Gemini-API-Key | Gemini mit *Google Search Grounding* sucht aktuelle Angebote im Zielland. |
| **KI-Websuche: Anthropic Claude** | Claude-API-Key | Claude mit dem serverseitigen *Web Search Tool*. |
| **SerpAPI (Google Shopping)** | SerpAPI-Key | Klassische Shopping-Suche ohne KI. |

**Warum KI?** Es gibt keine kostenlose, länderübergreifende Preis-API. Eine KI mit Websuche findet ein Produkt
anhand seines Namens in beliebigen Shops. Seiten ohne strukturierte Daten kann sie trotzdem auslesen.
Gegen erfundene Angebote hilft die Option **„KI-Preise auf der Shopseite prüfen“**: Die gefundenen Links werden geladen,
der echte Preis wird ausgelesen und tote Links (404) werden verworfen.

> Hinweis: Jede KI-Suche kostet API-Guthaben. Bei Claude sind Websuchen pro Suchanfrage kostenpflichtig, bei Gemini
> fällt Grounding je nach Tarif an. Mit dem Suchintervall (Standard: 12 h) und dem Aufwand (Claude: *Tief*) steuerst du die Kosten.

## Installation über HACS

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → URL `https://github.com/bercht-a/HADealFinder`, Typ **Integration**
2. „Deal Finder“ suchen → **Herunterladen**
3. Home Assistant neu starten
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Deal Finder**

### Manuell (ohne HACS)

1. `deal_finder.zip` aus dem neuesten [Release](https://github.com/bercht-a/HADealFinder/releases) herunterladen
   (oder lokal bauen: `python scripts/build.py`, ergibt `dist/deal_finder.zip`)
2. Inhalt nach `<config>/custom_components/deal_finder/` entpacken (z.B. per Samba-Share oder File-Editor-Add-on)
3. Home Assistant neu starten

### Neue Version veröffentlichen

```bash
git tag v0.1.2 && git push origin v0.1.2
```

Der Workflow `Release` baut `deal_finder.zip` mit dieser Version, erstellt das GitHub-Release, hängt das Paket an und
veröffentlicht es. HACS zeigt das Update danach an. Releases bitte **nicht** von Hand auf GitHub anlegen: Mit
„immutable releases“ lässt sich an ein veröffentlichtes Release kein Paket mehr anhängen.

## Einrichtung

1. **Allgemein**: Land/Markt (bestimmt Shops und Sprache), Währung, Suchintervall, optional SerpAPI-Key
2. **KI-Suche**: *Keine KI*, *Google Gemini* oder *Anthropic Claude* plus API-Key. Der Key wird sofort geprüft.
   - Gemini-Key: <https://aistudio.google.com/apikey>
   - Claude-Key: <https://platform.claude.com/settings/keys>
3. **KI-Modell**: Die Liste wird live vom Anbieter geladen. Eigene Modell-IDs sind möglich.
   Für Claude zusätzlich der Aufwand (*Tief* = günstig/schnell).
4. **Benachrichtigungen**: `notify`-Dienste, HA-Benachrichtigung, Preissenkungen

Alles lässt sich später unter **Konfigurieren** ändern (Menü: Allgemein / KI / Benachrichtigungen).

### Produkt erfassen

| Feld | Tipp |
|---|---|
| Produktname | z.B. `Sony WH-1000XM6 schwarz` |
| Suchbegriff | optional, möglichst genau (Modell, Speicher, Farbe) |
| Zielpreis | darunter wirst du benachrichtigt |
| Mindestpreis | filtert Zubehör und Fehltreffer (z.B. Hüllen für 9.90) |
| Produkt-URLs | eine pro Zeile, z.B. die toppreise.ch-Seite des Produkts |
| Ausschlussbegriffe | `gebraucht, refurbished, hülle` |
| Im Web suchen | KI und/oder SerpAPI verwenden |

Produkte lassen sich auch per Dienst hinzufügen, etwa aus einer Sprach-Automation:

```yaml
action: deal_finder.add_product
data:
  name: "LEGO Icons 10333 Barad-dûr"
  target_price: 380
  exclude_terms: "gebraucht"
```

## Dashboard-Beispiel

Markdown-Karte mit der ganzen Wunschliste:

```yaml
type: markdown
title: 🛒 Wunschliste
content: >
  {% set items = state_attr('sensor.deal_finder_deals_unter_zielpreis', 'products') or [] %}
  | Produkt | Preis | Ziel | Shop |
  |:--|--:|--:|:--|
  {% for p in items -%}
  | {{ '🔥 ' if p.below_target }}{{ p.name }} | {{ '%.2f' % p.price if p.price else '–' }} {{ p.currency }} | {{ p.target_price or '–' }} | {% if p.url %}[{{ p.shop }}]({{ p.url }}){% else %}{{ p.shop or '–' }}{% endif %} |
  {% endfor %}
```

## Automation-Beispiel

```yaml
triggers:
  - trigger: event
    event_type: deal_finder_price_alert
actions:
  - action: notify.mobile_app_mein_handy
    data:
      title: "{{ trigger.event.data.product }}: {{ trigger.event.data.price }} {{ trigger.event.data.currency }}"
      message: "bei {{ trigger.event.data.shop }}"
      data:
        url: "{{ trigger.event.data.url }}"
```

Event-Daten: `type` (`below_target` | `price_drop`), `product`, `price`, `currency`, `shop`, `url`, `target_price`, `previous_price`.

## Dienste

| Dienst | Beschreibung |
|---|---|
| `deal_finder.refresh` | Sofort suchen, für alle Produkte oder eines (`product: "Name"`) |
| `deal_finder.add_product` | Produkt zur Wunschliste hinzufügen |

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

## Lizenz

MIT
