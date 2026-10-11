# 365 EPG Generator - GitHub Actions

Automatické generovanie EPG pre T-Mobile CZ, Magio SK a SMS.

## Nastavenie

### 1. Vytvor repozitár na GitHub
- Choď na github.com → New repository
- Názov: `epg-generator` (alebo ľubovoľný)
- **Private** (odporúčané - skryje tvoje ID kanálov)
- Klikni **Create repository**

### 2. Nahraj súbory
Nahraj všetky súbory z tohto ZIP do repozitára:
- `generate_epg.py`
- `xmltv.py`
- `.github/workflows/generate.yml`
- `channels/custom_channels_tm.txt`
- `channels/custom_channels_mag.txt`
- `channels/custom_channels.txt`
- `README.md`

### 3. Nahraj súbory s ID kanálov
Do priečinka `channels/` nahraj tieto súbory zo svojho Kodi zariadenia:

| Súbor | Zdroj |
|-------|-------|
| `custom_channels_tm.txt` | T-Mobile TV GO |
| `custom_channels_mag.txt` | Magio SK |
| `custom_channels.txt` | SMS |

Súbory nájdeš na:
`Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/script.365.epg.generator/`

### 4. Spusti prvé generovanie
- GitHub → Actions → "Generovanie EPG" → Run workflow

### 5. Nastav URL v Simple Client
Po prvom generovaní bude EPG dostupné na:
```
https://raw.githubusercontent.com/TVOJE-MENO/epg-generator/main/epg.xml
```

V IPTV Simple Client zmeň cestu k EPG na túto URL.

## Plán generovania
EPG sa generuje automaticky každý deň o **03:00 SEČ** (02:00 UTC).

Čas môžeš zmeniť v `.github/workflows/generate.yml`:
```yaml
- cron: '0 2 * * *'  # 02:00 UTC = 03:00 SEČ
```

## Počet dní
Nastav v `generate_epg.py`:
```python
NUM_DAYS = 4  # Počet dní dopredu
```
