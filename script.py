import requests
import os
import re
from gtts import gTTS # Bibliothèque pour la voix

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

INFOS_LOCALES = "Piste 08/26 : Piste en herbe FERMÉE cause travaux. Prudence péril aviaire."

def envoyer_telegram_avec_audio(message, fichier_audio):
    # Envoi du texte
    url_txt = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url_txt, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
    
    # Envoi du fichier audio
    url_audio = f"https://api.telegram.org/bot{TOKEN}/sendAudio"
    with open(fichier_audio, 'rb') as audio:
        requests.post(url_audio, data={"chat_id": CHAT_ID}, files={'audio': audio})

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        w_match = re.search(r' (\d{3})(\d{2})KT', metar)
        q_match = re.search(r'Q(\d{4})', metar)
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        return {
            "qnh": int(q_match.group(1)) if q_match else None,
            "temp": int(t_match.group(1).replace('M', '-')) if t_match else None,
            "w_dir": int(w_match.group(1)) if w_match else None,
            "w_spd": int(w_match.group(2)) if w_match else None
        }
    except: return None

def executer_veille():
    # Construction du texte pour la voix
    m1, m2 = obtenir_metar("LFBH"), obtenir_metar("LFRI")
    meteo_txt = ""
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        wd = (m1['w_dir'] + m2['w_dir']) / 2
        ws = (m1['w_spd'] + m2['w_spd']) / 2
        meteo_txt = f"Météo. Vent {wd:03.0f} degrés, {ws:.0f} noeuds. QNH {q_moy:.0f}. Température {t_moy:.0f} degrés."

    # Scan NOTAM (R147 et R45A)
    zones_alertes = []
    try:
        check_url = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html")
        res = requests.get(check_url, timeout=15)
        liste_notam = res.text.upper()
        
        if "R147" in liste_notam: zones_alertes.append("R 147")
        if "R45A" in liste_notam: zones_alertes.append("R 45 Alpha")
    except: pass

    notam_txt = "Zones. " + (f"Attention, zones actives : {', '.join(zones_alertes)}." if zones_alertes else "Aucune zone active signalée.")

    # Texte final pour l'ATIS (Vocal)
    texte_atis = f"Atlantic Air Park, LF 85 23. {meteo_txt} {notam_txt} {INFOS_LOCALES}"
    
    # Texte pour Telegram (Markdown)
    rapport_tele = (
        f"🛩 *ATIS LF8523*\n━━━━━━━━━━━━\n"
        f"🌤 {meteo_txt.replace('.', '')}\n"
        f"🚫 *Zones :* {'⚠️ ' + ', '.join(zones_alertes) if zones_alertes else '✅ RAS'}\n"
        f"🚧 *Note :* {INFOS_LOCALES}"
    )

    # Génération de la voix
    tts = gTTS(text=texte_atis, lang='fr')
    tts.save("atis.mp3")

    envoyer_telegram_avec_audio(rapport_tele, "atis.mp3")

if __name__ == "__main__":
    executer_veille()
