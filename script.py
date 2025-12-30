async def executer_veille():
    m = obtenir_metar(ICAO)
    if not m: return

    # --- AUDIO FR ---
    # Ajout d'une virgule avant "observation" pour la pause
    # Suppression des virgules dans q_audio_fr pour accélérer la diction
    q_fr_rapide = m['q_audio_fr'].replace(',', '') 
    
    txt_fr = (f"Atlantic Air Park, observation de {m['heure_metar'].replace(':',' heures ')} UTC. "
              f"{m['w_audio_fr']}. Température {m['t_audio_fr']} degrés. Point de rosée {m['d_audio_fr']} degrés. "
              f"Q N H {q_fr_rapide} hectopascals. "
              f"Piste en herbe zéro huit vingt-six fermée cause travaux. Prudence. Péril aviaire. "
              f"Zone R 147 : pas d'information.")

    # --- AUDIO EN (inchangé car nickel) ---
    txt_en = (f"Atlantic Air Park observation at {m['heure_metar'].replace(':',' ')} UTC. "
              f"{m['w_audio_en']}. Temperature {m['t_audio_en']} degrees. Dew point {m['d_audio_en']} degrees. "
              f"Q N H {m['q_audio_en']} hectopascals. Grass runway zero eight twenty-six closed due to works. Caution. Bird hazard. "
              f"Military area Romeo one four seven: non information.")

    await generer_audio(txt_fr, txt_en)
    
    # ... (le reste du code HTML reste identique)
