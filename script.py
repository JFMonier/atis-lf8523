import requests
import os
import re

# Secrets GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONFIGURATION MANUELLE LF8523 ---
INFOS_LOCALES = "Piste 08/26 : Piste en herbe FERMÉE cause travaux. Prudence péril aviaire."

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None
        metar = response.text.split('\n')[1]
        
        # Extraction Vent (ex: 24010KT ou 04005MPS)
        wind_match = re.search(r' (\d{3})(\d{2})KT', metar)
        wind_dir = int(wind_match.group(1)) if wind_match else None
        wind_speed = int(wind_match.group(2)) if wind_match else None
        
        # Extraction QNH
        qnh_match = re.search(r'Q(\d{4})', metar)
        qnh = int(qnh_match.group(1)) if qnh_match else None
        
        # Extraction Température
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        if temp_match:
            temp = int(temp_match.group(1).replace('M', '-'))
            dew = int(temp_match.group(2).replace('M', '-'))
        else:
            temp, dew = None, None
            
        return {"qnh": qnh, "temp": temp, "dew": dew, "wind_dir": wind_dir, "wind_speed": wind_speed}
    except:
        return None

def executer_veille():
    rapport = f"🛩 *BULLETIN AUTOMATIQUE LF8523*\n(Atlantic Air Park)\n━━━━━━━━━━━━━━━━━━\n\n"
    
    m1 = obtenir_metar("LFBH")
    m2 = obtenir_metar("LFRI")
    
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        # Calcul vent moyen
        if m1['wind_dir'] and m2['wind_dir']:
            w_dir = (m1['wind_dir'] + m2['wind_dir']) / 2
            w_spd = (m1['wind_speed'] + m2['wind_speed']) / 2
            rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• Vent : {w_dir:03.0f}° / {w_spd:.0f} kt\n• QNH : {q_moy:.0f} hPa\n• Temp : {t_moy:.1f}°C\n• Rosée : {d_moy:.1f}°C\n\n"
        else:
            rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• QNH : {q_moy:.0f} hPa\n• Temp : {t_moy:.1f}°C\n\n"
    
    rapport += f"🚧 *Infos Terrain :*\n{INFOS_LOCALES}\n\n"
    
    # 3. SURVEILLANCE ZONE R147 (Source alternative gratuite)
    url_notam = "https://icao.pikaero.com/api/notams?region=LFRR"
    try:
        res = requests.get(url_notam, timeout=15)
        r147_active = "✅ Non signalée"
        if "R147" in res.text.upper():
            r147_active = "⚠️ ACTIVÉE (Voir SIA)"
        rapport += f"🚫 *Zone R147 :* {r147_active}\n"
    except:
        rapport += "🚫 *Zone R147 :* Vérification manuelle requise (SIA).\n"

    rapport += "\n_Généré automatiquement par le système Atlantic Park._"
    envoyer_telegram(rapport)

if __name__ == "__main__":
    executer_veille()
