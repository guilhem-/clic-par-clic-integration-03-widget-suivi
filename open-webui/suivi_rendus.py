"""
title: Suivi des rendus
description: Affiche dans la conversation une carte qui suit en direct un rendu du studio 3D (file, calcul, image, objet 3D, scène Blender).
version: 2.0
"""

# Outil natif d'Open WebUI (Espace de travail › Outils). Il renvoie une HTMLResponse : Open WebUI
# l'affiche comme un widget dans le message, dans un cadre isolé. Le widget interroge lui-même, depuis
# le navigateur, l'adresse d'état signée du studio (lecture seule, sans identité) jusqu'à la fin du rendu.

import html
import json

import requests
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        studio_url: str = Field(
            "http://studio.studio3d.svc.cluster.local:8000",
            description="Adresse interne du studio",
        )
        jeton: str = Field(
            "",
            description="Jeton du studio (le même que la connexion MCP)",
            json_schema_extra={"input": {"type": "password"}},
        )  # champ masqué dans les vannes

    def __init__(self):
        self.valves = self.Valves()

    def suivre_rendu(self, numero: int, __user__: dict = {}) -> HTMLResponse:
        """
        Affiche dans la conversation une carte de suivi du rendu : elle se met à jour toute seule
        jusqu'à l'image finale, l'objet 3D et la scène Blender. À appeler juste après soumettre_rendu.
        :param numero: le numéro de la demande renvoyé par soumettre_rendu
        """
        # 1. L'adresse d'état signée, demandée par le serveur d'Open WebUI : le jeton n'en sort pas.
        r = requests.get(
            f"{self.valves.studio_url}/api/suivi/{int(numero)}",
            timeout=10,
            headers={
                "Authorization": f"Bearer {self.valves.jeton}",
                "X-Utilisateur-Email": __user__.get("email", ""),
            },
        )
        if r.status_code != 200:
            return f"Suivi impossible pour la demande {numero} : {r.text[:200]}"
        info = r.json()
        # 2. La carte : le gabarit ci-dessous, rempli. Le titre vient de la conversation : échappé.
        page = (
            CARTE.replace("__ETAT__", json.dumps(info["etat"]))
            .replace("__TITRE__", html.escape(info["titre"]))
            .replace("__NUMERO__", str(info["numero"]))
        )
        # 3. Deux réponses : le widget pour l'utilisateur, une phrase pour le modèle.
        contexte = (
            f"Carte de suivi affichée pour la demande {info['numero']} ({info['titre']}) : elle montrera "
            "l'image, l'objet 3D et le lien de la scène. Ne les recopie pas."
        )
        return (
            HTMLResponse(content=page, headers={"Content-Disposition": "inline"}),
            contexte,
        )


CARTE = r"""<!doctype html><html><head><meta charset="utf-8">
<script type="module" src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>
<style>
  :root { color-scheme: light dark; --fond:#f8fafc; --texte:#0f172a; --doux:#64748b; --accent:#0891b2; --cadre:#e2e8f0; }
  @media (prefers-color-scheme: dark) { :root { --fond:#0f172a; --texte:#e2e8f0; --doux:#94a3b8; --cadre:#1e293b; } }
  * { box-sizing:border-box; margin:0; } body { font:19px/1.45 system-ui,'Segoe UI',sans-serif; color:var(--texte); background:transparent; }
  .carte { border:1px solid var(--cadre); border-radius:16px; background:var(--fond); padding:18px 20px; }
  .tete { display:flex; justify-content:space-between; align-items:baseline; gap:12px; }
  .titre { font-weight:650; font-size:21px; } .num { color:var(--doux); font-size:16px; }
  .etapes { display:flex; gap:6px; margin:12px 0 8px; }
  .etapes i { flex:1; height:8px; border-radius:4px; background:var(--cadre); transition:background .4s; }
  .etapes i.ok { background:var(--accent); }
  .etapes i.actif { background:linear-gradient(90deg,var(--accent),var(--cadre)); background-size:200% 100%; animation:defile 1.2s linear infinite; }
  @keyframes defile { from { background-position:100% 0 } to { background-position:-100% 0 } }
  .statut { color:var(--doux); font-size:18px; min-height:26px; }
  .vues { display:grid; gap:12px; grid-template-columns:1fr 1fr; margin-top:12px; }
  .vues img { display:block; width:100%; aspect-ratio:16/10; }
  .vues model-viewer { display:block; width:100%; height:100%; min-height:200px; }
  .vues img, .vues model-viewer { border-radius:10px; background:#e5e7eb; object-fit:cover; }
  .pied { display:flex; flex-wrap:wrap; gap:6px 18px; align-items:center; margin-top:12px; font-size:16px; color:var(--doux); }
  .pied a { color:var(--accent); font-weight:600; text-decoration:none; } .pied a:hover { text-decoration:underline; }
  .erreur { color:#dc2626; }
</style></head><body>
<div class="carte">
  <div class="tete"><span class="titre">__TITRE__</span><span class="num">Demande n° __NUMERO__</span></div>
  <div class="etapes"><i id="e1"></i><i id="e2"></i><i id="e3"></i></div>
  <div class="statut" id="statut">Connexion au studio…</div>
  <div id="resultat" hidden>
    <div class="vues"><img id="image" alt="Rendu"><model-viewer id="modele" camera-controls auto-rotate shadow-intensity="1"></model-viewer></div>
    <div class="pied">
      <a id="scene" target="_blank" hidden>Télécharger la scène Blender</a><span id="sans-scene" hidden>Scène Blender indisponible</span>
      <span id="assets"></span><span id="marquage"></span>
    </div>
  </div>
</div>
<script>
const ETAT = __ETAT__;  // adresse d'état signée, écrite par l'outil
const $ = (id) => document.getElementById(id);
const dire = (texte) => { $('statut').textContent = texte; };  // textContent : jamais de HTML venu du réseau

// Le cadre est isolé : Open WebUI ne peut pas le mesurer, il annonce lui-même sa hauteur.
const hauteur = () => parent.postMessage({ type: 'iframe:height', height: document.documentElement.scrollHeight }, '*');
new ResizeObserver(hauteur).observe(document.body);

function etapes(n, actif) {
  ['e1', 'e2', 'e3'].forEach((id, i) => { $(id).className = i < n ? 'ok' : (i === n && actif ? 'actif' : ''); });
}

function resultat(e) {
  $('image').src = e.png; $('modele').src = e.glb; $('modele').poster = e.png;
  if (e.scene === 'indisponible') $('sans-scene').hidden = false;
  else if (e.scene) { $('scene').href = e.scene; $('scene').hidden = false; }
  if (e.assets?.length) $('assets').textContent = 'Assets : ' + e.assets.map((a) => a.libelle).join(' · ');
  $('marquage').textContent = e.marquage_visible ? 'Marqué IA : métadonnées et bandeau' : 'Marqué IA : métadonnées';
  $('resultat').hidden = false;
}

async function suivre() {
  let e;
  try { e = await (await fetch(ETAT, { cache: 'no-store' })).json(); }
  catch { dire('Studio injoignable, nouvel essai…'); return setTimeout(suivre, 3000); }
  if (e.statut === 'en_attente') { etapes(0, true); dire(`Dans la file d'attente — position ${e.position}`); }
  else if (e.statut === 'en_cours') { etapes(1, true); dire(`Calcul en cours sur ${e.travailleur} — ${e.depuis_secondes} s`); }
  else if (e.statut === 'termine') {
    etapes(3, false);
    dire(`Prêt en ${e.duree_secondes} s, calculé par ${e.travailleur}. Faites tourner l'objet à la souris.`);
    return resultat(e);
  } else { etapes(0, false); dire(`Échec du rendu : ${e.erreur || 'erreur inconnue'}`); $('statut').className = 'statut erreur'; return; }
  setTimeout(suivre, 2000);  // toutes les deux secondes, jusqu'à la fin
}
suivre();
</script></body></html>"""
