import requests
import os
import re
import asyncio
import edge_tts
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Correction de l'ordre en français
INFOS_FR = "Piste en herbe zéro huit, deux six fermée cause travaux. Prudence. Péril aviaire."
INFOS_EN = "Grass runway zero eight, two six, closed due to works. Caution. Bird hazard."

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        # Préparation du QNH pour l'audio (chiffre par chiffre)
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        q_audio = ", ".join(list(q_val)) # Transforme "1025" en "1, 0, 2, 5"

        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        
        return {
            "heure_metar": h_tele,
            "qnh": int(q_val),
            "q_audio": q_audio,
            "temp": int(t_match.group(1).replace('M', '-')),
            "dew": int(t_match.group(2).replace('M', '-')),
            "w_dir": int(w_match.group(1)),
            "w_spd": int(w_match.group(2))
        }
    except: return None

def scanner_notams():
    resultats = {"R147": "Pas d'information", "R45A": "Pas d'information"}
    try:
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        
        for zone in resultats.keys():
            if zone in texte:
                # Tentative d'extraire les horaires (ex: de 0800 TO 1200)
                horaires = re.findall(rf"{zone}.*?(\d{{2}}\d{{2}}.*?TO.*?\d{{2}}\d{{2}})", texte)
                if horaires:
                    resultats[zone] = f"ACTIVE de {horaires[0]}"
                else:
                    resultats[zone] = "ACTIVE (Horaires : voir NOTAM)"
    except: pass
    return resultats

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        f.write(open("fr.mp3", "rb").read())
        f.write(open("en.mp3", "rb").read())

def executer_veille():
    m = obtenir_metar("LFBH")
    notams = scanner_notams()
    if not m: return

    # Construction du texte audio
    txt_notam_fr = f" Zone R 147 : {notams['R147']}. Zone R 45 Alpha : {notams['R45A']}."
    
    vocal_fr = (f"Atlantic Air Park. Observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
                f"Vent {m['w_dir']:03.0f} degrés, {m['w_spd']:.0f} nœuds. Température {m['temp']:.0f} degrés. "
                f"Point de rosée {m['dew']:.0f} degrés. Q N H {m['q_audio']}. {INFOS_FR} {txt_notam_fr}")
    
    vocal_en = (f"Atlantic Air Park. Observation at {m['heure_metar'].replace(':',' ')} UTC. "
                f"Wind {m['w_dir']:03.0f} degrees, {m['w_spd']:.0f} knots. Temperature {m['temp']:.0f} degrees. "
                f"Dew point {m['dew']:.0f} degrees. Q, N, H, {m['q_audio']}. {INFOS_EN} {txt_notam_fr}")

    asyncio.run(generer_audio(vocal_fr, vocal_en))

    # Page Web avec les lignes Zones précises
    html_content = f"""... (Structure habituelle avec fond sombre) ...
        <div class="data">💎 QNH {m['qnh']}</div>
        <div class="notam" style="color:#ffcc00;">🚫 R147 : {notams['R147']}</div>
        <div class="notam" style="color:#ffcc00;">🚫 R45A : {notams['R45A']}</div>
    ..."""
    # Sauvegarde index.html et envoi Telegram (audio uniquement)
    # ...
