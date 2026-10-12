"""Un widget de suivi dans la conversation : l'outil natif « Suivi des rendus » d'Open WebUI.

Fait ce que le module 3 de la série « Intégrations IA » montre à l'écran, sur l'état laissé par le
module 1 (connexion MCP « Studio 3D », modèle « Studio 3D », groupe « Graphistes ») :
  1. l'outil natif « Suivi des rendus » (open-webui/suivi_rendus.py), réservé au groupe ;
  2. ses vannes : adresse interne du studio et jeton du studio (lu dans .env, jamais affiché) ;
  3. l'outil activé sur le modèle « Studio 3D », et la phrase de open-webui/consignes-modele.txt
     (dernière ligne) ajoutée à ses consignes.

Côté studio, les routes /api/suivi/<n> et /s/<n>/<signature> sont dans studio/integrations.py, publiées
par studio/k8s-integrations.yaml (voir README.md).

Usage :
  python installer.py              # installe (ou met à jour)
  python installer.py --retirer    # retire l'outil, et revient aux consignes du module 1

Réglages : fichier .env (voir .env.example) ; les variables d'environnement l'emportent.
Aucune dépendance : Python 3.10 ou plus récent, bibliothèque standard seulement.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ICI = pathlib.Path(__file__).resolve().parent
OUTIL = {"id": "suivi_des_rendus", "nom": "Suivi des rendus",
         "description": "Carte de suivi en direct des rendus du studio 3D"}
MODELE = "studio-3d"
PHRASE = (ICI / "open-webui" / "consignes-modele.txt").read_text(encoding="utf-8").strip().splitlines()[-1]


def reglages() -> dict:
    """Lit .env (clé=valeur), puis l'environnement, qui l'emporte."""
    r = {"STUDIO_URL": "http://studio.studio3d.svc.cluster.local:8000", "GROUPE": "Graphistes"}
    env = ICI / ".env"
    if env.exists():
        for ligne in env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                r[cle.strip()] = valeur.strip()
    for cle in ("OWUI_URL", "OWUI_JETON", "STUDIO_URL", "STUDIO_JETON", "GROUPE"):
        if os.environ.get(cle):
            r[cle] = os.environ[cle]
    return r


R = reglages()


def api(methode: str, chemin: str, corps=None, ok404: bool = False):
    """Appel de l'API d'Open WebUI avec le jeton administrateur."""
    req = urllib.request.Request(R["OWUI_URL"].rstrip("/") + chemin, method=methode,
                                 data=None if corps is None else json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {R['OWUI_JETON']}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as rep:
            texte = rep.read().decode()
    except urllib.error.HTTPError as e:
        if ok404 and e.code in (400, 401, 404):
            return None
        sys.exit(f"{methode} {chemin} : {e.code} {e.read().decode()[:300]}")
    return json.loads(texte) if texte else None


def groupe() -> str:
    for g in api("GET", "/api/v1/groups/") or []:
        if g["name"] == R["GROUPE"]:
            return g["id"]
    sys.exit(f"groupe « {R['GROUPE']} » absent : installez d'abord le module 1")


# ---------------------------------------------------------------- 1 et 2. L'outil et ses vannes

def outil() -> None:
    corps = {"id": OUTIL["id"], "name": OUTIL["nom"],
             "content": (ICI / "open-webui" / "suivi_rendus.py").read_text(encoding="utf-8"),
             "meta": {"description": OUTIL["description"], "manifest": {}},
             "access_grants": [{"principal_type": "group", "principal_id": groupe(), "permission": "read"}]}
    if api("GET", f"/api/v1/tools/id/{OUTIL['id']}", ok404=True):
        api("POST", f"/api/v1/tools/id/{OUTIL['id']}/update", corps)
        print(f"outil « {OUTIL['nom']} » mis à jour")
    else:
        api("POST", "/api/v1/tools/create", corps)
        print(f"outil « {OUTIL['nom']} » créé, réservé au groupe {R['GROUPE']}")
    api("POST", f"/api/v1/tools/id/{OUTIL['id']}/valves/update",
        {"studio_url": R["STUDIO_URL"], "jeton": R["STUDIO_JETON"]})
    print("vannes enregistrées (adresse du studio, jeton)")


# ---------------------------------------------------------------- 3. Le modèle « Studio 3D »

def modele(ajouter: bool) -> None:
    m = api("GET", f"/api/v1/models/model?id={MODELE}", ok404=True)
    if not m:
        sys.exit("modèle « Studio 3D » absent : installez d'abord le module 1")
    outils = [t for t in m["meta"].get("toolIds", []) if t != OUTIL["id"]]
    m["meta"]["toolIds"] = outils + [OUTIL["id"]] if ajouter else outils
    texte = "\n".join(l for l in m["params"].get("system", "").splitlines() if l.strip() != PHRASE)
    m["params"]["system"] = f"{texte}\n{PHRASE}" if ajouter else texte
    api("POST", "/api/v1/models/model/update", m)
    print("modèle « Studio 3D » :", "outil activé, consigne ajoutée" if ajouter else "outil et consigne retirés")


def retirer() -> None:
    modele(False)
    api("DELETE", f"/api/v1/tools/id/{OUTIL['id']}/delete", ok404=True)
    print(f"outil « {OUTIL['nom']} » retiré")


if __name__ == "__main__":
    for cle in ("OWUI_URL", "OWUI_JETON") + (() if "--retirer" in sys.argv else ("STUDIO_JETON",)):
        if not R.get(cle):
            sys.exit(f"réglage manquant : {cle} (voir .env.example)")
    if "--retirer" in sys.argv:
        retirer()
    else:
        outil()
        modele(True)
