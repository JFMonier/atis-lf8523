import requests
import os
import re
from datetime import datetime, timezone
from gtts import gTTS

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INFOS_FR = "Piste zéro huit, deux six en herbe fermée cause travaux. Prudence péril aviaire."
INFOS_EN = "Grass runway zero eight, two six closed due to works. Bird hazard reported."

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        # La première ligne contient la date/heure de la NOAA
        # La deuxième ligne est le METAR brut
        lignes = response.text.split('\n')
        metar = lignes[1]
        
        # Extraction de l'heure du METAR (ex: 121530Z -> 15h30)
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        heure_metar = f"{time_match.group(2)}:{time_match.group(3)}" if time_match else "Inconnue"
        heure_vocal = f"{time_match.group(2)} heures {time_match.group(3)}" if time_match else "Inconnue"

        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        q_match = re.search(r'Q(\d{4})', metar)
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        
        return {
            "heure_metar": heure_metar,
            "heure_vocal": heure_vocal,
            "qnh": int(q_match.group(1)) if q_match else 1013,
            "temp": int(t_match.group(1).replace('M', '-')) if t_match else 15,
            "dew": int(t_match.group(2).replace('M', '-')) if t_match else 10,
            "w_dir": int(w_match.group(1)) if w_match else 0,
            "w_spd": int(w_match.group(2)) if w_match else 0
        }
    except: return None

def executer_veille():
    m1 = obtenir_metar("LFBH") # On prend l'heure de La Rochelle
    m2 = obtenir_metar("LFRI")
    
    if m1 and m2:
        # On utilise l'heure d'observation du METAR de LFBH
        h_vocal = m1['heure_vocal']
        h_tele = m1['heure_metar']
        
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        wd = (m1['w_dir'] + m2['w_dir']) / 2
        ws = (m1['w_spd'] + m2['w_spd']) / 2

        # --- TEXTE VOCAL ---
        vocal_fr = (f"Atlantic Air Park. Observation de {h_vocal} UTC. "
                    f"Vent {wd:03.0f} degrés, {ws:.0f} nœuds. "
                    f"Température {t_moy:.0f} degrés. Point de rosée {d_moy:.0f} degrés. "
                    f"Q N H {q_moy:.0f} hectopascals. {INFOS_FR}")
        
        vocal_en = (f"Atlantic Air Park. Observation at {h_tele.replace(':', ' ')} UTC. "
                    f"Wind {wd:03.0f} degrees, {ws:.0f} knots. "
                    f"Temperature {t_moy:.0f} degrees. Dew point {d_moy:.0f} degrees. "
                    f"Q N H {q_moy:.0f}. {INFOS_EN}")

        # Scan des zones (R147 / R45A)
        zones = []
        try:
            res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
            if "R147" in res.text.upper(): zones.append("R 147")
            if "R45A" in res.text.upper(): zones.append("R 45 Alpha")
        except: pass

        if zones:
            vocal_fr += f" Attention, zones actives : {', '.join(zones)}."
            vocal_en += f" Caution, active areas : {', '.join(zones)}."

        # Génération Audio
        tts = gTTS(text=vocal_fr + " ... " + vocal_en, lang='fr')
        tts.save("atis.mp3")
        
        # Telegram
        rapport = (f"🛩 *ATIS LF8523*\n⌚ Obs : {h_tele} UTC\n"
                   f"🌬 {wd:03.0f}°/{ws:.0f}kt\n🌡 T:{t_moy:.0f}°C / DP:{d_moy:.0f}°C\n"
                   f"💎 QNH {q_moy:.0f}\n🚫 {'⚠️ ' + ', '.join(zones) if zones else '✅ RAS'}\n"
                   f"🚧 {INFOS_FR}")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": rapport, "parse_mode": "Markdown"})
        with open("atis.mp3", 'rb') as a:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendAudio", data={"chat_id": CHAT_ID}, files={'audio': a})

if __name__ == "__main__":
    executer_veille()
