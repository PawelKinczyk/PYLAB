# PYLAB Roadmap — nowe funkcje

Dokument roboczy: architektura i kolejność wdrożenia funkcji ustalonych w burzy mózgów (2026-07-30). Kategorie A-G odpowiadają oryginalnej notatce. Kategoria F (Otworowanie) jest wstrzymana do czasu dostarczenia materiału źródłowego (skrypt Dynamo, opis `IND_Role`).

Każda funkcja niżej ma trzy stałe podsekcje: **API Revita** (konkretne klasy/metody, optymalny wybór), **UI/menu** (jak wygląda okno/przepływ), **Ustawienia** (co i gdzie jest konfigurowalne, w jakim formacie, gdzie żyje plik).

## Zasady pracy

- **Jedna gałąź na funkcję** (`feat/<slug>`), zgodnie z dotychczasową konwencją repo (`feat/add-bypass-button-guide`, `fix/ui-of-function`).
- Funkcje ze wspólnym fundamentem (np. cała seria D, B8→B9) mają gałąź bazową scaloną do `main` **przed** startem gałęzi zależnych — nie pracujemy równolegle na wspólnym kodzie na osobnych gałęziach.
- Każda funkcja kończy się aktualizacją `docs/button-guide.md`.
- Reużywamy istniejące wzorce zamiast pisać od nowa.

## Konwencja przechowywania ustawień (obowiązuje wszystkie funkcje niżej)

W repo już istnieją dwa różne wzorce przechowywania stanu — trzymamy się obu, każdy do innego celu:

1. **Ustawienia zespołowe/standardy** (naming convention, katalog otworów, lista worksetów per typ projektu, definicje filtrów) → JSON **w folderze przycisku w rozszerzeniu**, commitowany do gita, edytowalny przez dedykowany przycisk-edytor. To dokładny wzorzec `Air_terminal_calc_setting.pushbutton` + `air_terminals_supply_settings.json` (żyje obok `script.py`, edytor nadpisuje ten sam plik). Zespół dostaje aktualizacje przez `git pull`, nie przez ręczną synchronizację.
2. **Preferencje osobiste/ostatnio użyte wartości** (ostatni kierunek bypassu, ostatnio wybrany kierunek sekcji, rozmiar okna) → JSON w `%APPDATA%\pyRevit\PYLAB\<Tool>\...`, wzorzec `Bypass.pushbutton` i `FamilyShortcut.pushbutton/family_shortcut_store.py`. Per-użytkownik, nie commitowane.

Przy każdej funkcji niżej explicite zaznaczone, która kategoria dotyczy.

## Kolejność faz

| Faza | Zawartość | Blokuje |
|---|---|---|
| 0 | B8 — spike API (Revit 2023+ parameter/category binding) | B8 core, B9 |
| 1 | A6, A9, C3+C4, E2a, G — niezależne, mogą iść równolegle | — |
| 1 | D-core (framework health-checków) + D4 (silnik nazewnictwa) — równolegle do fazy 1 | D1, D2, D3, D5, D8 |
| 2 | B8 core (po spike) | B9 |
| 2 | D1, D2, D3 (po D-core) | — |
| 3 | B9 (po B8 core) | — |
| 3 | D5 (po D4 silnik) | D8 |
| 4 | D8 (po D4 + D5) | — |
| 5 | E2b (generowanie nowej rodziny — wymaga wyboru template) | — |
| wstrzymane | Cała kategoria F | czeka na materiał źródłowy |

---

## A: Systemy MEP

### A6 — Select all elements in pipe/duct system (start-koniec)

**Problem**: ręczne zaznaczanie całej trasy między dwoma punktami systemu.

**API Revita**:
- Pick 2 elementów: `uidoc.Selection.PickObject(ObjectType.Element, filter)` wywołane dwa razy z osobnym promptem ("Pick start element" / "Pick end element"). Filtr kategorii identyczny jak `PIPE_MAIN`/`DUCT_MAIN` w `MeasureElem.pushbutton` (Pipes/Pipe Fittings/Pipe Accessories albo Ducts/Duct Fittings/Duct Accessories — jedna rodzina na raz).
- **Optymalizacja kluczowa**: nie przeszukuj całego modelu. Pipe/Duct mają właściwość `.MEPSystem` (`PipingSystem`/`MechanicalSystem`), a system ma `.PipingNetwork`/`Elements` — to daje od razu **ograniczony zbiór elementów danego systemu**. BFS uruchamiamy tylko w obrębie tego zbioru, nie po całym dokumencie.
- Graf połączeń: dla każdego elementu w zbiorze — `element.ConnectorManager.Connectors` (Pipe/Duct) albo `element.MEPModel.ConnectorManager.Connectors` (fittings/accessories jako `FamilyInstance`). Każdy `Connector.AllRefs` (`ConnectorSet`) daje connectory sąsiadów, `.Owner.Id` = sąsiedni element.
- BFS od elementu startowego do końcowego — **BFS z natury zwraca najkrótszą ścieżkę** w grafie nieważonym, więc pętla/ring w systemie (wiele możliwych ścieżek) rozwiązuje się sam: pierwsza chwila dotarcia do celu = najkrótsza. Nie trzeba pisać osobnego tie-breaka.
- Zaznaczenie: `uidoc.Selection.SetElementIds(ICollection<ElementId>)`.

**UI/menu**: brak okna — tylko dwa kolejne pick-e (`forms.WarningBar` z promptem, jak `ActiveWorkset.pushbutton`), wynik = zaznaczenie w widoku + krótki raport w output window (liczba elementów, długość całkowita trasy).

**Ustawienia**: brak — funkcja bezstanowa, nic do konfigurowania.

**Panel**: MEPHelp.Panel. **Branch**: `feat/a6-select-system-path`

### A9 — Water volume + rozszerzone grupowanie (rozbudowa A3)

**Problem**: dodatkowo do długości, potrzebna pojemność wodna instalacji rurowej.

**API Revita**:
- Inner diameter: `BuiltInParameter.RBS_PIPE_INNER_DIAM_PARAM` (wartość liczona przez Revit z rzeczywistego schedule rury — dokładniejsza niż nominalna średnica pomniejszona o stałą grubość ścianki, bo uwzględnia rzeczywisty typ/schedule). Fallback jak w istniejącym kodzie: jeśli parametr nieobecny, pomiń element (licz do `skipped_count`, nie zgaduj grubości ścianki).
- Objętość na element: `V = pi * (inner_diameter/2)^2 * length` (stopy³ w jednostkach wewnętrznych Revita), sumowana per grupa `pipe_group_key` (już istniejący klucz typ+średnica).
- Konwersja do litrów do raportu: `1 ft³ = 28.3168 L` (praktyczniejsza jednostka dla instalatora niż m³).

**UI/menu**: rozszerzenie istniejącego flow w `MeasureElem.pushbutton` — przed pickiem elementów, jeśli wykryta rodzina to Pipe, dopytać `forms.CommandSwitchWindow.show(['Tak', 'Nie'], message='Oblicz też pojemność wodną?')` (dokładnie ten sam widget co w `Air_terminal_calc_setting.pushbutton`). Dla Duct/Wall pytanie pomijane (nie dotyczy).

**Ustawienia**: brak — parametr pytany za każdym uruchomieniem (jak reszta MeasureElem), nie zapamiętywany.

**Branch**: `feat/a9-measure-water-volume`

---

## B: Dane i parametry

### B8 — Zarządzanie project parameters + category binding (RVT 2023+)

**Problem**: ręczne dodawanie/usuwanie parametrów i ich przypisań do kategorii przez UI Revita.

**Zakres**: jeden otwarty model, tylko Revit 2023+. Realny zakres to **rebinding istniejących shared parameters do kategorii** — to NIE wymaga `ForgeTypeId` (tamten typ dotyczy tylko tworzenia zupełnie nowej definicji parametru, np. `ExternalDefinitionCreationOptions(name, forgeTypeId)`). `ForgeTypeId` potrzebny tylko jeśli dorzucamy też "utwórz nowy shared parameter" — trzymajmy to jako osobną, późniejszą opcję w tym samym narzędziu, nie w v1.

**API Revita**:
- Odczyt definicji: `app.OpenSharedParameterFile()` → `DefinitionFile.Groups` → `DefinitionGroup.Definitions` (`ExternalDefinition`).
- Odczyt aktualnego bindingu: `doc.ParameterBindings` (`BindingMap`) + `BindingMapIterator` — klucz `Definition`, wartość `ElementBinding` (`InstanceBinding`/`TypeBinding`), każdy ma `.Categories` (`CategorySet`).
- **Do zweryfikowania w spike (dokładnie to, co budzi niepewność w tym punkcie)**: budowa `CategorySet` zmieniała się między wersjami Revita — starsze API: `app.Create.NewCategorySet()`, nowsze (2024+): bezparametrowy konstruktor `new CategorySet()`. Trzeba sprawdzić który wariant działa na docelowych wersjach (2023-2026) i albo wybrać jeden próg wsparcia, albo rozgałęzić przez `getattr`/`try-except` (dokładnie jak `Bypass.pushbutton` robi z `SpecTypeId`/`UnitType`).
- Zmiana bindingu istniejącego parametru: **nie da się zmutować `CategorySet` istniejącego bindingu w miejscu** — trzeba zbudować nowy `CategorySet`, nowy `InstanceBinding`/`TypeBinding` i wywołać `doc.ParameterBindings.ReInsert(definition, newBinding)`, potem `doc.Regenerate()`.
- Moduł współdzielony z B9: `parameter_category_binding.py` z `list_shared_parameters(doc)`, `get_bound_categories(doc, param)`, `set_bound_categories(doc, param, categories)`.

**UI/menu**: `System.Windows.Forms.DataGridView` — wiersze = shared parameters, kolumny = kategorie projektu jako `DataGridViewCheckBoxColumn` (macierz, nie sekwencja pytań — Revit ma ~100+ kategorii, sekwencyjne pytania jak w Air Terminal editor byłyby nieużywalne w tej skali). Nad siatką textbox filtrujący kategorie po nazwie (kategorii jest za dużo żeby przewijać bez filtra). Przycisk "Zastosuj" robi diff między stanem bieżącym a zaznaczeniami i woła `set_bound_categories` tylko dla zmienionych parametrów. Przed zapisem dialog potwierdzenia (`MessageBox`) — zmiana bindingu może ukryć/odsłonić dane w instancjach, operacja nie jest trywialnie odwracalna.

**Ustawienia**: brak configu — to narzędzie interaktywne czytające stan wprost z dokumentu, nic nie trzeba przechowywać między sesjami.

**Faza 0 (spike)**: `spike/b8-api-research` — samodzielny branch bez UI, tylko potwierdzenie które wywołania `CategorySet`/`BindingMap` działają na 2023/2024/2025/2026 zainstalowanych u Ciebie.
**Branch (core)**: `feat/b8-parameter-category-manager` (na bazie spike)

### B9 — Batch parameter add z Excel/CSV (matrix binding)

**Problem**: masowe przypisywanie parametrów współdzielonych do kategorii przez arkusz.

**API Revita**: silnik identyczny jak B8 (`parameter_category_binding.py`) — B9 to tylko inny interfejs (Excel zamiast DataGridView) na te same trzy funkcje.

**Excel — konkretna biblioteka do reużycia**: `PlaceInRoomsSpaces.pushbutton` NIE używa openpyxl/xlrd — steruje realnym Microsoft Excel przez COM interop (`Type.GetTypeFromProgID("Excel.Application")` + `clr`). B9 ma reużyć dokładnie ten sam helper (nie wprowadzać nowej zależności typu openpyxl, która pod IronPython bywa problematyczna do zainstalowania). Wymaga zainstalowanego Excela na maszynie — tak samo jak dziś w PlaceInRoomsSpaces, więc brak nowego ryzyka środowiskowego.

**Format arkusza**: wiersz = parametr współdzielony (nazwa + GUID w ukrytej kolumnie pomocniczej — patrz "Ryzyko" niżej), kolumna = kategoria projektu, komórka `0/1` = czy ma być bindowany. Eksport woła `get_bound_categories` dla każdego parametru i wypełnia macierz; import czyta zmienione komórki i woła `set_bound_categories` tylko dla różnic (diff, nie pełny re-apply — szybciej i bezpieczniej).

**Ryzyko**: dopasowanie wiersza do parametru **po samej nazwie jest niebezpieczne** — dwa różne shared parameters mogą mieć tę samą nazwę wyświetlaną, tożsamość shared parameter to GUID. Arkusz musi nieść GUID (osobna, np. ukryta, kolumna), import matchuje po GUID, nie po tekście nazwy.

**UI/menu**: przycisk "Eksportuj do Excela" / "Importuj z Excela" (dwa tryby przez `forms.CommandSwitchWindow`, jak w Air Terminal settings), reszta dzieje się w Excelu — użytkownik edytuje 0/1 tam, nie w oknie Revita.

**Ustawienia**: brak własnych — dziedziczy z B8.

**Zależność**: wymaga scalonego `feat/b8-parameter-category-manager`. **Branch**: `feat/b9-parameter-excel-import`

---

## C: Dokumentacja i arkusze

### C3+C4 — Generator widoków z Room/Space (przekroje + 3D)

**Problem**: ręczne tworzenie przekrojów/widoków 3D per pomieszczenie do dokumentacji.

**API Revita**:
- Enumeracja pomieszczeń/przestrzeni: `FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms)` / `OST_MEPSpaces` — dokładnie ten collector co już działa w `PlaceInRoomsSpaces.pushbutton`, reużyć 1:1 (razem z filtrem wyszukiwania po numerze/nazwie).
- **Zasięg pomieszczenia — nie `get_BoundingBox`**: dla pomieszczeń nieregularnych (L-shape) sam bounding box bywa zawyżony/zaniżony względem realnego kształtu. Poprawniej: `room.GetBoundarySegments(new SpatialElementBoundaryOptions())` → realne krzywe granicy → policzyć min/max XY z punktów krzywych, dopiero na tym budować `BoundingBoxXYZ` dla przekroju. Dokładniejszy crop niż surowy bounding box.
- Przekrój: znaleźć `ViewFamilyType` dla sekcji — `FilteredElementCollector(doc).OfClass(ViewFamilyType)` filtrowany po `.ViewFamily == ViewFamily.Section` — potem `ViewSection.CreateSection(doc, viewFamilyTypeId, sectionBoxTransformed)`. `Transform` sekcji ustawiony wg wybranego kierunku (patrz niżej).
- Widok 3D + section box: **reużyć wprost matematykę z `Element3DFocus.pushbutton`** (otwarcie/utworzenie `{3D}`, `View3D.SetSectionBox(box)`) zamiast pisać drugi raz tę samą logikę.
- Kierunek: stała lookup-lista (nie config JSON — to geometria, nie standard firmowy) `{"Północ": (0,1,0), "Południe": (0,-1,0), "Wschód": (1,0,0), "Zachód": (-1,0,0)}` mapowana na bazę `Transform` przekroju.
- **Unikalność nazw**: Revit rzuca wyjątek przy duplikacie nazwy widoku i przy niedozwolonych znakach (`: { } [ ] | ; < > ? ' ~`). Trzeba: (1) sanitizować nazwę pomieszczenia/numeru z tych znaków, (2) sprawdzić kolizję przez `FilteredElementCollector(doc).OfClass(View)` po nazwie i dokładać sufiks `(2)`, `(3)`... w pętli przed `view.Name = ...`.

**UI/menu**: jedno okno (WinForms, layout jak `PlaceInRoomsSpaces.pushbutton`):
1. Lista pomieszczeń/przestrzeni z checkboxami + textbox filtrujący.
2. Lista kierunków z checkboxami (można wybrać więcej niż jeden — po jednej sekcji na zaznaczony kierunek na pomieszczenie).
3. Checkbox "Dogeneruj widok 3D z section boxem".
4. Przycisk "Generuj" → pętla po zaznaczonych pomieszczeniach × kierunkach, raport sukces/porażka w output window (wzorzec jak `PlaceInRoomsSpaces` już robi).

**Ustawienia**: wzorzec nazw widoku (`"{RoomNumber} - {RoomName} - Przekrój {Direction}"`) jako pojedynczy string-template w małym JSON obok skryptu (kategoria "ustawienia zespołowe" — cała firma ma trzymać się jednego wzorca nazw), edytowalny przez prosty `forms.ask_for_string`.

**Branch**: `feat/c3c4-room-view-generator`

---

## D: Model Health

Wspólny fundament dla D1-D5, D8 (D7 poza zakresem — zostaje w Dynamo, D6 zniesione, wchłonięte przez D4).

### D-core — Framework health-checków

**API Revita**: brak własnego — to warstwa infrastrukturalna pod resztą D.

**Architektura**: nowy panel `ModelHealth.Panel`. Wspólny moduł `health_report.py` (buduje tekstowy raport do output window, ten sam styl co `MeasureElem`/`Bypass`) + wspólny `config_loader.py` czytający JSON-y configów opisanych niżej.

**UI/menu**: `ModelHealth.Panel` dostaje własny przycisk na check (D1, D2, D3, D5, D8 — każdy osobny pushbutton, nie jeden wspólny wizard, bo każdy generuje inny, niezależny raport i można go chcieć odpalić osobno) + jeden wspólny przycisk "Ustawienia standardu" edytujący configi D4/D5/D8.

**Ustawienia**: brak własnych na tym poziomie — patrz D4/D5.

**Branch**: `feat/d-health-framework-core`

### D4 — Silnik standardu nazewnictwa (widoki, szablony, przekroje, zestawienia, rodziny, filtry)

**Problem**: standard nazewnictwa różni się per projekt/biuro — musi być definiowalny przez użytkownika, nie hardcoded. Sam standard jeszcze nie istnieje jako spisany dokument — silnik ma przyjąć dowolną definicję, treść dogrywamy osobno.

**API Revita — źródła nazw per typ elementu**:
- Widoki: `FilteredElementCollector(doc).OfClass(View)`, z wykluczeniem `view.IsTemplate` chyba że sprawdzamy akurat szablony.
- Szablony widoków: te same obiekty `View` z `.IsTemplate == True` — osobny target w configu, nie osobna kolekcja.
- **Sekcje to podzbiór widoków, nie osobna kategoria configu** — Revit: `ViewSection` dziedziczy po `View`. Zamiast osobnego targetu "sections" rozdzielonego od "views", lepiej trzymać jeden target `views` z regułami różnicowanymi po `View.ViewType` (`ViewType.Section`, `ViewType.ThreeD`, `ViewType.FloorPlan`...) — unika podwójnego liczenia tego samego widoku w dwóch configach.
- Zestawienia: `FilteredElementCollector(doc).OfClass(ViewSchedule)` — wykluczyć wewnętrzne (`IsTemplate`, harmonogramy rewizji tytułowych).
- Rodziny: `FilteredElementCollector(doc).OfClass(Family)` (`.Name`) + opcjonalnie zagnieżdżone `FamilySymbol.Name` dla typów.
- Filtry: `FilteredElementCollector(doc).OfClass(ParameterFilterElement)` (`.Name`).
- Arkusze: `FilteredElementCollector(doc).OfClass(ViewSheet)` — **uwaga**: arkusz ma DWA nazywalne pola, `.Name` i `.SheetNumber` — standard nazewnictwa zwykle dotyczy numeru, nie nazwy opisowej. Config musi rozróżniać które pole sprawdzamy.

**Silnik walidacji** (czysty Python, bez API Revita — tylko string ops): rozbij nazwę po `delimiter`, idź człon po członie: `type: closed` → sprawdź czy wartość jest w `variants`; `type: freetext` → sprawdź `min_len`/`max_len`. Raport wskazuje który człon zawiódł i czego oczekiwano.

**Format configu** (`naming_standards.json`, jeden plik, klucz per target — łatwiej wersjonować niż 6 osobnych plików):
```json
{
  "views": {
    "delimiter": "_",
    "segments": [
      {"name": "dyscyplina", "type": "closed", "variants": ["ARC", "MEP", "STR"]},
      {"name": "poziom", "type": "freetext", "min_len": 1, "max_len": 3},
      {"name": "typ_widoku", "type": "closed", "variants": ["RZUT", "PRZEKROJ", "3D"]},
      {"name": "opis", "type": "freetext", "max_len": 20}
    ]
  },
  "sheets": { "...": "..." },
  "families": { "...": "..." },
  "filters": { "...": "..." },
  "schedules": { "...": "..." }
}
```

**UI/menu (edytor configu)**: `DataGridView` — wiersze = człony danego targetu, kolumny = `nazwa / typ (closed|freetext) / warianty (comma-separated) / min_len / max_len`. Wybór targetu (views/sheets/families/filters/schedules) przez dropdown nad siatką. To upgrade względem sekwencyjnych `forms.ask_for_string` z Air Terminal editor — człony i warianty są z natury tabelaryczne, siatka jest szybsza do edycji niż seria promptów.

**Świadomie poza v1**: człony opcjonalne/trailing, zależność wariantu jednego członu od innego, case-sensitivity toggle.

**Ustawienia**: kategoria "zespołowa" — `naming_standards.json` w folderze przycisku, commitowany.

**Zależność**: `feat/d-health-framework-core`. **Branch**: `feat/d4-naming-standard-engine`

### D1 — Preflight checks (rozmiar rodzin, licznik linii, autor widoku)

**API Revita**:
- Licznik linii szczegółu: `FilteredElementCollector(doc, view.Id).OfClass(CurveElement).OfCategory(BuiltInCategory.OST_Lines)` — **collector skopowany do widoku** (konstruktor 2-argumentowy), nie manualne filtrowanie całego modelu po widoku — dużo tańsze na dużych projektach.
- Autor/ostatnia zmiana: `WorksharingUtils.GetWorksharingTooltipInfo(doc, element.Id).LastChangedBy` — działa tylko gdy `doc.IsWorkshared == True`; dla modeli bez worksharingu raportować "N/D", nie rzucać wyjątku.
- **Rozmiar rodziny — nie ma bezpośredniego API na rozmiar w bajtach dla załadowanej rodziny.** Dwa poziomy:
  - Szybki proxy (domyślny): liczba `FamilySymbol` w rodzinie (`family.GetFamilySymbolIds().Count`), liczba zagnieżdżonych rodzin, liczba parametrów — "wynik złożoności" zamiast realnego rozmiaru, liczony bez dotykania dysku.
  - Dokładny rozmiar (opt-in, wolniejszy): `doc.EditFamily(family)` → tymczasowy `SaveAs` do folderu tymczasowego → `os.path.getsize` → usunięcie pliku tymczasowego. Realny rozmiar, ale kosztowny przy setkach rodzin — checkbox "Dokładny rozmiar (wolniejsze)" w UI, wyłączony domyślnie.

**UI/menu**: pojedynczy przycisk w `ModelHealth.Panel`, uruchamia wszystkie trzy podchecki naraz, raport w output window; jeden checkbox (opisany wyżej) do wolnego trybu rozmiaru rodzin.

**Ustawienia**: brak configu — progi (np. "flaguj rodziny z >50 typami") mogą być stałymi w kodzie na start, do configu tylko jeśli okaże się potrzebne w praktyce.

**Zależność**: `feat/d-health-framework-core`. **Branch**: `feat/d1-preflight-checks`

### D2 — Kontrola worksetów

**API Revita**:
- `FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)` — enumeracja, sprawdzenie nazw wg listy/wzorca z configu.
- Elementy nadal na domyślnym worksecie (`Workset1`/"0"): **`ElementWorksetFilter`** jako gotowy `ElementFilter` podany wprost do collectora (`FilteredElementCollector(doc).WherePasses(new ElementWorksetFilter(worksetId))`) — szybsze niż pętla po wszystkich elementach z ręcznym sprawdzaniem `.WorksetId`.

**UI/menu**: pojedynczy przycisk, raport listy niezgodnych worksetów + liczby elementów na domyślnym workseсie.

**Ustawienia**: lista dozwolonych nazw/wzorca worksetów — może współdzielić config z G1 (lista worksetów per typ projektu), zamiast trzymać osobno.

**Branch**: `feat/d2-workset-check`

### D3 — Kontrola przypięcia osi/poziomów/linków

**API Revita**: `FilteredElementCollector(doc).OfClass(Grid|Level|RevitLinkInstance)`, filtr po `.Pinned == False`, raport listy.

**UI/menu**: pojedynczy przycisk, brak opcji.

**Ustawienia**: brak.

**Branch**: `feat/d3-pin-check`

### D5 — Wykrywanie brakujących parametrów

**API Revita**: config = lista wymaganych parametrów per `BuiltInCategory`. **Ważne**: dla shared parameters identyfikacja po GUID, nie po nazwie wyświetlanej (dwa różne parametry mogą mieć tę samą nazwę — ten sam problem co w B9). Config przechowuje GUID + nazwę pomocniczą do wyświetlania. Odczyt: `element.get_Parameter(guid)` zamiast `LookupParameter(name)`.

**UI/menu**: pojedynczy przycisk, raport elementów z brakującym/pustym parametrem, grupowany po kategorii.

**Ustawienia**: `required_parameters.json` — lista `{category, parameter_guid, parameter_label}`, zespołowa, edytor: `DataGridView` (kategoria / GUID / etykieta), z przyciskiem "wybierz z pliku shared parameters" żeby nie wpisywać GUID ręcznie.

**Zależność**: `feat/d4-naming-standard-engine` (współdzieli mechanizm loadera configu, nie samą logikę). **Branch**: `feat/d5-missing-parameters`

### D8 — Walidacja zgodności dokumentacji z BIM standardem

**API Revita**: umbrella nad D4 + D5, plus:
- Kompletność arkuszy: lista wymaganych numerów/prefixów arkuszy z configu vs `FilteredElementCollector(doc).OfClass(ViewSheet)`.
- **Efekt synergii z C3+C4**: skoro widoki z generatora sekcji mają w nazwie numer pomieszczenia (ustalone wcześniej), D8 może sprawdzić "czy każde pomieszczenie ma wygenerowany komplet widoków" przez wyszukanie widoków, których nazwa zawiera dany numer pomieszczenia — kompletność dokumentacji per pomieszczenie bez dodatkowego mechanizmu powiązania.

**UI/menu**: pojedynczy przycisk, zbiorczy raport (sekcja per sub-check: nazewnictwo / parametry / kompletność arkuszy / kompletność widoków per pomieszczenie).

**Ustawienia**: `required_sheets.json` (lista wymaganych numerów/prefixów arkuszy) — nowy config, zespołowy, edytor analogiczny do D5.

**Zależność**: `feat/d4-naming-standard-engine` + `feat/d5-missing-parameters`. **Branch**: `feat/d8-bim-standard-compliance`

### D7 — poza zakresem

Zostaje w Dynamo. Brak roboty w PYLAB.

---

## E: Narzędzia produkcyjne

### E2 — Quick family by rectangle x/y/z

Dwie ścieżki, osobne przyciski w grupie pulldown (wzorzec `AirTerminalCalculator.pulldown` z siostrzanymi pushbuttonami — `QuickFamily.pulldown` z `Assign.pushbutton` i `Generate.pushbutton`).

**E2a — Assign existing family**

**API Revita**:
- Lista typów: `FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_GenericModel)`, wybór przez `forms.SelectFromList.show` (już używany widget, np. w Air Terminal settings deleter).
- Placement: `doc.Create.NewFamilyInstance(point, symbol, level, StructuralType.NonStructural)` — dokładnie ten sam wzorzec co już działa w `PlaceInRoomsSpaces.pushbutton`.
- **Ryzyko konkretne do zaadresowania w kodzie**: jeśli X/Y/Z sterowane parametrami na poziomie **typu** (nie instancji), zmiana wartości zmieni WSZYSTKIE instancje danego typu w projekcie, nie tylko nowo postawioną. Przed zmianą trzeba sprawdzić czy parametr jest instance-level; jeśli jest type-level, zduplikować typ (`symbol.Duplicate(newName)`) pod unikalną kombinację X/Y/Z zamiast nadpisywać współdzielony typ.

**UI/menu**: mały dialog — dropdown wyboru rodziny/typu + trzy pola liczbowe X/Y/Z + przycisk "Umieść" (pick punktu po zatwierdzeniu).

**Ustawienia**: brak configu, wartości wpisywane za każdym razem; ostatnio użyta rodzina zapamiętywana w `%APPDATA%` (preferencja osobista) jako wygoda.

**Branch**: `feat/e2a-quick-family-assign`

**E2b — Generate new family**

**API Revita**:
- Template: zamiast bundlować własny `.rft` w repo (ryzyko niedopasowania do wersji Revita 2022-2026, każda wersja ma nieco inny domyślny zestaw szablonów) — poprosić użytkownika o wskazanie **swojego zainstalowanego** `Generic Model.rft` przy pierwszym uruchomieniu (`forms.pick_file(file_ext='rft')`), zapamiętać ścieżkę w `%APPDATA%\pyRevit\PYLAB\QuickFamily\template_path.json` (per-maszyna, bo ścieżka instalacji Revita jest per-maszyna). Bezpieczniejsze niż zgadywanie API do auto-discovery szablonu.
- Tworzenie: `app.NewFamilyDocument(templatePath)` → nowy `Document` (family doc) → `familyDoc.FamilyCreate.NewExtrusion(...)` z prostokątnym profilem `CurveArrArray` wymiarowanym z X/Y/Z.
- **Decyzja zakresu**: geometria generowana jako **stała** (nie parametryczna z `FamilyManager.AddParameter`) — "quick family" to z założenia jednorazowy kształt, nie utrzymywana rodzina parametryczna. Jeśli w praktyce okaże się potrzebna parametryczność, to osobna, większa funkcja do dopisania później.
- Załadowanie z powrotem: `familyDoc.LoadFamily(doc)` → `Family` → `FamilySymbol.Activate()` → placement jak w E2a.

**UI/menu**: dialog z X/Y/Z + przycisk "Wskaż template" (tylko przy pierwszym użyciu, potem zapamiętane) + "Generuj i umieść".

**Ustawienia**: ścieżka do template `.rft` — preferencja osobista w `%APPDATA%`, nie zespołowa (ścieżka instalacji Revita różni się per stacja roboczą).

**Ryzyko**: najcięższa operacja API w tej fazie — edycja dokumentu rodziny w locie jest krucha, wymaga testowania na wielu wersjach Revita.

**Branch**: `feat/e2b-quick-family-generate` (osobno, później — faza 5)

---

## G: Project Setup

### G1+G2+G3 — Project Setup Wizard

**Problem**: powtarzalny setup nowego projektu (worksety, widoki koordynacyjne, filtry+parametry) rozbity na 3 ręczne kroki.

**API Revita**:
- G1 (worksety): `doc.IsWorkshared` — jeśli `False`, najpierw `doc.EnableWorksharing(...)`. Potem `Workset.Create(doc, name)` w pętli po liście z configu.
- G2 (widoki koordynacyjne): batch `ViewPlan.Create(doc, viewFamilyTypeId, levelId)` per poziom z configu, przypisanie `view.ViewTemplateId` i `view.SetViewRange(...)` wg konwencji z configu (mapowanie poziom→szablon).
- G3 (filtry + parametry): `ParameterFilterElement.Create(doc, name, categories, elementFilter)` z reguł w configu; jeśli w regule są project parameters — **współdzieli silnik `parameter_category_binding.py` z B8**, nie duplikuje kodu bindowania kategorii.
- **Atomowość**: cały wizard w jednym `TransactionGroup` (nie osobne sub-transakcje per krok jak w Bypass) — setup projektu ma być "wszystko albo nic": jeśli krok 2 się wywali, krok 1 też ma się cofnąć, żeby nie zostawić projektu w połowicznym stanie. `transactionGroup.RollBack()` przy błędzie, `.Assimilate()` przy sukcesie.

**UI/menu**: jedno okno WinForms:
1. `CheckedListBox` na górze: `[ ] Worksety`, `[ ] Widoki koordynacyjne`, `[ ] Filtry i parametry` — użytkownik zaznacza które kroki odpalić.
2. Dropdown "Typ projektu" (np. MEP/ARC/STR) — wybiera który zestaw z configu ma być użyty (różne biura/branże mają różne listy worksetów/szablonów).
3. Pod checklistą dynamicznie pokazywany podgląd tego co zostanie utworzone (lista worksetów / mapowanie poziom→szablon / lista filtrów) — tylko podgląd, edycja configu w osobnym przycisku ustawień, nie w tym oknie.
4. Przycisk "Uruchom" → jeden `TransactionGroup`, raport w output window.

**Ustawienia**: `project_setup_templates.json`, zespołowy, klucz per typ projektu:
```json
{
  "MEP": {
    "worksets": ["MEP-Wod-Kan", "MEP-Wentylacja", "MEP-Elektryka"],
    "views": [{"level": "Poziom 0", "template": "MEP Koordynacja"}],
    "filters": [{"name": "Kolizje", "categories": ["Pipes", "Ducts"], "rule": "..."}]
  }
}
```
Edytor: osobny przycisk "Ustawienia Project Setup" z `DataGridView` per sekcja (worksety jako lista tekstowa edytowalna wiersz-po-wierszu, mapowanie widoków jako dwie kolumny poziom/szablon, filtry jako tabela nazwa/kategorie/reguła).

**Branch**: `feat/g-project-setup-wizard`

---

## F: Otworowanie — wstrzymane

Cała kategoria (F1-F12) czeka na dostarczenie materiału źródłowego: skrypt/opis logiki z Dynamo oraz wyjaśnienie `IND_Role` (F5). Bez tego F1 (fundament dla F2-F12) nie da się zaplanować. Wracamy do tej sekcji gdy materiał będzie dostępny.

---

## Otwarte kwestie do domknięcia w trakcie implementacji

- **D4/D8**: treść samego standardu nazewnictwa (jakie konkretnie warianty/człony per typ elementu) — do zdefiniowania wspólnie, silnik jest gotowy przyjąć dowolną konfigurację.
- **B8**: spike musi potwierdzić który wariant budowy `CategorySet` działa na docelowych wersjach Revita (2023-2026) — patrz sekcja B8.
- **D1**: czy proxy złożoności rodziny (liczba typów/parametrów) wystarcza, czy od razu potrzebny dokładny rozmiar w bajtach mimo kosztu wydajnościowego.
- **E2b**: brak bundlowanego `.rft` — użytkownik wskazuje własny przy pierwszym użyciu (świadoma decyzja, nie luka).
