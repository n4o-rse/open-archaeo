# Wikidata: WikiProject Informatics / Software — Properties

Quelle: <https://www.wikidata.org/wiki/Wikidata:WikiProject_Informatics/Software/Properties>
(oldid 2149080987), Properties zu *software* (Q7397).

Reihenfolge und Inhalte folgen der Wikisyntax der Seite. Die Spalte **Rolle**
unterscheidet Haupt-Statement (`statement`) von kontextualisiertem Qualifier
(`qualifier`), wie auf der Seite über `contextualized-qualifier=true` markiert.

---

## 1. Allgemeine Software-Properties

| # | Titel | ID | Datentyp | Rolle | Beschreibung | Beispiel | Inverse |
|---|-------|----|----------|-------|--------------|----------|---------|
| 1 | Arch Linux package | P3454 | External ID | statement | Name des offiziellen Arch-Linux-Pakets | GIMP → `gimp` | -- |
| 2 | based on | P144 | Item | statement | Werk(e) oder Input, die als Basis für das Item dienen; fiktionale Analoga über P1074 | Windows 8.1 → Windows 8 | derivative work |
| 3 | based on / removed feature | P756 | Item | qualifier | Welches Feature in dieser Version eines Produkts entfernt wurde | Devuan → Debian, removed feature: systemd | -- |
| 4 | binding of software library | P1372 | Item | statement | Software-Bibliothek in einer anderen Programmiersprache, die durch das Binding bereitgestellt wird | PyGObject → GObject | -- |
| 5 | issue tracker URL | P1401 | URL | statement | Webseite, auf der Bugs, Issues und Feature Requests gemeldet werden | Wikidata → `https://bugzilla.wikimedia.org/` | -- |
| 6 | creator | P170 | Item | statement | Urheber:in des Werks, wenn keine spezifischere Property existiert | The Potato Eaters → Vincent van Gogh | notable work, significant person |
| 7 | Debian stable package | P3442 | External ID | statement | Name des offiziellen Debian-stable-Pakets | GIMP → `gimp` | -- |
| 8 | depends on software | P1547 | Item | statement | Subjekt-Software hängt von Objekt-Software ab | Gradle → Maven Central Repository | -- |
| 9 | developer | P178 | Item | statement | Organisation oder Person, die das Item entwickelt hat | GNU/Linux → Richard Stallman | -- |
| 10 | developer / instance of | P31 | Item | qualifier | Wenn das Geschäftsmodell der Entwickler:in (P178) von dem des Gesamtunternehmens abweicht, als P31/P279 *business model* (Q815823) setzen | Loomio → Loomio Cooperative Limited | -- |
| 11 | DistroWatch ID | P3112 | External ID | statement | Kennung eines Betriebssystems bei DistroWatch.com | Debian → `debian` | -- |
| 12 | edition or translation of | P629 | Item | statement | Ist eine Version, Ausgabe oder Übersetzung dieser Entität | Windows 8.1 → Windows 8 | has edition or translation |
| 13 | end time | P582 | Point in time | statement | Zeitpunkt, ab dem die Software nicht mehr weiterentwickelt oder gefixt wurde | udev → 2012 | -- |
| 14 | facet of | P1269 | Item | statement | Thema, dessen Aspekt dieses Item ist; Item mit breiterer Perspektive auf dasselbe Thema | deb → dpkg | -- |
| 15 | F-Droid package | P3597 | External ID | statement | Android-Paket im offiziellen F-Droid-Repository | Wikipedia → `org.wikipedia` | -- |
| 16 | Fedora package | P3463 | External ID | statement | Name des offiziellen Fedora-Pakets | GIMP → `gimp` | -- |
| 17 | follows | P155 | Item | statement | Die Software ist unmittelbarer Nachfolger einer älteren, veralteten Software | opkg → ipkg | followed by |
| 18 | followed by | P156 | Item | statement | Die Software wird durch ihren unmittelbaren Nachfolger abgelöst | ipkg → opkg | follows |
| 19 | Framalibre ID | P4107 | External ID | statement | Kennung im Framalibre-Verzeichnis freier Software | LibreOffice Writer → `libreoffice-writer` | -- |
| 20 | Free Software Directory entry | P2537 | External ID | statement | Link zur FSD-Seite einer Software oder Lizenz | Cheese → Cheese | -- |
| 21 | Gentoo package | P3499 | External ID | statement | Name des offiziellen Gentoo-Pakets | GIMP → `media-gfx/gimp` | -- |
| 22 | GitHub account | P2037 | External ID | statement | Account des Projekts, der Person oder Organisation auf GitHub | Michael Niedermayer → `michaelni` | -- |
| 23 | Google Play Store app ID | P3418 | External ID | statement | Paketname einer bei Google Play registrierten App | VLC → `org.videolan.vlc` | -- |
| 24 | GUI toolkit or framework | P1414 | Item | statement | Framework oder Toolkit für die grafische Oberfläche | GIMP → GTK | -- |
| 25 | has part(s) | P527 | Item | statement | Teil dieses Subjekts; Inverse zu P361, siehe auch P2670 | MakeHuman → data set | part of |
| 26 | has part(s) / copyright license | P275 | Item | qualifier | Lizenz, unter der dieser Teil des Werks veröffentlicht ist | MakeHuman → data set, license: CC0 | -- |
| 27 | inception | P571 | Point in time | statement | Entstehungsdatum; nur verwenden, wenn das tatsächliche Erstellungsdatum bekannt ist, sonst P577 | Unix → 1969 | P582 |
| 28 | influenced by | P737 | Item | statement | Subjekt wurde durch diese Entität beeinflusst oder inspiriert | Lua → C++ | -- |
| 29 | input device | P479 | Item | statement | Eingabegerät zur Interaktion mit einer Software oder einem Gerät | Counter-Strike → Maus, Tastatur | -- |
| 30 | output device | P5196 | Item | statement | Ausgabegerät zur Interaktion mit Software, Konsole oder Grafikkarte | Adrift → Oculus Rift | -- |
| 31 | IRC channel URL | P1613 | URL | statement | Offizieller IRC-Kanal einer Institution oder eines Projekts | Inkscape → `http://irc.lc/gimp/inkscape/` | -- |
| 32 | language of work or name | P407 | Item | statement | Sprache des Werks oder Namens; für Personen P103 bzw. P1412 | Autobiografia di Alice Toklas → Italienisch | -- |
| 33 | copyright license | P275 | Item | statement | Lizenz, unter der das Werk veröffentlicht ist | Inkscape → GNU GPL v2 | -- |
| 34 | media type | P1163 | String | statement | IANA-registrierte Kennung eines Dateityps | SVG → `image/svg+xml` | -- |
| 35 | movement | P135 | Item | statement | Bewegung, die das Softwareprojekt unterstützt; z. B. GNU Project (Q7598) → free software movement (Q1076638) | GNU social → free software movement | -- |
| 36 | official blog URL | P1581 | URL | statement | URL des Blogs dieser Software | RStudio → `http://blog.rstudio.org/` | -- |
| 37 | official website | P856 | URL | statement | URL der Website dieser Software | RStudio → `http://www.rstudio.org/` | -- |
| 38 | Open Hub ID | P1972 | External ID | statement | Kennung freier Software bei OpenHub.net | Mozilla Firefox → `firefox` | -- |
| 39 | operating system | P306 | Item | statement | Betriebssystem, auf dem die Software läuft, bzw. das auf Hardware installierte OS | GIMP → Linux | -- |
| 40 | package management system | P3033 | Item | statement | Paketverwaltung, über die die Software publiziert wird | Mozilla Firefox → dpkg | -- |
| 41 | part of | P361 | Item | statement | Größere Software enthält diese Software, oder sie gehört zu einer Gruppe wie dem GNU Project (Q7598) | Speex → GNU Project | has part(s) |
| 42 | platform | P400 | Item | statement | Plattform, für die ein Werk entwickelt oder veröffentlicht wurde | Mozilla Firefox → x86 | -- |
| 43 | port | P1641 | Quantity | statement | Standard-Kommunikationsendpunkt in TCP, UDP o. a. | SMTP → 25 | -- |
| 44 | price | P2284 | Quantity | statement | Veröffentlichter oder gezahlter Preis (mit Währungseinheit) | Warfarin 1 mg → 1.18 USD | -- |
| 45 | programmed in | P277 | Item | statement | Programmiersprache(n), in der/denen die Software entwickelt wird | MediaWiki → PHP | -- |
| 46 | publication date | P577 | Point in time | statement | Datum der Erstveröffentlichung eines Werks | Node.js → 27 May 2009 | P582 |
| 47 | readable file format | P1072 | Item | statement | Dateiformat, das ein Programm öffnen und lesen kann | Inkscape → SVG | -- |
| 48 | part of the series | P179 | Item | statement | Reihe, die das Subjekt enthält | Windows 8.1 → Windows NT | -- |
| 49 | software engine | P408 | Item | statement | Von diesem Item eingesetzte Software-Engine | Wikipedia → MediaWiki | -- |
| 50 | software quality assurance | P2992 | Item | statement | QA-Prozess für eine bestimmte Software | CKAN → continuous integration | -- |
| 51 | SQA / archive URL | P1065 | URL | qualifier | URL, unter der die QA-Berichte archiviert werden | Loomio → CI, archive URL: `https://travis-ci.org/loomio/loomio` | -- |
| 52 | SQA / described at URL | P973 | URL | qualifier | URL, die den QA-Prozess beschreibt | Loomio → CI, described at: `.../.travis.yml` | -- |
| 53 | computes solution to | P2159 | Item | statement | Problem, das dieser Algorithmus oder diese Methode löst | Dijkstra-Algorithmus → kürzeste Wege | -- |
| 54 | source code repository URL | P1324 | URL | statement | Öffentliches Quellcode-Repository | OpenVPN → `https://gitlab.com/openvpn/openvpn` | -- |
| 55 | SourceForge project | P2209 | External ID | statement | Kennung eines offiziellen SourceForge-Repositories | FileZilla → `filezilla` | -- |
| 56 | Stack Exchange tag | P1482 | URL | statement | Tag auf den Stack-Exchange-Websites | PHP → `http://stackoverflow.com/tags/php` | -- |
| 57 | TeX string | P1993 | String | statement | String zur Darstellung eines Konzepts in TeX oder LaTeX | Binomialverteilung → `\binom{n}{k}` | -- |
| 58 | Ubuntu package | P3473 | External ID | statement | Name des offiziellen Ubuntu-Pakets | GIMP → `gimp` | -- |
| 59 | Unicode character | P487 | String | statement | Einzelnes Unicode-Zeichen, das das Item repräsentiert; nur in NFC-Form, kein Steuerzeichen | € → € | -- |
| 60 | user manual URL | P2078 | URL | statement | Link zum Benutzerhandbuch des Subjekts | darktable → `https://www.darktable.org/usermanual/index.html.php` | -- |
| 61 | writable file format | P1073 | Item | statement | Dateiformat, das ein Programm erzeugen oder schreiben kann | Inkscape → SVG | -- |
| 62 | digital rights management system | P1032 | Item | statement | DRM-Technologien zur Nutzungskontrolle nach dem Verkauf | Neverwinter Nights → SecuROM | -- |
| 63 | distribution format | P437 | Item | statement | Methode oder Typ der Distribution | GTA V → Blu-ray Disc | -- |
| 64 | swMATH work ID | P6830 | External ID | statement | Kennung des Informationsdienstes für mathematische Software | Maple → `545` | -- |

FLOSS-spezifische Properties sind im
[FLOSS project](https://www.wikidata.org/wiki/Wikidata:WikiProject_Informatics/FLOSS)
dokumentiert, Videospiel-Properties im
[Video games project](https://www.wikidata.org/wiki/Wikidata:WikiProject_Video_games).

---

## 2. instance of (P31)

| Titel | ID | Datentyp | Rolle | Beschreibung | Beispiel |
|-------|----|----------|-------|--------------|----------|
| instance of / start time | P580 | Point in time | qualifier | Zeitpunkt, ab dem eine Entität existiert bzw. ein Statement gilt | LimeWire → abandonware, start time: 27 October 2010 |

Wird eine Software nicht mehr gepflegt, sollte *abandonware* (Q281039) als P31
gesetzt werden, mit Qualifiern P580 und P582 (wenn die Software *zeitweise*
ungepflegt war) oder P585 (wenn kein Zeitraum bekannt ist).

---

## 3. software version identifier (P348)

| Titel | ID | Datentyp | Rolle | Beschreibung | Beispiel |
|-------|----|----------|-------|--------------|----------|
| software version identifier | P348 | String | statement | Numerische oder nominale Kennung einer Version eines Programms oder Dateiformats, aktuell oder vergangen | Bugzilla → `4.5.1` |

**Rangkonvention:** Die neueste Version wird als *preferred* markiert, alle
anderen behalten *normal rank* -- nicht *deprecated*, weil ein Statement nicht
falsch wird, sobald eine neue Version erscheint. Alte Versionen sollen nicht
entfernt werden, da der historische Verlauf auswertbar bleiben soll (z. B. für
automatisch generierte Grafiken).

### Qualifier zu P348

| Titel | ID | Datentyp | Beschreibung | Beispiel |
|-------|----|----------|--------------|----------|
| version type | P548 | Item | Versionstyp: alpha, beta, stable | Bugzilla 5.1.1 → beta version |
| publication date | P577 | Point in time | Datum der Erstveröffentlichung dieser Version | Bugzilla 5.1.1 → 16 May 2016 |
| download URL | P4945 | URL | URL, über die das Werk heruntergeladen werden kann | CAPD library 4.2.153 → `https://sourceforge.net/projects/capd/files/4.2.153/src/capd-4.2.153.tar.gz` |
| DOI | P356 | External ID | Digital Object Identifier (nur Großbuchstaben) | Chemistry Development Kit 1.5.13 → `10.5281/zenodo.50388` |
| title | P1476 | Monolingual text | Name der Version, wenn ein Release zusätzlich zur Nummer einen Namen trägt | Swfdec 0.9.2 → *Bloxorz* |

**version type:** Der Typ soll grundsätzlich nicht geändert werden. Beispiel --
0.0.3 erscheint im September als beta und im Oktober als stable: dafür werden
*zwei* Statements angelegt, jeweils mit eigenem `version type`, eigener
`publication date` und eigener Referenz.

**publication date:** Bei abweichenden Quellen ist die verlässlichste zu
bevorzugen. Ist ein *git tag* auf v1.2 am 3. Juli gesetzt und ein Blogpost
kündigt sie am 5. Juli an, gilt das Datum des Tags.

**download URL:** Bei mehreren Architekturen oder Plattformen dürfen alle URLs
angegeben werden. Wird nur eine genannt, ist die mit dem Quellcode zu
bevorzugen (Beispiel: CAPD library, Q5008740).

---

## 4. API als Teil einer Software

Ein *application programming interface* (Q165194) ist als P279-Unterklasse
P361 (*part of*) der Software (Q7397), die es implementiert. Beispiel: OSM API
(Q25822543).

---

## 5. Qualifier: has characteristic (P1552) → mirror storage (Q654822)

| Titel | ID | Datentyp | Rolle | Beschreibung | Beispiel |
|-------|----|----------|-------|--------------|----------|
| source code repository URL / has characteristic | P1552 | Item | qualifier | Spiegel eines Quellcode-Repositories oder einer anderen Webressource | id Tech 3 → `https://github.com/id-Software/Quake-III-Arena`, has characteristic: mirror storage |

Ist ein P1324 oder P856 ein *mirror storage* (Q654822), erhält es den Qualifier
P1552. Gibt es mehrere mögliche Quellen für den Spiegel, wird die URL, von der
gespiegelt wird, als *reference URL* (P854) im Referenzabschnitt gesetzt.

---

## 6. Sources / References

| Property | ID | Verwendung |
|----------|----|------------|
| retrieved | P813 | Datum, das sich auf die Information im Referenzabschnitt bzw. den Wert des Claims bezieht. Besonders nützlich für Bots (z. B. `User:FLOSSbot`), die etwa P1324-URLs alle 30 Tage auf Erreichbarkeit prüfen. |
| RfC ID | P892 | Verweis auf ein Request-for-Comments-Dokument von IETF und Internet Society (ohne Präfix "RFC"). |
| ISO standard | P503 | ISO-Standard, der das Item normiert. |

---

## 7. Ergänzung: name (P2561)

> Nicht auf der WikiProject-Seite gelistet, in der Praxis für Software aber
> einschlägig und daher hier ergänzt.

| Titel | ID | Datentyp | Rolle | Beschreibung |
|-------|----|----------|-------|--------------|
| name | P2561 | Monolingual text | statement | Name der Entität als Statement, sprachmarkiert |

P2561 tritt *neben* das Item-Label, nicht an dessen Stelle. Das Label trägt den
aktuellen Namen -- einen pro Sprache, nicht belegbar, nicht datierbar. Als
Statement kann P2561 dagegen Qualifier, Referenzen und Ranks aufnehmen. Für
Software heißt das konkret:

- Umbenennungen bleiben nachvollziehbar: früherer Name mit P580/P582 datiert,
  aktueller Name im *preferred rank*.
- Namensvarianten und Schreibweisen lassen sich mit Quelle belegen, statt sie
  in die Aliase zu schieben, wo sie unbelegt bleiben.
- Der Name eines einzelnen Release wird davon abgegrenzt: dafür ist P1476
  (*title*) als Qualifier an P348 vorgesehen (siehe Abschnitt 3).

---

## 8. standard UNIX utility / IEEE Std 1003.1, 2013

Utilities wie `chmod` sind *standard UNIX utility or command* (Q18343316), AKA
IEEE Std 1003.1, 2013. Das passende Item erhält P31 → Q18343316 mit einer
Referenz auf die entsprechende opengroup.org-Seite. Existiert eine Software,
die den Standard implementiert (etwa GNU Core Utilities, Q1348204), wird das
Utility als P361 dieser Software gesetzt. Musterbeispiel: chmod (Q310986).
