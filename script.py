import requests
import os
import re
import asyncio
import edge_tts
import time

STATIONS = ["LFBH", "LFRI"]

def formater_chiffre_fr(n):
    n_str = str(n).replace('-', '')
    if n_str == "1": return "unité"
    return n_str.lstrip('0') if len(n_str) > 1 and n_str.startswith('0') else n_str

def obtenir_donnees_moyennes():
    temps, rosees, qnhs, vents_dir, vents_spd, rafales = [], [], [], [], [], []
    h_tele = "--:--"
    for icao in STATIONS:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                lines = res.text.split('\n')
                if len(lines) < 2: continue
                metar = lines[1]
                time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
                if time_match: h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
                tr_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
                if tr_match:
                    temps.append(int(tr_match.group(1).replace('M', '-')))
                    rosees.append(int(tr_match.group(2).replace('M', '-')))
                q_match = re.search(r'Q(\d{4})', metar)
                if q_match: qnhs.append(int(q_match.group(1)))
                w_match = re.search(r' ([0-9]{3}|VRB)(\d{2})(G\d{2})?KT', metar)
                if w_match:
                    direction = w_match.group(1)
                    vitesse = int(w_match.group(2))
                    if direction != "VRB": vents_dir.append(int(direction))
                    vents_spd.append(vitesse)
                    if w_match.group(3): rafales.append(int(w_match.group(3).replace('G', '')))
        except: continue

    if not vents_spd or not qnhs: return None

    m_t = round(sum(temps)/len(temps)) if temps else 0
    m_r = round(sum(rosees)/len(rosees)) if rosees else 0
    m_q = round(sum(qnhs)/len(qnhs))
    m_wd = round(sum(vents_dir)/len(vents_dir)) if vents_dir else None
    m_ws = round(sum(vents_spd)/len(vents_spd))
    max_g = max(rafales) if rafales else None

    # Préparation audio
    q_str = str(m_q)
    q_audio = " ".join([formater_chiffre_fr(c) for c in list(q_str)])
    t_audio = (("moins " if m_t < 0 else "") + formater_chiffre_fr(abs(m_t)))
    d_audio = (("moins " if m_r < 0 else "") + formater_chiffre_fr(abs(m_r)))
    
    w_visu = f"{str(m_wd).zfill(3) if m_wd else 'VRB'}/{m_ws}" + (f"G{max_g}" if max_g else "")
    w_audio = f"vent {m_wd if m_wd else 'variable'} degrés, {m_ws} nœuds" + (f" avec rafales à {max_g}" if max_g else "")

    return {
        "heure_metar": h_tele, "qnh": q_str, "q_audio": q_audio,
        "temp_visu": str(m_t), "dew_visu": str(m_r),
        "t_audio": t_audio, "d_audio": d_audio,
        "w_dir_visu": w_visu, "w_audio": w_audio
    }

def scanner_notams():
    status = {"R147": "pas d'information", "R45A": "pas d'information", "DEBUG": "Initialisation..."}
    try:
        # On utilise NotamInfo qui agrège mieux les zones militaires (Série Z)
        url = "https://api.allorigins.win/get?url=" + requests.utils.quote("https://notaminfo.com/france/notams")
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            full_text = res.text.upper()
            status["DEBUG"] = f"Flux lu ({len(full_text)} car.)"
            
            # Recherche ciblée sur R147 et R45A
            for zone in ["R147", "R45A"]:
                # On cherche la zone et un créneau 1430-1600 dans les 400 caractères suivants
                match = re.search(rf"{zone}.{{1,400}}?(\d{{4}}[-/]\d{{4}})", full_text)
                if match:
                    t = match.group(1).replace('/', '-')
                    status[zone] = f"active de {t[:2]}:{t[2:4]} à {t[-4:-2]}:{t[-2:]}"
                elif zone in full_text:
                    status[zone] = "citée (vérifier SIA)"
    except Exception as e:
        status["DEBUG"] = f"Erreur NOTAM: {str(e)[:40]}"
    return status

async def generer_audio(vocal_fr):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("atis.mp3")

async def executer_veille():
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return

    # Récupération des remarques depuis GitHub Secrets
    remarques_raw = os.getenv("ATIS_REMARQUES", "Piste en herbe 08/26 fermée cause travaux | Prudence :: Grass runway 08/26 closed due to works | Caution")
    partie_fr = remarques_raw.split("::")[0] if "::" in remarques_raw else remarques_raw
    liste_fr = [r.strip() for r in partie_fr.split("|")]
    
    html_remarques = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in liste_fr])
    audio_rem_fr = ". ".join(liste_fr) + "."

    # Construction de la phrase NOTAM
    notam_fr = f"Zone R 147 : {notams['R147']}."
    if "active" in notams['R45A']:
        notam_fr += f" Attention, zone R 45 alpha {notams['R45A']}."

    # Texte final pour Henri
    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')}. "
              f"{m['w_audio']}. Température {m['t_audio']} degrés. Point de rosée {m['d_audio']} degrés. "
              f"Q N H {m['q_audio']} hectopascals. {audio_rem_fr} {notam_fr}")

    await generer_audio(txt_fr)
    ts = int(time.time())

    # Génération du HTML
    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; }}
        h1 {{ color: #fff; margin-bottom: 5px; }}
        .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; font-size: 0.9em; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); }}
        .debug {{ font-size: 0.7em; color: #555; margin-top: 20px; }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure (UTC)</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">
        {html_remarques}
        <div class="alert-line">⚠️ RTBA R147 : {notams['R147']}</div>
        <div class="alert-line" style="color:#4dabff;">⚠️ RTBA R45A : {notams['R45A']}</div>
    </div>
    <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    <div class="debug">Dernier scan : {notams['DEBUG']}</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
