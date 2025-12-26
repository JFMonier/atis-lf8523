import requests
import os

# Récupération des secrets GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Erreur envoi Telegram : {e}")

def verifier_r147():
    # Source de données publique (FIR Paris - LFRR)
    # On utilise un service qui reformate les données du SIA pour les rendre lisibles par un script
    url = "https://api.aviation-edge.com/api/public/notam?region=LFRR"
    
    try:
        print("Vérification des NOTAM en cours...")
        response = requests.get(url)
        # Si cette source est temporairement indisponible, on affiche l'erreur
        if response.status_code != 200:
            print("Source indisponible pour le moment.")
            return

        notams = response.json()
        trouve = False
        
        for n in notams:
            # On cherche dans le texte du NOTAM (souvent dans le champ 'itemE' ou 'text')
            texte = str(n).upper()
            
            if "R147" in texte or "R 147" in texte:
                trouve = True
                # On essaie d'extraire le texte propre si disponible
                contenu = n.get('itemE', 'Détail non disponible (voir SIA)')
                alerte = (
                    f"⚠️ *ALERTE ZONE R147 - ATLANTIC AIR PARK*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"Un NOTAM concernant la R147 a été détecté.\n\n"
                    f"📝 *Extrait :*\n_{contenu[:300]}..._\n\n"
                    f"🔗 Vérifiez sur SOFIA-Briefing pour confirmation."
                )
                envoyer_telegram(alerte)
                print("Une alerte a été envoyée sur Telegram !")

        if not trouve:
            print("RAS : Pas de mention de la R147 pour le moment.")

    except Exception as e:
        print(f"Erreur lors de la vérification : {e}")

if __name__ == "__main__":
    verifier_r147()
