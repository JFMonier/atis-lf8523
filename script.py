import requests
import os
import re
import asyncio
import edge_tts

# Configuration
ICAO = "LFBH"

def formater_chiffre_fr(n):
    """Gère la diction spécifique : 'unité' pour 1 et suppression du zéro initial."""
    n_str = str(n).replace('-', '')
    if n_str == "1": return "unité"
    return n_str.lstrip('0') if len(n_str) > 1 and n_str.startswith('0') else n_str

def obtenir_metar(icao):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
    try:
        response = requests.get(url, timeout=10)
        metar = response.text.split('\n')[1]
        
        time_match = re.search(r' (\d{2})(\d{2})(\d{2})Z', metar)
        h_tele = f"{time_match.group(2)}:{time_match.group(3)}"
        
        # --- VENT ---
        w_dir_visu, w_spd_visu = "000", "0"
        w_audio_fr, w_audio_en = "", ""

        if "00000KT" in metar:
            w_dir_visu, w_spd_visu = "CALME", "0"
            w_audio_fr, w_audio_en = "vent calme", "wind calm"
        else:
            w_match = re.search(r' ([A-Z0-9]{3})(\d{2})(G\d{2})?KT', metar)
            if w_match:
                d, s, g = w_match.group(1), w_match.group(2), w_match.group(3)
                w_dir_visu = d
                if d == "VRB":
                    w_audio_fr, w_audio_en = "vent variable", "wind variable"
                else:
                    d_en = " ".join(list(d)).replace('0', 'zero').replace('1', 'one')
                    w_audio_fr = f"vent {d} degrés"
                    w_audio_en = f"wind {d_en} degrees"
                
                spd = s.lstrip('0') or "0"
                w_spd_visu = s
                w_audio_fr += f", {spd} nœuds"
                w_audio_en += f", {spd} knots"
                
                if g:
                    gst = g.replace('G', '').lstrip('0')
                    w_spd_visu += f"G{gst}"
                    w_audio_fr += f", rafales {gst} nœuds"
                    w_audio_en += f", gusts {gst} knots"

        # --- QNH ---
        q_match = re.search(r'Q(\d{4})', metar)
        q_val = q_match.group(1) if q_match else "1013"
        q_fr_elements = [formater_chiffre_fr(c) for c in list(q_val)]
        q_fr_rapide = " ".join(q_fr_elements)
        q_en = " ".join(list(q_val))

        # --- TEMP / ROSÉE ---
        t_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)
        t_raw, d_raw = t_match.group(1), t_match.group(2)
        
        def dict_temp(val, lang):
            neg = "moins " if "M" in val and lang=="fr" else "minus " if "M" in val else ""
            num = val.replace('M', '').lstrip('0') or "0"
            return f"{neg}{num}"

        return {
            "heure_metar": h_tele, "qnh": q_val, "q_audio_fr": q_fr_rapide, "q_audio_en": q_en,
            "temp_visu": t_raw.replace('M', '-'), "dew_visu": d_raw.replace('M', '-'),
            "t_audio_fr": dict_temp(t_raw, "fr"), "d_audio_fr": dict_temp(d_raw, "fr"),
            "t_audio_en": dict_temp(t_raw, "en"), "d_audio_en": dict_temp(d_raw, "en"),
            "w_dir_visu": w_dir_visu, "w_spd_visu": w_spd_visu,
            "w_audio_fr": w_audio_fr, "w_audio_en": w_audio_en
        }
    except: return None

def scanner_notams():
    resultats = {"R147": "pas d'information"}
    try:
        res = requests.get("https://api.allorigins.win/get?url=" + requests.utils.quote("https://www.notams.faa.gov/common/icao/LFRR.html"), timeout=15)
        texte = res.text.upper()
        if "R147" in texte:
            horaires = re.findall(r"R147.*?(\d{4}.*?TO.*?\d{4})", texte)
            if horaires:
                resultats["R147"] = f"active de {horaires[0].replace('TO', 'à')}"
            else:
                resultats["R147"] = "active (voir NOTAM)"
    except: pass
    return resultats

async def generer_audio(vocal_fr, vocal_en):
    await edge_tts.Communicate(vocal_fr, "fr-FR-HenriNeural", rate="+5%").save("fr.mp3")
    await edge_tts.Communicate(vocal_en, "en-GB-ThomasNeural", rate="+10%").save("en.mp3")
    with open("atis.mp3", "wb") as f:
        for fname in ["fr.mp3", "en.mp3"]:
            with open(fname, "rb") as fd: f.write(fd.read())
    for f in ["fr.mp3", "en.mp3"]:
        if os.path.exists(f): os.remove(f)

async def executer_veille():
    m = obtenir_metar(ICAO)
    notams = scanner_notams()
    if not m: return

    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {m['q_audio_fr']} hectopascals. "
              f"Piste en herbe zéro huit vingt-six fermée cause travaux. Prudence. Péril aviaire. "
              f"Zone R 147 : {notams['R147']}.")

    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. Grass runway zero eight twenty-six closed due to works. Caution. Bird hazard. "
              f"Military area Romeo one four seven: non information.")

    await generer_audio(txt_fr, txt_en)

    html_content = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ATIS LF8523</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; padding: 20px; background: #121212; color: #e0e0e0; }}
        .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; max-width: 500px; margin: auto; border: 1px solid #333; }}
        h1 {{ color: #fff; margin-bottom: 5px; }} .subtitle {{ color: #4dabff; font-weight: bold; margin-bottom: 25px; text-transform: uppercase; }}
        .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .data-item {{ background: #2a2a2a; padding: 15px; border-radius: 10px; border: 1px solid #3d3d3d; }}
        .label {{ font-size: 0.75em; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 1.2em; font-weight: bold; color: #fff; margin-top:5px; }}
        .alert-section {{ text-align: left; background: rgba(255, 204, 0, 0.1); border-left: 4px solid #ffcc00; padding: 15px; margin-bottom: 25px; }}
        .alert-line {{ color: #ffcc00; font-weight: bold; font-size: 0.9em; margin-bottom: 8px; }}
        audio {{ width: 100%; filter: invert(90%); }}
    </style></head><body><div class="card">
    <h1>ATIS LF8523</h1><div class="subtitle">Atlantic Air Park</div>
    <div class="data-grid">
        <div class="data-item"><div class="label">Heure</div><div class="value">⌚ {m['heure_metar']}Z</div></div>
        <div class="data-item"><div class="label">Vent</div><div class="value">🌬 {m['w_dir_visu']} / {m['w_spd_visu']}kt</div></div>
        <div class="data-item"><div class="label">Temp / Rosée</div><div class="value">🌡 {m['temp_visu']}° / {m['dew_visu']}°</div></div>
        <div class="data-item"><div class="label">QNH</div><div class="value">💎 {m['qnh']} hPa</div></div>
    </div>
    <div class="alert-section">
        <div class="alert-line">⚠️ Piste en herbe 08/26 fermée cause travaux</div>
        <div class="alert-line">⚠️ Prudence</div>
        <div class="alert-line">⚠️ Péril aviaire</div>
        <div class="alert-line">⚠️ RTBA R147 : {notams['R147']}</div>
    </div>
    <div class="label" style="margin-bottom:10px;">Écouter l'audio</div>
    <audio controls autoplay><source src="atis.mp3" type="audio/mpeg"></audio>
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(executer_veille())
