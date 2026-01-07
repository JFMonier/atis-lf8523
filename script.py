import requests
import os
import re
import asyncio
import edge_tts
import time
import json

# =================================================================
# ATIS LF8523 - Version Optimisée (Sans R45A et Design Sombre)
# =================================================================

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
                
                # Heure
                time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
                if time_match: h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
                
                # Température / Rosée
                tr_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
                if tr_match:
                    temps.append(int(tr_match.group(1).replace('M', '-')))
                    rosees.append(int(tr_match.group(2).replace('M', '-')))
                
                # QNH
                q_match = re.search(r'Q(\d{4})', metar)
                if q_match: qnhs.append(int(q_match.group(1)))
                
                # VENT
                w_match = re.search(r' ([0-9]{3}|VRB)(\d{2})(G\d{2})?KT', metar)
                if w_match:
                    direction = w_match.group(1)
                    vitesse = int(w_match.group(2))
                    if direction != "VRB":
                        vents_dir.append(int(direction))
                    vents_spd.append(vitesse)
                    if w_match.group(3):
                        rafales.append(int(w_match.group(3).replace('G', '')))
        except: continue

    if not vents_spd or not qnhs: return None

    m_t = round(sum(temps)/len(temps)) if temps else 0
    m_r = round(sum(rosees)/len(rosees)) if rosees else 0
    m_q = round(sum(qnhs)/len(qnhs))
    m_wd = round(sum(vents_dir)/len(vents_dir)) if vents_dir else None
    m_ws = round(sum(vents_spd)/len(vents_spd))
    max_g = max(rafales) if rafales else None

    q_str = str(m_q)
    q_audio_fr = " ".join([formater_chiffre_fr(c) for c in list(q_str)])
    
    if m_wd is None:
        v_fr, v_en = f"vent variable, {m_ws} nœuds", f"wind variable, {m_ws} knots"
        v_visu = f"VRB / {m_ws}"
    else:
        wd_str = str(m_wd).zfill(3)
        wd_en = " ".join(list(wd_str)).replace('0','zero').replace('1','one')
        v_fr, v_en = f"vent {m_wd} degrés, {m_ws} nœuds", f"wind {wd_en} degrees, {m_ws} knots"
        v_visu = f"{wd_str} / {m_ws}"

    if max_g and max_g > m_ws:
        v_fr += f", avec rafales à {max_g} nœuds"
        v_en += f", gusting {max_g} knots"
        v_visu += f"G{max_g}"

    return {
        "heure_metar": h_tele, "qnh": q_str, "q_audio_fr": q_audio_fr, "q_audio_en": " ".join(list(q_str)),
        "temp_visu": str(m_t), "dew_visu": str(m_r),
        "t_audio_fr": (("moins " if m_t < 0 else "") + formater_chiffre_fr(abs(m_t))),
        "d_audio_fr": (("moins " if m_r < 0 else "") + formater_chiffre_fr(abs(m_r))),
        "t_audio_en": (("minus " if m_t < 0 else "") + str(abs(m_t))),
        "d_audio_en": (("minus " if m_r < 0 else "") + str(abs(m_r))),
        "w_dir_visu": v_visu, "w_audio_fr": v_fr, "w_audio_en": v_en
    }

def scanner_notams():
    status = {"R147": {"info": "pas d'information", "date": ""}}
    
    # MÉTHODE 1 : Site AZBA du SIA
    try:
        url = "https://www.sia.aviation-civile.gouv.fr/schedules"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            match_r147 = re.search(r'(\d{2})/(\d{2})/(\d{4}).*?R\s*147.*?(\d{2}):?(\d{2})[^\d]*(\d{2}):?(\d{2})', res.text, re.IGNORECASE | re.DOTALL)
            if match_r147:
                jour, mois = match_r147.group(1), match_r147.group(2)
                h1, m1, h2, m2 = match_r147.group(4), match_r147.group(5), match_r147.group(6), match_r147.group(7)
                status["R147"]["date"] = f"{jour}/{mois}"
                status["R147"]["info"] = f"active {h1}h{m1}-{h2}h{m2}Z"
                return status
    except: pass
    return status

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd: f.write(fd.read())
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    from datetime import datetime
    m = obtenir_donnees_moyennes()
    notams = scanner_notams()
    if not m: return
    
    maintenant = datetime.now()
    date_generation_courte = maintenant.strftime("%d/%m %H:%M")

    remarques_raw = os.getenv("ATIS_REMARQUES", "Prudence oiseaux secteur piste | Activité voltige possible :: Caution birds near runway | Aerobatics possible")
    partie_fr, partie_en = remarques_raw.split("::") if "::" in remarques_raw else (remarques_raw, "Caution")
    
    liste_fr = [r.strip() for r in partie_fr.split("|")]
    liste_en = [r.strip() for r in partie_en.split("|")]
    
    html_remarques = "".join([f'<div class="alert-line">⚠️ {r}</div>' for r in liste_fr])
    audio_remarques_fr = ". ".join(liste_fr) + "."
    audio_remarques_en = ". ".join(liste_en) + "."

    # AUDIO FR
    notam_audio_fr = f"Zone R 147 : {notams['R147']['info']}."

    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. {audio_remarques_fr} {notam_audio_fr}")

    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. {audio_remarques_en} Check NOTAM for military areas.")

    await generer_audio(txt_fr, txt_en)
    ts = int(time.time())

    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ATIS LF8523</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 2.5vh 2.5vw; 
            background: linear-gradient(135deg, #2c5f7c 0%, #4a90b8 50%, #6bb6d6 100%);
            color: #e0e0e0; min-height: 100vh; margin: 0; 
        }}
        .container {{ width: 95%; max-width: 100%; margin: 0 auto; }}
        h1 {{ color: #fff; margin: 0 0 8px 0; text-align: center; text-shadow: 0 2px 10px rgba(0,0,0,0.3); }} 
        .subtitle {{ color: #fff; font-weight: 600; margin-bottom: 30px; text-transform: uppercase; text-align: center; opacity: 0.9; font-size: 0.85em; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        
        /* CONTENEURS INTERNES ASSOMBRIS */
        .data-item {{ 
            background: rgba(0, 0, 0, 0.25); 
            padding: 18px; border-radius: 12px; 
            border: 1px solid rgba(255, 255, 255, 0.15); 
            backdrop-filter: blur(8px);
        }}
        .alert-section {{ 
            background: rgba(0, 0, 0, 0.25); 
            border-left: 4px solid #ff9800; 
            padding: 18px; margin-bottom: 25px; border-radius: 8px;
            backdrop-filter: blur(8px);
        }}
        
        .label {{ font-size: 0.7em; color: rgba(255, 255, 255, 0.6); text-transform: uppercase; font-weight: 600; }}
        .value {{ font-size: 1.2em; font-weight: 700; color: #fff; margin-top: 8px; }}
        .alert-line {{ color: #ffb74d; font-weight: 600; font-size: 0.9em; margin-bottom: 10px; display: flex; align-items: center; }}
        .zone-date {{ background: rgba(255, 183, 77, 0.2); padding: 2px 8px; border-radius: 4px; margin-left: 8px; color: #ffd54f; }}
        .audio-container {{ background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 12px; margin: 20px 0; border: 1px solid rgba(255,255,255,0.2); }}
        audio {{ width: 100%; filter: invert(90%) hue-rotate(180deg); height: 40px; }}
        .btn-refresh {{ background: #fff; color: #2c5f7c; border: none; padding: 16px; border-radius: 10px; cursor: pointer; font-weight: 700; width: 100%; text-transform: uppercase; }}
        .update-info {{ font-size: 0.8em; color: #fff; margin-top: 15px; text-align: center; opacity: 0.8; }}
        .disclaimer {{ font-size: 0.7em; color: rgba(255, 255, 255, 0.8); margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px; }}
    </style></head><body><div class="container">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure (UTC)</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">
        {html_remarques}
        <div class="alert-line" style="font-size: 1em; margin-top: 10px;">
            🚨 R147 CHARENTE : {notams['R147']['info']}
            {('<span class="zone-date">📅 ' + notams["R147"]["date"] + '</span>') if notams['R147']['date'] else ''}
        </div>
    </div>
    <div class="audio-container">
        <audio controls><source src="atis.mp3?v={ts}" type="audio/mpeg"></audio>
    </div>
    <button class="btn-refresh" onclick="window.location.reload()">🔄 Actualiser les données</button>
    <div class="update-info">Dernière mise à jour : {date_generation_courte}</div>
    <div class="disclaimer"><strong>⚠️ Attention :</strong> Données indicatives non officielles. Consultez le SIA et Météo France avant tout vol.</div>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
