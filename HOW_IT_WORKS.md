# Jak SoundDeck funguje

Tento text je pro člověka, který Python zná jen základně. Popisuje, co tahle aplikace opravdu dělá a proč je kód rozdělený tak, jak je. Není to obecná učebnice. Když se tu píše o třídě nebo souboru, jde o kód v tomhle repozitáři.

SoundDeck je soundboard pro Discord. Vezme mikrofon, přimíchá k němu zvuky a výsledek pošle do virtuálního audio zařízení. Discord si to zařízení vybere jako mikrofon.

---

## Obrázky toku

Zvuková cesta:

```
MICROPHONE
     │
     ▼
sounddevice InputStream
     │
     ▼
PCM BUFFER (ring buffer)
     │
     ├──────── SOUND (už dekódované PCM v paměti)
     │              │
     ▼              ▼
        AUDIO MIXER
             │
             ▼
         soft clip
             │
             ▼
      OutputStream
             │
             ▼
        BLACKHOLE 2ch
             │
             ▼
          DISCORD
```

Architektura programu:

```
UI (karty, dialogy)
│
Controller  (SoundboardController)
│
Services
├── Audio      engine.py, mixer.py
├── Hotkeys    HotkeyManager
├── YouTube    metadata, downloader, cutter
└── Config     JsonConfigStorage
```

Platformy:

```
CORE
│
├── macOS
│   ├── BlackHole 2ch
│   └── Liquid Glass (theme + volitelně AppKit)
│
└── Windows (připraveno, ještě ne hotový build)
    ├── VB-CABLE
    └── Fluent / Mica tokeny
```

Jádro neví, jestli běží na Macu nebo na Windows. Zeptá se adaptéru v `src/soundboard/platform/`. Jediné místo, které se podívá na jméno operačního systému, je `src/soundboard/platform/detect.py`.

---

## 1. Co aplikace dělá

Uživatel vybere mikrofon a virtuální výstup. Přidá zvuk ze souboru nebo z YouTube klipu, který smí použít. Stiskne klávesu nebo kartu. Zvuk se přehraje, smíchá s mikrofonem a odejde do BlackHole. Discord poslouchá BlackHole, takže slyší hlas i zvuk.

Vstupní bod je `main()` v `src/soundboard/main.py`. Ta funkce nic nemíchá. Jen složí objekty dohromady a spustí okno.

## 2. Jak celá architektura funguje

Okno nesmí sahat na zvukovou knihovnu `sounddevice`. Karta `SoundCard` jen vyšle signál, například `play_requested(sound_id)`. `SoundboardController` v `src/soundboard/services/controller.py` ten signál chytí a zavolá `AudioEngine.play`.

Tok je pořád stejný:

1. UI řekne, co chce.
2. Controller to provede.
3. Engine, knihovna zvuků, hotkeys nebo YouTube worker udělají práci.
4. Zpět do UI jde jen stav: běží engine, jak daleko je přehrávání, jaká je chyba.

Díky tomu jde mixer testovat bez okna a bez mikrofonu.

## 3. Co je virtual audio device

Je to zařízení, které se v systému tváří jako mikrofon nebo reproduktor, ale není to hardware. Program do něj zapíše vzorky. Jiný program si je přečte, jako by šly z opravdového mikrofonu.

SoundDeck vlastní ovladač nevyrábí. Použije zařízení, které už v systému je.

## 4. Co je BlackHole

BlackHole 2ch je virtuální audio zařízení pro macOS. Má dva kanály, tedy stereo. SoundDeck do něj posílá hotový mix. V kódu ho hledá `find_by_hints` v `src/soundboard/audio/devices.py` podle jmen z `MacOSPlatform.virtual_output_hints()`: nejdřív `BlackHole 2ch`, potom cokoliv se jménem BlackHole.

Když BlackHole není, aplikace nespadne. `MacOSPlatform.install_instructions()` vrátí text s `brew install blackhole-2ch` a okno ho ukáže v pruhu nahoře.

## 5. Proč Discord potřebuje virtuální mikrofon

Discord umí nahrávat jen jedno vstupní zařízení. Nemá tlačítko „přimíchej k mikrofonu soubor MP3“. Kdybychom zvuk pustili jen do reproduktorů, Discord by ho neslyšel. Když je mix v BlackHole a Discord má jako vstup BlackHole, slyší totéž, co by jinak slyšel z mikrofonu: hlas i efekty.

Návod je v onboardingu, krok 4, v `src/soundboard/ui/dialogs/onboarding_dialog.py`.

## 6. Jak funguje microphone input

`AudioEngine.start` otevře `sounddevice.InputStream` na vybraném mikrofonu. Žádáme 48 000 Hz a formát float32. Když má mikrofon jeden kanál, žádáme jeden. Dva kanály bychom po něm chtít neměli, protože by stream nemusel naběhnout.

Callback `_input_callback` v `src/soundboard/audio/engine.py` dostane malý blok vzorků, zdvojí mono na stereo a uloží to do ring bufferu. Nic jiného. Žádný disk, žádné okno.

## 7. Co je digitální audio

Zvuk v počítači není spojitá vlna. Je to řada čísel. Každé číslo říká, jak daleko je membrána reproduktoru v jednom okamžiku. Když čísla přehrajeme dost rychle za sebou, ucho slyší tón.

## 8. Co je PCM

PCM znamená pulzně kódová modulace. Je to právě ta řada čísel, bez komprese. MP3 je zabalené, PCM je rozbalené. SoundDeck si zvuk po importu uloží jako PCM, aby ho šlo v reálném čase jen číst z paměti.

Soubor se jmenuje `sounds/<id>.f32`. Je to surové little-endian float32, stereo, bez hlavičky. Zápis dělá `save_pcm` v `src/soundboard/audio/loader.py`.

## 9. Co je sample

Sample, česky vzorek, je jedno číslo v té řadě. V SoundDecku je vzorek typu float32. Nula je ticho uprostřed. Kladné číslo je jedna strana vlny, záporné druhá. Hodnota 1.0 je plná hlasitost, kterou ještě považujeme za „na hraně“.

Stereo vzorek jsou dvě čísla vedle sebe: levý a pravý kanál. V NumPy má jeden zvuk tvar `(počet_vzorků, 2)`.

## 10. Co je sample rate

Sample rate je, kolik vzorků připadá na jednu sekundu. Když je jich málo, vysoké frekvence zmizí. Když jich je zbytečně moc, soubor je velký a mixer počítá déle.

## 11. Proč používáme 48 kHz

Konstanta `SAMPLE_RATE` v `src/soundboard/audio/formats.py` je 48 000. To je běžná frekvence ve videu, ve hrách a ve virtuálních zařízeních včetně BlackHole. Discord a BlackHole si s ní rozumí.

Mikrofon může v systému hlásit třeba 44 100 Hz. O převod se postará Core Audio, když stream otevřeme na 48 000. V callbacku už žádný resampling není. Byl by drahý a v reálném čase zbytečný.

## 12. Co je float32

Je to desetinné číslo uložené ve 32 bitech. Pro zvuk je praktické, protože sčítání hlasitostí je obyčejné sčítání čísel. Celá čísla (třeba 16bitové WAV) by se před mixem stejně převáděla.

`DTYPE` v `formats.py` je `numpy.float32`. Všechny buffery v enginu mají tenhle typ, aby se v callbacku nemuselo nic překlápět.

## 13. Jak sounddevice získává data z mikrofonu

`sounddevice` je Python obal kolem knihovny PortAudio. PortAudio mluví s Core Audio na macOS. My mu řekneme: „zařízení, 48 kHz, float32, bloky po 512 vzorcích, a tady je funkce, kterou volej“.

Tu funkci PortAudio volá pořád dokola, z vlastního vlákna, ne z vlákna okna.

## 14. Co je audio callback

Callback je funkce, kterou nepíšeme jako smyčku `while True` v našem kódu. Zavolá ji cizí knihovna, když má nová data nebo když potřebuje data nová.

V enginu jsou dva:

- `_input_callback` dostane mikrofon a uloží ho.
- `_output_callback` musí vyplnit výstupní buffer, než PortAudio blok odešle do BlackHole.

Když output callback nestihne práci včas, v reproduktoru (nebo v BlackHole) lupne mezera.

## 15. Proč callback běží pořád

Stream je otevřený po celou dobu, kdy engine běží. I v tichu. BlackHole musí pořád dostávat vzorky, jinak Discord slyší výpadky. Ticho je blok nul. Proto callback běží, i když žádný zvuk nehraje: pořád míchá mikrofon, a když mikrofon ještě nemá data, doplní nuly.

## 16. Co je buffer

Buffer je předem připravené pole, kam se data odkládají. V SoundDecku jsou dva druhy.

Ring buffer v `src/soundboard/audio/ring_buffer.py` je kruh. Mikrofon píše dopředu, výstup čte pozadu. Když se mikrofon předběhne, zahodí se nejstarší vzorky. Když výstup čte rychleji, než mikrofon stíhá, doplní se ticho. To řeší to, že dvoje hodiny (mikrofon a BlackHole) nejdou úplně stejně.

Druhý druh jsou pevné pracovní buffery v enginu: `_mic`, `_out`, `_scratch`, `_cube`. Mají délku `MAX_BLOCK_SIZE` (2048). Callback si z nich ukrajuje jen tolik, kolik PortAudio právě chce, obvykle 512. Nové velké pole se v callbacku nezakládá.

Než se ring buffer poprvé naplní aspoň jedním blokem, výstup posílá ticho. Jinak by na startu luplo.

## 17. Jak se microphone buffer míchá se sound bufferem

Funkce `mix_into` v `src/soundboard/audio/mixer.py` dostane blok mikrofonu a seznam hlasů (`PlaybackVoice`). Každý hlas má pole PCM, pozici a hlasitost.

Pro každý hlas se vezme kus PCM od aktuální pozice, vynásobí hlasitostí a přičte k mikrofonu. Pozice se posune dopředu. Když dojde na konec, hlas se vypne.

Víc zvuků může hrát najednou. Jeden `sound_id` má jen jeden hlas. Druhé spuštění téhož zvuku ho vrátí na začátek, nepřekryje samo sebe.

Na začátku a na konci je krátký fade, 64 vzorků (`FADE_FRAMES`). To je asi 1,3 milisekundy. Schová cvaknutí, když zvuk usekneme.

## 18. Jak funguje volume

Vzorec v `mix_into` je:

```
součet = mikrofon * mic_volume
       + zvuk1 * hlasitost_zvuku1
       + zvuk2 * hlasitost_zvuku2
       ...
výstup = soft_clip(součet * master_volume)
```

`mic_volume` a `master_volume` jsou v nastavení. Hlasitost karty je `SoundEntry.volume` a na kartě ji ukazuje slider. Během tažení se hodnota posílá do enginu hned, na disk se zapíše až po puštění slideru, aby se config nepřepisoval stokrát za sekundu.

Číslo 0.8 na kartě je 80 %. V mixu je to násobek 0.8.

## 19. Co je clipping

Když součet přesáhne rozsah, který zařízení umí přehrát, vlna se uřízne. U celých čísel to často znamená, že hodnota přeteče a zvuk ošklivě praská. U floatů nad 1.0 zařízení stejně narazí do stropu. Tomu se říká clipping.

Mikrofon na 1.0 plus zvuk na 1.0 je součet 2.0. To už je moc.

## 20. Jak clipping řešíme

`soft_clip_into` v `mixer.py` udělá dvě věci.

Nejdřív ostře omezí blok na rozsah −1 až 1, aby obří číslo nerozbilo další krok. Potom použije křivku:

```
y = x - x³ / 3
```

U tichých hodnot je sklon křivky skoro 1, takže tichý signál projde skoro beze změny. Čím je signál hlasitější, tím víc se křivka ohne. Nejhlasitější výsledek je ±2/3, tedy asi 0,667. Záměrně nejedeme až na ±1. Zůstane rezerva a součet nepraská.

Test `test_clipping_limits_a_hot_sum` v `tests/test_mixer.py` to počítá na NumPy polích, bez reproduktoru.

## 21. Jak se output dostane do BlackHole

`AudioEngine.start` otevře druhý stream: `OutputStream` na zařízení, jehož jméno sedí na uložený výstup. Callback do `outdata` zapíše už smíchaný blok. PortAudio ten blok předá Core Audio a Core Audio ho vloží do BlackHole, protože BlackHole je to zařízení, které jsme vybrali.

Kdyby uživatel vybral skutečné reproduktory, mix by šel do reproduktorů. Nastavení na to upozorní, protože mikrofon by mohl začít snímat sám sebe. To je zpětná vazba.

## 22. Jak BlackHole předá audio Discordu

BlackHole se v systému objeví jako vstup i jako výstup. SoundDeck píše do výstupu BlackHole. Discord čte vstup BlackHole. Jsou to dvě strany téhož virtuálního kabelu. Aplikace mezi nimi nic dalšího neposílá.

## 23. Jak funguje MP3

MP3 není řada vzorků. Je to komprimovaný popis zvuku. Přehrávač ho musí nejdřív dekódovat. Dekódování chce čas, soubor na disku a často i externí program. Do audio callbacku to nepatří.

## 24. Proč MP3 nepouštíme přímo v callbacku

Callback má na jeden blok pár milisekund (512 / 48000 je asi 10,7 ms) a nesmí sahat na disk. Kdyby se při každém stisku F1 spouštěl dekodér, okno by se sekalo a ve zvuku by byly díry.

Proto import zavolá FFmpeg jednou. Do knihovny se uloží PCM. Stisk klávesy jen řekne enginu „začni číst tohle pole od začátku“.

## 25. Jak FFmpeg převede audio

`ffmpeg_to_pcm` v `src/soundboard/audio/loader.py` spustí proces:

```
ffmpeg -i soubor -ac 2 -ar 48000 -f f32le pipe:1
```

`-ac 2` znamená stereo. `-ar 48000` je vzorkování. `-f f32le` je surové float32. Výstup teče do paměti, ne do dalšího souboru na disku. NumPy z těch bajtů složí pole `(N, 2)`.

Když FFmpeg v systému není, `resolve_ffmpeg` vyhodí `SoundLoadError` s textem `brew install ffmpeg`. Engine kvůli tomu nespadne. Nefunguje jen import.

## 26. Jak funguje NumPy audio array

NumPy pole je blok čísel v jednom kuse paměti. Pro stereo float32 na 2 sekundy je to 48000 × 2 × 2 × 4 bajty, asi 0,7 MB. Mixer nekopíruje celý zvuk při každém bloku. Vezme výřez `samples[pozice:pozice+512]` a ten přičte.

`ensure_stereo_f32` v `mixer.py` hlídá tvar a typ. Špatné pole se do enginu nedostane.

## 27. Jak fungují hotkeys

Každý zvuk může mít řetězec jako `F1` nebo `Cmd+Shift+V`. `parse_hotkey` v `src/soundboard/hotkeys/parser.py` z něj udělá objekt `Hotkey`: jedna klávesa a množina modifikátorů.

`HotkeyManager` v `manager.py` z toho postaví posluchače knihovny pynput (`GlobalHotKeys`). Posluchač běží ve vlastním vlákně. Když kombinace přijde, do fronty vloží jen `sound_id`. Okno si frontu vybírá časovačem. pynput tedy nesahá na widgety.

## 28. Jak aplikace pozná, který zvuk pustit

Vazba je slovník `sound_id → Hotkey` uvnitř manageru. Callback, který pynput zavolá, je uzavřený nad konkrétním id. Controller v `_drain` id přečte a zavolá `play`. Engine najde PCM podle téhož id v `_buffers`.

Když dvě karty chtějí stejnou kombinaci, `set_binding` vyhodí `HotkeyError` a starou vazbu nechá být. Test je v `tests/test_hotkeys.py`.

## 29. Jak funguje YouTube import

Dialog `YouTubeDialog` nejdřív načte údaje o videu, potom nechá vybrat začátek a konec, umí klip přehrát a umí ho přidat na plochu. Celé video se do knihovny neukládá.

Nahoře v dialogu je věta, že funkce je jen pro obsah, který uživatel smí stáhnout a použít. Kód nepřidává obcházení DRM. yt-dlp jede s obyčejným nastavením. Když video nejde stáhnout, uživatel dostane krátkou hlášku a log dostane podrobnosti.

## 30. Co dělá yt-dlp

`fetch_metadata` v `src/soundboard/youtube/metadata.py` zavolá `extract_info(..., download=False)`. Vrátí se titulek, délka a adresa náhledu. Soubor se ještě nestahuje.

`download_audio` v `downloader.py` stáhne nejlepší audio stopu do dočasné složky jako `source.<přípona>`. Průběh jde ven přes `progress_hooks` a v okně ho kreslí progress bar.

`normalize_youtube_url` pustí dál jen hosty `youtube.com`, `youtu.be`, `m.youtube.com` a `music.youtube.com`.

## 31. Co dělá FFmpeg u YouTube

Stejná funkce `ffmpeg_to_pcm` jako u souboru. U klipu se navíc předají časy `-ss` a `-t`. `-t` je délka, tedy konec minus začátek. Používáme délku schválně, protože kombinace `-ss` a `-to` se ve FFmpeg snadno přečte špatně.

## 32. Jak získáme audio

yt-dlp uloží dočasný soubor (třeba webm nebo m4a). FFmpeg ho umí přečíst, když je v systému sestavený s příslušnými dekodéry. Homebrew FFmpeg to umí. Výsledkem je zase float32 stereo na 48 kHz.

## 33. Jak vystřihneme pouze část

`cut_to_pcm` v `src/soundboard/youtube/cutter.py` nejdřív zavolá `validate_clip`. Ta odmítne konec před začátkem, konec za délkou videa a klip delší než 120 sekund (`MAX_CLIP_SECONDS`). Teprve potom se spustí FFmpeg.

120 sekund sterea ve float32 je zhruba 46 MB. Delší klip by knihovnu zbytečně nafukoval. Celé video se stejně maže.

## 34. Jak fungují timestampy

`parse_timestamp` v `timestamps.py` umí `12.5`, `1:23`, `1:23.5` i `00:01:23.500`. Výsledek jsou sekundy jako obyčejné číslo. `format_timestamp` je vypíše zpátky jako `HH:MM:SS.mmm`.

Slider v dialogu má rozsah v milisekundách, protože `QSlider` chce celá čísla. Textové pole a slider se navzájem přepisují, ale signály se na chvíli zablokují, aby se nezacyklily.

## 35. Jak funguje preview

Preview neukládá zvuk do configu. Vystřihne PCM do dočasného souboru a controller zavolá `preview_pcm`. Ten ho zaregistruje pod id `__preview__` a přehraje ho stejným enginem, tedy do BlackHole, ne do reproduktorů. Když se dialog zavře, `stop_preview` hlas zastaví a buffer zahodí.

Když engine neběží, preview se nespustí a okno řekne, ať se engine nejdřív zapne.

## 36. Jak fungují temporary files

Dočasná složka je `Application Support/SoundDeck/tmp/<náhodné id>/`. V ní leží stažené audio a vystřižené `.f32` náhledy. Trvalý je až soubor, který `SoundLibrary.add_samples` zkopíruje do `sounds/<id>.f32` a zapíše do JSON.

## 37. Jak a proč je mažeme

Celé video v knihovně nechceme. Je velké a uživatel si vybral jen kus. `YouTubeDialog.closeEvent` zavolá `shutil.rmtree` na tu dočasnou složku. I když přidání selže, surový download nezůstane ležet.

## 38. Jak funguje config

`AppConfig` v `src/soundboard/config/models.py` drží audio nastavení, seznam zvuků a příznak, že onboarding už proběhl. `JsonConfigStorage` to ukládá jako JSON verze 1.

Zápis jde nejdřív do `config.json.tmp` a potom se soubor atomicky přejmenuje. Když se aplikace složí uprostřed zápisu, nezůstane půlka JSON. Rozbitý soubor se odloží jako `config.json.bak` a aplikace naběhne s prázdným nastavením.

Cesty ke zvukům jsou relativní, tvaru `sounds/abc.f32`. Absolutní cesta ani `..` se při čtení nepřijme. Hlasitost mimo 0 až 1 se ořízne.

`ConfigStorage` je protokol. JSON je jedna implementace. SQLite může přijít později, aniž by se měnily karty nebo engine.

## 39. Kam macOS ukládá data

`MacOSPlatform.app_support_dir()` vrací:

```
~/Library/Application Support/SoundDeck/
```

Uvnitř je `config.json`, složka `sounds/`, složka `logs/` a dočasné `tmp/`. Ve zdrojovém repozitáři uživatelská data nejsou. Složka `data/` v repu je prázdná schránka a git ji ignoruje.

Windows adaptér by použil `%APPDATA%\SoundDeck`. Ten kód je v `windows.py`, ale Windows build se ještě nestaví.

## 40. Jak funguje threading

Jsou tři světy:

- UI vlákno. Okno, kliky, časovač, který vybírá fronty.
- Audio vlákno. Callbacky PortAudio. Nesmí čekat na okno.
- Workers. `QThread` v `src/soundboard/services/workers.py` pro metadata, stažení a FFmpeg.

Mezi nimi jsou fronty (`queue.SimpleQueue`) a Qt signály. Audio vlákno nezavolá `QMessageBox`. Jen nastaví text chyby. UI vlákno ho v `poll_health` jednou za 40 ms přečte, engine zastaví a ukáže dialog.

## 41. Proč YouTube download nesmí běžet na UI threadu

Qt kreslí okno jen tehdy, když UI vlákno není zaneprázdněné. Stažení videa trvá sekundy a FFmpeg taky. Kdyby běžely přímo v kliknutí na tlačítko, okno by zatuhlo a progress bar by se nehýbal.

`DownloadWorker.run` proto běží mimo UI vlákno. `progress.emit` Qt sám zařadí zpátky do UI vlákna. To je bezpečný způsob, jak z workeru aktualizovat widget.

## 42. Co je Qt event loop

`app.exec()` v `main.py` je smyčka, která čeká na události: myš, klávesy, časovače, signály z jiných vláken. Dokud smyčka běží, okno žije. Když se zavře, `aboutToQuit` zavolá `controller.shutdown()`: zastaví hotkeys i audio streamy.

## 43. Jak funguje PySide6

PySide6 jsou oficiální Python vazby na Qt 6. Okno, tlačítka, slidery a dialogy jsou Qt widgety. Vzhled není výchozí šedý Qt. Na startu se nastaví styl Fusion a přes něj náš stylesheet z tokenů.

`MainWindow` je hlavní okno. `GlassDialog` je společný základ dialogů. Nativní tlačítka zavřít, minimalizovat a maximalizovat nemalujeme. Necháváme je systému. Skryjeme jen text v titulku a nadpis „SoundDeck“ kreslíme v hlavičce okna.

## 44. Jak fungují signals a slots

Signál je hlášení „něco se stalo“. Slot je funkce, která to chce slyšet. Propojení je `signal.connect(funkce)`.

`SoundCard` má signály `play_requested`, `stop_requested`, `delete_requested`, `rename_requested`, `volume_changed`, `volume_committed` a `hotkey_edit_requested`. `MainWindow.reload_sounds` je napojí na metody controlleru.

Výhoda: karta nemusí znát engine. Controller nemusí znát, jestli klik přišel z karty nebo z hotkey.

## 45. Jak fungují themes

`ThemeTokens` v `src/soundboard/ui/themes/base.py` je seznam barev, poloměrů rohů, mezer a délek animací. Stylesheet `styles.qss` nemá v sobě natvrdo `#ffffff`. Má značky jako `{{accent}}`. `Theme.stylesheet()` je nahradí hodnotami z tokenů.

macOS tokeny jsou průsvitné, s větším zaoblením a písmem `.AppleSystemUIFont`. Windows tokeny jsou hustší, s menším poloměrem a písmem Segoe UI. Komponenty (`SoundCard`, `GlassButton`, …) jsou stejné třídy. Mění se jen čísla a stylesheet.

`theme_for_platform` vybere téma podle `platform.name`, ne podle rozházených `if Darwin` v UI.

## 46. Proč máme platform abstraction

Virtuální zařízení, složka s daty, oprávnění a vzhled okna se mezi systémy liší. Kdyby to bylo v enginu, Windows verze by znamenala přepis mixeru. Adaptér má metody `app_support_dir`, `virtual_output_hints`, `install_instructions`, `apply_window_effects`, `accessibility_granted` a `open_privacy_settings`.

Engine se zeptá jen na jméno zařízení, které mu controller předá. Jméno BlackHole nebo VB-CABLE vybere UI podle adaptéru.

## 47. Co je macOS-specific

- Cesta v Application Support.
- Hledání BlackHole.
- Kontrola Accessibility přes `AXIsProcessTrusted` (ctypes, bez PyObjC).
- Otevření System Settings na soukromí.
- `apply_window_effects` v `macos.py`: průhledný titlebar, zachovaná systémová tlačítka okna, `NSVisualEffectView` pod obsahem.

PyObjC se importuje až uvnitř té metody. Když chybí nebo AppKit okno odmítne, metoda vrátí False a zůstane Qt fallback: poloprůhledná plocha, jemný okraj, zaoblení. Aplikace kvůli sklu nespadne.

## 48. Co je platform-independent

Mixer, ring buffer, formát PCM, loader (FFmpeg), JSON config, parser hotkeys, YouTube střih, controller, karty a dialogy. Tyhle soubory neimportují AppKit a nevolají `platform.system()`.

`HotkeyManager` sice na Macu potřebuje oprávnění, ale samotná třída jen zavolá funkci, kterou dostane z venku. V testech tu funkci nikdo nevolá, protože listener se nespouští.

## 49. Jak později přidáme Windows

1. V `detect.py` už Windows vrací `WindowsPlatform`.
2. Doplní se opravdové Mica/Acrylic v `apply_window_effects`, nebo se nechá Qt téma.
3. Uživatel nainstaluje VB-CABLE. Hinty už jsou: `CABLE Input`, `VB-Audio`, `VB-CABLE`.
4. Téma se přepne samo, protože `platform.name` bude `windows`.
5. Mixer se nemění. Pořád 48 kHz, float32, stereo, dva streamy.

Windows soundboard tedy nemá vypadat jako macOS sklo. Má mít stejné karty a jiné tokeny.

## 50. Jak se aplikace buildí do .app

Soubor `packaging/sounddeck.spec` je zadání pro PyInstaller. Ten zabalí Python, Qt, PortAudio a yt-dlp do `SoundDeck.app`. V `Info.plist` je věta, proč aplikace chce mikrofon (`NSMicrophoneUsageDescription`).

`pyside6-deploy` je nástroj vhodný pro čisté Qt aplikace. Tady jsou ještě nativní knihovny zvuku a globálních kláves, proto je v projektu PyInstaller.

FFmpeg se do `.app` nebalí. Má být nainstalovaný v systému. Jinak by balík byl zbytečně obrovský a licenčně složitější.

## 51. Jaká macOS permissions potřebujeme

- **Mikrofon.** Bez něj není co míchat. Systém se zeptá při prvním startu streamu. Ve vývojovém režimu se zeptá terminálu nebo Pythonu, ve kterém aplikace běží. V `.app` se zeptá SoundDecku.
- **Accessibility.** Bez něj pynput globální klávesy nedostane. `accessibility_granted` v `macos.py` se zeptá systému. Když je odpověď ne, vazby zůstanou uložené a v okně se objeví vysvětlení. Aplikace nespadne.
- **Input Monitoring** někdy macOS chce navíc. Když hotkeys pořád nejdou, je to další přepínač ve stejném panelu Soukromí.

## 52. Jak projekt debugovat

Log je v `~/Library/Application Support/SoundDeck/logs/sounddeck.log`. Nastavuje ho `configure_logging` v `src/soundboard/logging_config.py`. V souboru je traceback. V okně je jedna věta.

Hledej řádky `Audio engine started`, `Imported sound`, `YouTube` a `ERROR`. V kódu není `print` jako logování.

Testy:

```
pytest
```

Mixer, config, hotkeys, timestampy a validace klipu jedou bez zařízení. Když se engine nespustí, dialog „Audio engine“ ukáže důvod z PortAudio. Častý důvod je špatné zařízení nebo chybějící oprávnění mikrofonu.

## 53. Nejčastější chyby

- **BlackHole není nainstalovaný.** Pruh v okně to řekne. Nainstaluj ho a v Settings zvol BlackHole 2ch.
- **Discord pořád bere vestavěný mikrofon.** Vstup v Discordu musí být BlackHole, ne MacBook Microphone.
- **Nic není slyšet.** Engine musí být ve stavu running. Bez vybraného vstupu a výstupu se nespustí.
- **Zpětná vazba, pískání.** Výstupem nesmí být reproduktory, když mikrofon slyší místnost. Použij sluchátka a BlackHole.
- **Import souboru selže.** Chybí FFmpeg, nebo soubor není opravdové audio. Přípona sama nestačí, FFmpeg obsah ještě kontroluje.
- **Hotkey nic nedělá.** Chybí Accessibility. Otevři v Settings odkaz na oprávnění a povol proces, který SoundDeck spustil.
- **Dva zvuky na jedné klávese.** Druhý se neuloží. Chyba řekne, že kombinace už je použitá.
- **YouTube nejde stáhnout.** Video je chráněné, soukromé, nebo nejsi oprávněný ho stáhnout. Aplikace ochranu neobchází.
- **Zařízení zmizelo za běhu.** Engine se zastaví a okno nabídne restart. `poll_health` hlídá, jestli streamy pořád žijí. První půlsekundu po startu tenhle test ještě neběží, aby se engine nezabil sám, než PortAudio ohlásí, že je aktivní.

---

## Python, který v projektu opravdu je

U každého pojmu je, co to je, kde to v SoundDecku je a proč jsme to tak napsali.

### class

Třída je šablona objektu. `AudioEngine` v `engine.py` je třída. Popisuje, co engine umí: `start`, `stop`, `play`. Samotný běh vznikne až objektem `AudioEngine()` v `main.py`. Třída je jedna, objekt je ten živý engine téhle relace.

### object

Objekt je konkrétní kus dat a chování. `SoundEntry` pro Vine Boom je objekt: má id, jméno, cestu, hotkey a hlasitost. Jiný zvuk je jiný objekt stejné třídy.

### __init__

`__init__` je metoda, která objekt nachystá hned po vzniku. `AudioEngine.__init__` připraví ring buffer, prázdné slovníky a pracovní NumPy pole. Streamy ještě neotevírá. Otevření je až `start`, protože v konstruktoru ještě nevíme, jaký mikrofon uživatel vybral.

### method

Metoda je funkce, která patří objektu a bere `self`. `RingBuffer.write` zapisuje do toho bufferu, na kterém ji zavoláš. Není to globální funkce, která by sahala do nějakého společného pole.

### property

Property vypadá jako atribut, ale spočítá se. `AudioDevice.is_input` v `devices.py` je property. Vrátí True, když má zařízení aspoň jeden vstupní kanál. Volající píše `device.is_input`, ne `device.is_input()`. Číslo kanálů se neukládá podruhé.

### type hints

Typy v podpisech, třeba `def play(self, sound_id: str) -> None`, nic za běhu samy nehlídají. Říkají čtenáři a editoru, co funkce čeká. V tomhle projektu jsou skoro všude, protože se tu míchá zvuk, Qt a vlákna a bez typů se v tom snadno splete id zvuku s cestou.

### dataclass

`@dataclass` vygeneruje `__init__` a porovnání. `SoundEntry`, `AppConfig`, `Hotkey`, `VideoMetadata` a `PlaybackState` jsou dataclass. `Hotkey` a `PlaybackState` jsou `frozen`, tedy se po vzniku nemění. Hodí se do fronty mezi vlákny: nikdo ti pod rukama nepřepíše klávesu, kterou už posloucháš.

### enum

Vlastní `Enum` třídu tu nemáme. Stavy enginu jsou krátké řetězce `"running"`, `"stopped"` a `"error"`, které controller posílá signálem `engine_status_changed`. Je jich málo a UI podle nich jen přepne barvu tečky. Až by stavů bylo víc a začaly se plést s obyčejným textem, patří do enumu.

### callback

Callback je funkce předaná někomu jinému, aby ji zavolal později. `_output_callback` dostane PortAudio. `_callback` v `HotkeyManager` vyrobí funkci, kterou pynput zavolá při klávese. Progress hook yt-dlp je taky callback: stáhne kousek a zavolá naši funkci s číslem 0 až 1.

### thread

Vlákno je druhý souběžný běh v jednom procesu. Audio callback je vlákno PortAudio. `QThread` u YouTube je další. UI zůstává ve svém. Nesdílejí widgety. Sdílejí fronty a pole, která už existují.

### queue

`queue.SimpleQueue` je fronta bezpečná mezi vlákny. Hotkey vlákno do ní vloží id. UI vlákno ho v `_drain` vytáhne. Audio příkazy (`play`, `stop`, `volume`) jdou stejnou frontou do output callbacku. Callback si jich za jeden blok vezme nejvýš 32, aby ho příkazy nezahltily.

### context manager

Context manager je `with`. V `fetch_metadata` je `with YoutubeDL(options) as downloader`. Na konci bloku se yt-dlp uklidí, i když nastane chyba. Streamy enginu context manager nepoužívají, protože mají žít dlouho a zavírají se v `stop()`.

### pathlib

`Path` z `pathlib` je cesta jako objekt, ne slepený řetězec. `SoundLibrary.path_for` složí `support_dir / entry.file` a odmítne cestu s `..`. `tmp_path` v testech je taky `Path`. Na Windows i macOS se to chová stejně, proto tu nejsou ručně psaná lomítka v logice.

### exceptions

`SoundDeckError` a potomci (`ConfigError`, `AudioEngineError`, `SoundLoadError`, `HotkeyError`, `YouTubeError`) jsou chyby, které smí vidět uživatel. Ostatní výjimky se zalogují s tracebackem a do okna jde obecná věta z `public_message`. Nikde není `except Exception: pass`. Prázdné spolknutí chyby by schovalo pád enginu.

### logging

`logging.getLogger(__name__)` v modulech píše do souboru i na stderr. Úrovně jsou info pro start a import, error pro spadlý stream. Do callbacku se neloguje. Log na disk by v reálném čase zablokoval zvuk. Callback jen zapíše větu do atributu a UI ji zaloguje potom.

### dependency injection

Velké objekty si engine nevyrábí potají. `main.py` vytvoří storage, knihovnu, engine, hotkeys a platformu a předá je do `SoundboardController`. Controller tedy nejde natvrdo na „globální engine“. V testu knihovny se předá dočasná složka `tmp_path` a žádný skutečný Application Support.

`HotkeyManager` dostane funkci `accessibility_granted` z venku. Manager nemusí importovat macOS, aby věděl, jestli smí poslouchat klávesy.

### abstract base class

`PlatformAdapter` v `platform/base.py` je abstraktní třída. Metody jako `app_support_dir` nemají tělo, mají `@abstractmethod`. `MacOSPlatform` a `WindowsPlatform` je musí doplnit. Kdo zkusí udělat holý `PlatformAdapter()`, Python to nepustí. Díky tomu Windows stub nemůže „zapomenout“ cestu k datům a tiše spadnout až u uživatele.

---

## Prohlídka souborů

### `src/soundboard/main.py`

`main` je composition root. Nastaví log, Qt, téma, načte JSON, složí controller a ukáže okno. Když onboarding ještě neproběhl, otevře ho až po startu smyčky, aby okno už mělo systémový rám.

### `src/soundboard/audio/engine.py`

`AudioEngine` vlastní streamy, ring buffer, tabulku PCM a frontu příkazů. Umí `start`, `stop`, `restart`. Když zařízení za běhu zmizí, `poll_health` vrátí větu a streamy zavře. `monitor_available` vrací False. Položka „Monitor output locally“ v nastavení je proto vypnutá a má vysvětlení. Není to tlačítko, které by předstíralo, že posloucháš mix.

### `src/soundboard/audio/mixer.py`

`mix_into` a `soft_clip_into` jsou čisté funkce nad poli. `PlaybackVoice` drží pozici přehrávání. Testy v `tests/test_mixer.py` jim předají ticho, jedničky a hlasitosti a podívají se na výsledek.

### `src/soundboard/audio/devices.py`

`list_devices` se zeptá PortAudio. `resolve_device` spáruje uložené jméno s živým zařízením, protože číselný index se po rebootu mění. Dvě zařízení se stejným jménem dostanou příponu s indexem.

### `src/soundboard/audio/loader.py`

`loader.py` validuje příponu a prázdný soubor dřív, než spustí FFmpeg. Podporované přípony jsou `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`.

### `src/soundboard/audio/ring_buffer.py`

`RingBuffer` je kruh pro mikrofon. Zámek drží jen po dobu kopie jednoho bloku. Test přetečení je v `tests/test_ring_buffer.py`.

### `src/soundboard/hotkeys/manager.py`

`HotkeyManager` ukládá vazby, odmítá konflikty a spouští pynput. `apply` posluchače znovu postaví po každé změně. Bez vazeb posluchače nespouští.

### `src/soundboard/youtube/downloader.py` a `cutter.py`

Downloader stáhne dočasné audio. Cutter z něj udělá PCM výřez. Metadata jsou zvlášť, aby šlo ukázat titulek dřív, než se cokoli stahuje.

### `src/soundboard/youtube/waveform.py`

`WaveformProvider` umí vrátit špičky pro budoucí kresbu vlny. `NullWaveformProvider.peaks` vrací `None`. Dialog proto kreslí slidery a časy, ne vlnu. Až bude vlna, dialog se nemusí učit stahování znovu.

### `src/soundboard/config/storage.py`

`JsonConfigStorage` načte a uloží `AppConfig`. Rozbitý JSON odloží a vyhodí `ConfigError`.

### `src/soundboard/platform/macos.py` a `windows.py`

macOS umí BlackHole, Accessibility a pokus o vibrancy. Windows umí cestu v AppData a jména VB-CABLE. `apply_window_effects` na Windows vrací False a do logu napíše, že Mica ještě není.

### `src/soundboard/ui/components/sound_card.py`

Karta ukáže jméno, tlačítko přehrát nebo zastavit, hotkey, procenta hlasitosti a tenký slider. Klik na plochu karty zvuk spustí. Během přehrávání má karta akcentový okraj a tenký průběh. Pulz průhlednosti je jen vizuální. Zvuk na něj nečeká.

### `src/soundboard/ui/main_window.py`

Okno slepí hlavičku, varovný pruh a mřížku. Počet sloupců bere `columns_for_width` v `flow_layout.py`: užší okno 2, střední 3, široké 4 a víc. Minimální velikost okna je 1024×700.

### `src/soundboard/ui/dialogs/onboarding_dialog.py`

Čtyři kroky: mikrofon, virtuální výstup, první soubor, Discord. Skip před krokem výstupu zařízení nepřepíše, aby se omylem nezapnul výstup do reproduktorů.

### `src/soundboard/services/controller.py`

Jediné místo, které zná zároveň engine, knihovnu, hotkeys a signály do okna. Časovač každých 40 ms vybere chyby enginu, stisknuté hotkeys a posun přehrávání.

---

## Co je schválně až další verze

- Poslech mixu na lokálních sluchátkách. Rozhraní na enginu je, v UI je položka vypnutá.
- Kreslená waveforma při střihu. Protokol `WaveformProvider` je, implementace vrací prázdno.
- Windows Mica a instalátor. Tokeny a adaptér jsou, efekty ne.
- SQLite. Protokol úložiště je, soubor je JSON.
