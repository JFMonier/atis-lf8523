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
        metar = response.text.split('\n')[1]
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        q_match = re.search(r'Q(\d{4})', metar)
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        return {
            "qnh": int(q_match.group(1)) if q_match else 1013,
            "temp": int(t_match.group(1).replace('M', '-')) if t_match else 15,
            "dew": int(t_match.group(2).replace('M', '-')) if t_match else 10,
            "w_dir": int(w_match.group(1)) if w_match else 0,
            "w_spd": int(w_match.group(2)) if w_match else 0
        }
    except: return None

def executer_veille():
    now_utc = datetime.now(timezone.utc)
    heure_vocal = now_utc.strftime("%H") + " heures " + now_utc.strftime("%M")
    time_en = now_utc.strftime("%H %M") + " UTC"
    
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        wd = (m1['w_dir'] + m2['w_dir']) / 2
        ws = (m1['w_spd'] + m2['w_spd']) / 2

        # --- CONSTRUCTION DU TEXTE VOCAL (ORDRE RÉGLEMENTAIRE) ---
        vocal_fr = (f"Atlantic Air Park. Information de {heure_vocal} UTC. "
                    f"Vent {wd:03.0f} degrés, {ws:.0f} nœuds. "
                    f"Température {t_moy:.0f} degrés. Point de rosée {d_moy:.0f} degrés. "
                    f"Q N H {q_moy:.0f} hectopascals. {INFOS_FR}")
        
        vocal_en = (f"Atlantic Air Park. Information at {time_en}. "
                    f"Wind {wd:03.0f} degrees, {ws:.0f} knots. "
                    f"Temperature {t_moy:.0f} degrees. Dew point {d_moy:.0f} degrees. "
                    f"Q N H {q_moy:.0f}. {INFOS_EN}")

        # Scan des zones
        zones_alertes = []
        try:
            check_url = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html")
            res = requests.get(check_url, timeout=15)
            notams = res.text.upper()
            if "R147" in notams: zones_alertes.append("R 147")
            if "R45A" in notams: zones_alertes.append("R 45 Alpha")
        except: pass

        if zones_alertes:
            alerte_txt = f" Attention, zones actives : {', '.join(zones_alertes)}."
            vocal_fr += alerte_txt
            vocal_en += f" Caution, active areas : {', '.join(zones_alertes)}."

        # Génération Audio et envoi
        tts = gTTS(text=vocal_fr + " ... " + vocal_en, lang='fr')
        tts.save("atis.mp3")
        
        # Rapport Telegram
        rapport_tele = (
            f"🛩 *ATIS LF8523*\n⌚ {now_utc.strftime('%H:%M')} UTC\n"
            f"🌬 {wd:03.0f}°/{ws:.0f}kt\n🌡 T:{t_moy:.0f}°C / DP:{d_moy:.0f}°C\n"
            f"💎 QNH {q_moy:.0f}\n🚫 {'⚠️ ' + ', '.join(zones_alertes) if zones_alertes else '✅ RAS'}\n"
            f"🚧 {INFOS_FR}"
        )
        
        url_txt = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        url_audio = f"https://api.telegram.org/bot{TOKEN}/sendAudio"
        requests.post(url_txt, data={"chat_id": CHAT_ID, "text": rapport_tele, "parse_mode": "Markdown"})
        with open("atis.mp3", 'rb') as a:
            requests.post(url_audio, data={"chat_id": CHAT_ID}, files={'audio': a})

if __name__ == "__main__":
    executer_veille()
