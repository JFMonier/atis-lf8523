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
    # Supprime le zéro devant un chiffre seul (ex: 05 devient 5)
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
        # Préparation QNH FR sans virgules pour la fluidité
        q_fr_elements = [formater_chiffre_fr(c) for c in list(q_val)]
        q_fr_rapide = " ".join(q_fr_elements)
        # Préparation QNH EN
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
            horaires = re.findall(r"R147.*?(\d{4}.*?TO.*?\d{4})",
