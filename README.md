# 365 EPG Generator bol ako predloha. Ďakujem....
-------------------------------------------------
Automatické generovanie EPG pre moje potreby.

V IPTV Simple Client zmeň cestu k EPG na túto URL:
https://raw.githubusercontent.com/Udavac/Generujem_EPG/main/epg.xml

## Plán generovania
EPG sa generuje automaticky každý deň o **03:00 SEČ** (02:00 UTC).

Čas môžeš zmeniť v `.github/workflows/generate.yml`:
```yaml
- cron: '0 2 * * *'  # 02:00 UTC = 03:00 SEČ

## Počet dní Nastavíš v `generate_epg.py`


