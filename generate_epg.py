# -*- coding: utf-8 -*-
# EPG Generator pre GitHub Actions
# Generuje EPG pre T-Mobile CZ, Magio SK, SMS

import os
import time
import unicodedata
import requests
import xml.etree.ElementTree as ET
import gzip
import xmltv
from datetime import datetime, timedelta

# ── Nastavenia ──────────────────────────────────────────────────────────────
NUM_DAYS = 2         # Počet dní dopredu
NUM_DAYS_BACK = 0     # Počet dní spätne
OUTPUT_FILE = "epg.xml"
# ────────────────────────────────────────────────────────────────────────────

now = datetime.now()

# Automatická detekcia letného/zimného času pre SR
def is_dst(dt):
    year = dt.year
    last_sunday_march = max(
        datetime(year, 3, day)
        for day in range(25, 32)
        if datetime(year, 3, day).weekday() == 6
    )
    last_sunday_october = max(
        datetime(year, 10, day)
        for day in range(25, 32)
        if datetime(year, 10, day).weekday() == 6
    )
    return last_sunday_march <= dt < last_sunday_october

if is_dst(now):
    TimeShift = " +0200"
    TimeShift1 = " +0100"
else:
    TimeShift = " +0100"
    TimeShift1 = " +0000"

print(f"Časová zóna: {TimeShift.strip()} ({'letný čas' if is_dst(now) else 'zimný čas'})")

W = xmltv.Writer(
    encoding="utf-8",
    source_info_url="http://www.funktronics.ca/python-xmltv",
    source_info_name="Funktronics",
    generator_info_name="python-xmltv",
    generator_info_url="http://www.funktronics.ca/python-xmltv"
)


def encode(string):
    return str(unicodedata.normalize('NFKD', string).encode('ascii', 'ignore'), "utf-8")


def read_ids(filename):
    path = os.path.join("channels", filename)
    if not os.path.exists(path):
        print(f"  [!] Súbor {path} neexistuje - preskočujem")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _process_programme(y, tvch):
    try:
        channel = y["channel"]["name"]
        if channel not in tvch:
            return
        start_time = y["startTime"].replace("-", "").replace("T", "").replace(":", "")
        stop_time = y["endTime"].replace("-", "").replace("T", "").replace(":", "")
        title = y["program"]["title"]
        desc = y["program"]["description"]
        epi = y["program"]["programValue"]["episodeId"]
        if epi is not None:
            title = title + " (" + epi + ")"
        year = y["program"]["programValue"]["creationYear"]
        try:
            subgenre = y["program"]["programCategory"]["subCategories"][0]["desc"]
        except:
            subgenre = ''
        try:
            genre = [(y["program"]["programCategory"]["desc"], u''), (subgenre, u'')]
        except:
            genre = None
        try:
            icon = y["program"]["images"][0]
        except:
            icon = None
        try:
            directors = [dr["fullName"] for dr in y["program"]["programRole"]["directors"]]
        except:
            directors = []
        try:
            actors = [ac["fullName"] for ac in y["program"]["programRole"]["actors"]]
        except:
            actors = []
        programm = {
            'channel': tvch[channel],
            'start': start_time + TimeShift,
            'stop': stop_time + TimeShift,
            'title': [(title, u'')],
            'desc': [(desc, u'')]
        }
        if year is not None:
            programm['date'] = year
        if genre is not None:
            programm['category'] = genre
        if icon is not None:
            programm['icon'] = [{"src": icon}]
        if directors and actors:
            programm['credits'] = {"director": directors, "actor": actors}
        elif directors:
            programm['credits'] = {"director": directors}
        elif actors:
            programm['credits'] = {"actor": actors}
        W.addProgramme(programm)
    except:
        pass


def get_tm_programmes(tm_ids, lng):
    prfx = "tm-" if lng == "cz" else "mag-"
    title_ = "T-Mobile TV GO" if lng == "cz" else "Magio GO"
    print(f"\n[{title_}] Začínam generovanie...")

    tm_ids_list = [x.strip() for x in tm_ids.split(",") if x.strip()] if tm_ids else []

    try:
        params = {
            "dsid": "c75536831e9bdc93",
            "deviceName": "Xiaomi Mi 11",
            "deviceType": "OTT_STB",
            "osVersion": "13",
            "appVersion": "3.7.0",
            "language": lng.upper()
        }
        headers = {
            "Host": lng + "go.magio.tv",
            "authorization": "Bearer",
            "User-Agent": "okhttp/3.12.12",
            "content-type": "application/json",
            "Connection": "Keep-Alive"
        }
        req = requests.post(
            "https://" + lng + "go.magio.tv/v2/auth/init",
            params=params, headers=headers, verify=True, timeout=30
        ).json()
        token = req["token"]["accessToken"]
        print(f"  Auth OK")

        headers2 = {
            "Host": lng + "go.magio.tv",
            "authorization": "Bearer " + token,
            "User-Agent": "okhttp/5.3.2",
            "content-type": "application/json"
        }

        req1 = requests.get(
            "https://" + lng + "go.magio.tv/v2/television/channels?list=LIVE&queryScope=LIVE",
            headers=headers2, timeout=30
        ).json()["items"]

        tvch = {}
        active_channel_ids = []

        for y in req1:
            ch_id = str(y["channel"]["channelId"])
            if not tm_ids_list or ch_id in tm_ids_list:
                active_channel_ids.append(ch_id)
                name = y["channel"]["name"]
                logo = str(y["channel"]["logoUrl"])
                chan_xml_id = prfx + ch_id + "-" + encode(name).replace(" HD", "").lower().replace(" ", "-")
                tvch[name] = chan_xml_id
                W.addChannel({
                    "display-name": [(name.replace(" HD", ""), u"cs")],
                    "id": chan_xml_id,
                    "icon": [{"src": logo}]
                })

        print(f"  Kanálov: {len(active_channel_ids)}")

        for i in range(NUM_DAYS_BACK * -1, NUM_DAYS):
            next_day = now + timedelta(days=i)
            back_day = next_day - timedelta(days=1)
            date_to = next_day.strftime("%Y-%m-%d")
            date_from = back_day.strftime("%Y-%m-%d")
            date_ = next_day.strftime("%d.%m.%Y")
            print(f"  Sťahujem {date_}...")

            if lng == "cz":
                tm_all = ",".join(active_channel_ids)
                try:
                    url = (
                        "https://czgo.magio.tv/v2/television/epg?filter=channel.id=in=(" + tm_all +
                        ");endTime=ge=" + date_from + "T23:00:00.000Z;startTime=le=" + date_to +
                        "T23:59:59.999Z&limit=500&offset=0&lang=CZ"
                    )
                    req_data = requests.get(url, headers=headers2, timeout=30).json().get("items", [])
                    for x in req_data:
                        for y in x["programs"]:
                            _process_programme(y, tvch)
                except Exception as e:
                    print(f"  [!] Chyba {date_}: {e}")
            else:
                for ch_id in active_channel_ids:
                    try:
                        url = (
                            "https://skgo.magio.tv/v2/television/epg?filter=channel.id=in=(" + ch_id +
                            ");endTime=ge=" + date_from + "T23:00:00.000Z;startTime=le=" + date_to +
                            "T23:59:59.999Z&limit=500&offset=0&lang=SK"
                        )
                        req_data = requests.get(url, headers=headers2, timeout=30).json().get("items", [])
                        time.sleep(0.05)
                        for x in req_data:
                            for y in x["programs"]:
                                _process_programme(y, tvch)
                    except Exception as e:
                        print(f"  [!] Chyba kanál {ch_id} {date_}: {e}")
                        continue

        print(f"  [{title_}] Hotovo")

    except Exception as e:
        print(f"  [{title_}] FATÁLNA CHYBA: {e}")


def get_sms_programmes(sms_ids):
    """Generuje EPG pre TV.SMS.cz cez 365dni.cz API"""
    print(f"\n[SMS] Začínam generovanie...")

    sms_ids_list = [x.strip() for x in sms_ids.split(",") if x.strip()] if sms_ids else []
    if not sms_ids_list:
        print("  [SMS] Žiadne kanály")
        return

    headers = {"user-agent": "SMSTVP/1.7.3 (242;cs_CZ) ID/ef284441-c1cd-4f9e-8e30-f5d8b1ac170c HW/Redmi Note 7 Android/10 (QKQ1.190910.002)"}

    try:
        html = requests.get(
            "http://programandroid.365dni.cz/android/v6-tv.php?locale=cs_CZ",
            headers=headers, timeout=30
        ).text
        root_ch = ET.fromstring(html)
    except Exception as e:
        print(f"  [SMS] CHYBA načítania kanálov: {e}")
        return

    ch = {}
    for i in root_ch.iter("a"):
        ch_id = i.attrib.get("id", "")
        if ch_id in sms_ids_list:
            name_el = i.find("n")
            name = name_el.text if name_el is not None else ch_id
            xml_id = encode((ch_id + "-" + name).replace(" ", "-").lower())
            ch[ch_id] = xml_id
            try:
                icon = "http://sms.cz/kategorie/televize/bmp/loga/velka/" + i.find("o").text
            except:
                icon = ""
            W.addChannel({
                "display-name": [(name, u"cs")],
                "id": xml_id,
                "icon": [{"src": icon}] if icon else []
            })

    print(f"  Kanálov: {len(ch)}")
    if not ch:
        print("  [SMS] Žiadne kanály nenájdené")
        return

    chl = ",".join(ch.keys())
    count = 0

    for i in range(NUM_DAYS_BACK * -1, NUM_DAYS):
        next_day = now + timedelta(days=i)
        date = next_day.strftime("%Y-%m-%d")
        date_ = next_day.strftime("%d.%m.%Y")
        print(f"  Sťahujem {date_}...")
        try:
            html = requests.get(
                "http://programandroid.365dni.cz/android/v6-program.php?datum=" + date + "&id_tv=" + chl,
                headers=headers, timeout=30
            ).text
            root_prog = ET.fromstring(html)
            for p in root_prog.iter("p"):
                ch_id = p.attrib.get("id_tv", "")
                if ch_id in ch:
                    n = p.find("n").text if p.find("n") is not None else ""
                    try:
                        k = p.find("k").text or ""
                    except:
                        k = ""
                    start = p.attrib.get("o", "").replace("-", "").replace(":", "").replace(" ", "") + TimeShift
                    stop = p.attrib.get("d", "").replace("-", "").replace(":", "").replace(" ", "") + TimeShift
                    W.addProgramme({
                        "channel": ch[ch_id],
                        "start": start,
                        "stop": stop,
                        "title": [(n, u"")],
                        "desc": [(k, u"")]
                    })
                    count += 1
        except Exception as e:
            print(f"  [SMS] Chyba {date_}: {e}")

    print(f"  Programov: {count}")
    print(f"  [SMS] Hotovo")


def main():
    print("=" * 50)
    print("365 EPG Generator - GitHub Actions")
    print(f"Čas: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Dní dopredu: {NUM_DAYS}")
    print("=" * 50)

    tm_ids = read_ids("custom_channels_tm.txt")
    mag_ids = read_ids("custom_channels_mag.txt")
    sms_ids = read_ids("custom_channels.txt")

    if tm_ids:
        get_tm_programmes(tm_ids, "cz")

    if mag_ids:
        get_tm_programmes(mag_ids, "sk")

    if sms_ids:
        get_sms_programmes(sms_ids)

    print(f"\nZapisujem {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "wb") as f:
        W.write(f, pretty_print=True)

    size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Hotovo! Veľkosť: {size:.1f} MB")
    print("=" * 50)


if __name__ == "__main__":
    main()
