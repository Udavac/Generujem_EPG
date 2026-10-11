# -*- coding: utf-8 -*-
# EPG Generator pre GitHub Actions
# Generuje EPG pre T-Mobile CZ, Magio SK, SMS

import os
import sys
import time
import unicodedata
import requests
import xml.etree.ElementTree as ET
import gzip
import xmltv
from datetime import datetime, timedelta

# ── Nastavenia ──────────────────────────────────────────────────────────────
NUM_DAYS = 4          # Počet dní dopredu
NUM_DAYS_BACK = 0     # Počet dní spätne
OUTPUT_FILE = "epg.xml"
# ────────────────────────────────────────────────────────────────────────────

now = datetime.now()
local_now = now.astimezone()
TimeShift = " " + str(local_now)[-6:].replace(":", "")
TimeShift1 = TimeShift[:3] + str(int(TimeShift[3]) - 1) + TimeShift[4:]

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
    """Načítaj ID kanálov zo súboru v priečinku channels/"""
    path = os.path.join("channels", filename)
    if not os.path.exists(path):
        print(f"  [!] Súbor {path} neexistuje - preskočujem")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _process_programme(y, tvch):
    """Spracuje jeden program z Magio/TM API."""
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
    """Generuje EPG pre T-Mobile CZ alebo Magio SK."""
    prfx = "tm-" if lng == "cz" else "mag-"
    title_ = "T-Mobile TV GO" if lng == "cz" else "Magio GO"
    print(f"\n[{title_}] Začínam generovanie...")

    tm_ids_list = tm_ids.split(",") if tm_ids else []

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

        per = NUM_DAYS + NUM_DAYS_BACK
        for i in range(NUM_DAYS_BACK * -1, NUM_DAYS):
            next_day = now + timedelta(days=i)
            back_day = next_day - timedelta(days=1)
            date_to = next_day.strftime("%Y-%m-%d")
            date_from = back_day.strftime("%Y-%m-%d")
            date_ = next_day.strftime("%d.%m.%Y")
            print(f"  Sťahujem {date_}...")

            if lng == "cz":
                # T-Mobile: hromadný request
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
                # Magio SK: per-kanál
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
    """Generuje EPG pre TV.SMS.cz"""
    print(f"\n[SMS] Začínam generovanie...")

    try:
        req = requests.get(
            "http://www.tv.sms.cz/epg.xml.gz",
            timeout=60, stream=True
        )
            content = gzip.decompress(req.content)
        root = ET.fromstring(content)
    except:
        try:
                    req = requests.get("http://www.tv.sms.cz/epg.xml", timeout=60)
            root = ET.fromstring(req.content)
        except Exception as e:
            print(f"  [SMS] CHYBA: {e}")
            return


    sms_ids_list = sms_ids.split(",") if sms_ids else []

    ch = {}
    for i in root.iter("channel"):
        ch_id = i.attrib.get("id", "")
        if not sms_ids_list or ch_id in sms_ids_list:
            name_el = i.find("display-name")
            name = name_el.text if name_el is not None else ch_id
            icon_el = i.find("icon")
            icon = icon_el.attrib.get("src", "") if icon_el is not None else ""
            ch[ch_id] = name
            W.addChannel({
                "display-name": [(name, u"cs")],
                "id": ch_id,
                "icon": [{"src": icon}] if icon else []
            })

    print(f"  Kanálov: {len(ch)}")

    count = 0
    for prog in root.iter("programme"):
        ch_id = prog.attrib.get("channel", "")
        if ch_id in ch:
            title_el = prog.find("title")
            desc_el = prog.find("desc")
            title = title_el.text if title_el is not None else ""
            desc = desc_el.text if desc_el is not None else ""
            programm = {
                "channel": ch_id,
                "start": prog.attrib.get("start", ""),
                "stop": prog.attrib.get("stop", ""),
                "title": [(title, u"")],
                "desc": [(desc, u"")]
            }
            W.addProgramme(programm)
            count += 1

    print(f"  Programov: {count}")
    print(f"  [SMS] Hotovo")


def main():
    print("=" * 50)
    print("365 EPG Generator - GitHub Actions")
    print(f"Čas: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Dní dopredu: {NUM_DAYS}")
    print("=" * 50)

    # Načítaj ID kanálov zo súborov
    tm_ids = read_ids("custom_channels_tm.txt")
    mag_ids = read_ids("custom_channels_mag.txt")
    sms_ids = read_ids("custom_channels.txt")

    # Generuj EPG
    if tm_ids is not None:
        get_tm_programmes(tm_ids, "cz")

    if mag_ids is not None:
        get_tm_programmes(mag_ids, "sk")

    if sms_ids is not None:
        get_sms_programmes(sms_ids)

    # Zapis EPG
    print(f"\nZapisujem {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "wb") as f:
        W.write(f, pretty_print=True)

    size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"Hotovo! Veľkosť: {size:.1f} MB")
    print("=" * 50)


if __name__ == "__main__":
    main()
