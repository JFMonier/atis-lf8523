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
    # Source NOAA (Météo officielle)
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None
        
        metar = response.text.split('\n')[1]
        
        # Extraction QNH (recherche Q suivi de 4 chiffres)
        qnh_match = re.search(r'Q(\d{4})', metar)
        qnh = int(qnh_match.group(1)) if qnh_match else None
        
        # Extraction Température (ex: 12/08 ou M01/M03)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        if temp_match:
            temp = int(temp_match.group(1).replace('M', '-'))
            dew = int(temp_match.group(2).replace('M', '-'))
        else:
            temp, dew = None, None
            
        return {"qnh": qnh, "temp": temp, "dew": dew}
    except:
        return None

def executer_veille():
    rapport = f"🛩 *BULLETIN AUTOMATIQUE LF8523*\n(Atlantic Air Park)\n━━━━━━━━━━━━━━━━━━\n\n"
    
    # 1. MÉTÉO MOYENNÉE (LFBH La Rochelle / LFRI La Roche-sur-Yon)
    m1 = obtenir_metar("LFBH")
    m2 = obtenir_metar("LFRI")
    
    if m1 and m2:
        q_moy = (m1['qnh'] + m2['qnh']) / 2
        t_moy = (m1['temp'] + m2['temp']) / 2
        d_moy = (m1['dew'] + m2['dew']) / 2
        rapport += f"🌤 *Météo (Moyenne LFBH/LFRI) :*\n• QNH : {q_moy:.0f} hPa\n• Temp : {t_moy:.1f}°C\n• Rosée : {d_moy:.1f}°C\n\n"
    else:
        rapport += "⚠️ *Météo :* Service temporairement indisponible.\n\n"
    
    # 2. INFOS TERRAIN
    rapport += f"🚧 *Infos Terrain :*\n{INFOS_LOCALES}\n\n"
    
    # 3. SURVEILLANCE ZONE R147
    # Utilisation d'une source alternative de secours pour les NOTAM
    url_notam = "https://api.aviation-edge.com/api/public/notam?region=LFRR"
    try:
        res = requests.get(url_notam, timeout=15)
        r147_active = "NON"
        if res.status_code == 200:
            notams = res.text.upper()
            if "R147" in notams:
                r147_active = "⚠️ OUI (Active/Signalée)"
        
        rapport += f"🚫 *Zone R147 :* {r147_active}\n"
    except:
        rapport += "🚫 *Zone R147 :* Scan impossible (Vérifiez SIA).\n"

    rapport += "\n_Généré automatiquement par le système Atlantic Park._"
    envoyer_telegram(rapport)

if __name__ == "__main__":
    executer_veille()
