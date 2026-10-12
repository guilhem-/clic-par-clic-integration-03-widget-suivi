# Un widget de suivi dans la conversation — outil natif Open WebUI, HTMLResponse, état signé

Code et configuration de la démonstration du module 3 de la série « Clic par clic » **Intégrations IA**
(Open WebUI relié au studio 3D de l'organisation).

Vidéo : {{video}}

## But

Au module 2, le studio prévenait l'utilisatrice par un message direct, hors de la conversation. Ici, le
suivi se fait **dans le message** : un **outil natif** d'Open WebUI, « Suivi des rendus », renvoie une
`HTMLResponse` (en-tête `Content-Disposition: inline`). Open WebUI l'affiche comme un **widget**, dans un
cadre isolé, et ce widget interroge lui-même, depuis le navigateur, une **adresse d'état signée** du
studio, toutes les deux secondes, jusqu'à l'image, l'objet 3D, le lien de la scène Blender, les assets de
la bibliothèque utilisés et la mention du marquage.

```
modèle ──soumettre_rendu (MCP)──▶ studio
modèle ──suivre_rendu──▶ outil natif (serveur d'Open WebUI) ──jeton + utilisateur──▶ studio /api/suivi/<n>
                              └── HTMLResponse ──▶ widget (navigateur) ──toutes les 2 s──▶ studio /s/<n>/<signature>
```

Contenu, à l'état montré en fin de vidéo :

| Fichier | Rôle |
|---|---|
| `open-webui/suivi_rendus.py` | L'outil natif : vannes (adresse interne du studio, jeton en champ masqué), fonction `suivre_rendu(numero)` qui demande l'adresse signée au studio **depuis le serveur** (le jeton ne sort jamais), remplit le gabarit de la carte (titre échappé) et renvoie deux choses : le widget, et une phrase pour le modèle. Puis la carte elle-même (`CARTE`) : HTML, `model-viewer`, et le script qui annonce sa hauteur (`postMessage` « iframe:height »), interroge l'état et n'écrit jamais de HTML venu du réseau (`textContent`) |
| `open-webui/consignes-modele.txt` | Les consignes du module 1, plus une phrase (dernière ligne) : appeler `suivre_rendu` après chaque `soumettre_rendu`, sans recopier l'image |
| `studio/integrations.py` | Côté studio : `/api/suivi/<n>` (interne : jeton du studio, adresse de l'utilisateur, sa demande seulement) renvoie l'adresse d'état ; `/s/<n>/<signature>` (publique, lecture seule) renvoie l'état sans identité ni code : position, worker, puis image, objet 3D, scène Blender, assets, marquage |
| `studio/k8s-integrations.yaml` | Publie `/s/` (et elle seule) par l'Ingress Traefik du cluster |
| `installer.py` | L'outil, ses vannes, son activation sur le modèle et la consigne, par l'API d'Open WebUI (`--retirer` pour revenir à l'état du module 1) |

## Pourquoi un cadre isolé et une adresse signée ?

Open WebUI affiche le widget dans un `iframe` **sans `allow-same-origin`** : son script s'exécute, mais ne
voit ni les cookies ni la session d'Open WebUI, et Open WebUI ne peut pas en mesurer la hauteur ; c'est
pourquoi la page l'annonce elle-même (`parent.postMessage({ type: 'iframe:height', height }, '*')`).

Le widget tourne dans le navigateur de l'utilisateur : il ne doit recevoir **ni le jeton du studio, ni
l'identité de l'utilisateur**. L'outil (sur le serveur) échange ces deux preuves contre une adresse
signée (HMAC du numéro avec le secret du studio), valable pour un seul rendu, en lecture seule ; une
signature fausse renvoie 404. L'état publié contient les liens signés du studio (la scène Blender passe
par une redirection vers un lien présigné d'une minute, comme au module 2).

## Prérequis

- L'état de fin du **module 1** : dépôt [clic-par-clic-integration-01-brancher-studio](https://github.com/guilhem-/clic-par-clic-integration-01-brancher-studio)
  (connexion MCP « Studio 3D », modèle « Studio 3D », groupe « Graphistes »). Le notificateur du module 2
  n'est pas nécessaire (les deux méthodes se combinent).
- Le studio 3D dans sa dernière version, déployé dans le même cluster qu'Open WebUI : dépôt
  [clic-par-clic-studio3d-06-stockage-s3](https://github.com/guilhem-/clic-par-clic-studio3d-06-stockage-s3)
  (image `studio3d:5`, Redis, workers, bibliothèque d'assets, stockage S3).
- Open WebUI 0.11 (tourné sur 0.11.3), un compte **administrateur** et son jeton.
- `kubectl` relié au cluster, Python 3.10 ou plus récent (bibliothèque standard seulement).

## Installation pas à pas

### 1. Les routes du studio

`integrations.py` s'ajoute à l'image du studio : `api.py` le charge s'il est présent. Dans le dépôt du
module 6 de la série Studio 3D :

```bash
cp studio/integrations.py ../clic-par-clic-studio3d-06-stockage-s3/studio/
# Dockerfile : COPY commun.py api.py travailleur.py … integrations.py ./
docker build -t studio3d:5 ../clic-par-clic-studio3d-06-stockage-s3/studio
k3d image import studio3d:5 -c <votre cluster>     # avec k3d ; sinon, poussez l'image dans votre registre
kubectl rollout restart deployment/studio-api -n studio3d
kubectl apply -f studio/k8s-integrations.yaml        # publie /s/ sur studio.localhost
```

Adaptez `host` dans `k8s-integrations.yaml` et la variable `STUDIO_PUBLIC_URL` du studio à l'adresse vue
par les navigateurs de vos utilisateurs.

### 2. À la main, comme dans la vidéo

1. **Espace de travail › Outils › Créer** : nom « Suivi des rendus », description ; collez le contenu de
   `open-webui/suivi_rendus.py` dans l'éditeur ; **Accès** › groupe « Graphistes » ;
   **Enregistrer & Créer**, puis **Confirmer** (un outil exécute du code sur le serveur).
2. Dans la liste des outils, roue **Vannes** de « Suivi des rendus » : l'adresse interne du studio est
   proposée par défaut ; collez le jeton du studio (champ masqué) ; **Enregistrer**.
3. **Espace de travail › Modèles › Studio 3D** : cochez l'outil « Suivi des rendus » ; à la fin des
   consignes, ajoutez la dernière ligne de `open-webui/consignes-modele.txt` ;
   **Enregistrer & Mettre à jour**.

### 3. Ou par le script

```bash
cp .env.example .env          # OWUI_URL, OWUI_JETON, STUDIO_URL, STUDIO_JETON, GROUPE
python installer.py           # outil, vannes, modèle, consigne
python installer.py --retirer # revient à l'état du module 1
```

## Essai

Avec le compte d'un membre du groupe « Graphistes », modèle « Studio 3D » : « Crée une scène de salon
avec le fauteuil et le vase en céramique de la bibliothèque, sous l'éclairage salon bois. » La carte de
suivi apparaît dans la réponse (file d'attente, puis calcul), puis l'image, l'objet 3D à faire tourner,
le lien « Télécharger la scène Blender », les assets utilisés et le marquage. Rechargez la page : la carte
est enregistrée avec la conversation.

L'adresse lue par le widget se lit aussi à la main :

```bash
curl -s http://studio.localhost:8080/s/1/<signature>          # l'état, en JSON
curl -s -o /dev/null -w "%{http_code}" http://studio.localhost:8080/s/1/<autre signature>   # 404
```

## Sécurité

- Le jeton du studio reste dans les vannes de l'outil, sur le serveur d'Open WebUI (champ masqué).
- Le widget ne reçoit qu'une adresse signée, en lecture seule, pour un seul rendu ; l'état publié ne
  contient ni l'adresse de l'utilisateur, ni le code de la scène.
- Le titre de la demande (écrit par le modèle) est échappé dans le gabarit ; le script n'affiche les
  textes venus du réseau qu'avec `textContent`.
- Aucun secret dans ce dépôt (`.env` est ignoré par git).

## Série

- Module précédent : **Prévenir l'utilisateur quand son rendu est prêt** —
  [clic-par-clic-integration-02-notifications](https://github.com/guilhem-/clic-par-clic-integration-02-notifications).
- Module suivant : **Le studio comme un modèle : une fonction Pipe**.
- Construire le studio : série « Créer un service d'IA compatible agentique : le studio 3D »
  (dépôts `clic-par-clic-studio3d-01` à `06`).

## Licence

MIT (voir `LICENSE`).
