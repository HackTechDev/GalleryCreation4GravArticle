# Analyse de `createGallery.py`

Analyse du 2 octobre 2026. Le script est propre : bien découpé, idempotent et documenté. Il reste un vrai bug de confidentialité et quelques points fragiles.

## Ce que fait le script

1. **Liste les photos** de `<entrée>/orig/` (`.jpg` / `.jpeg`), triées par nom, donc par date pour les noms `IMG_AAAAMMJJ_…`.
2. **Réduit `orig/` sur place** à 1346 px au plus sur le grand côté. Il applique l'orientation EXIF et enregistre en JPEG qualité 85, sans métadonnées.
3. **Crée `mini/`** (816 px) pour chaque photo qui n'a pas encore de vignette, à partir de l'`orig` déjà réduit.
4. **Écrit `item.md`** :
   - s'il n'existe pas, il le crée avec l'en-tête Grav (le front matter) et la galerie ;
   - s'il existe, il remplace seulement le bloc entre `<!-- gallery:start -->` et `<!-- gallery:end -->`.

## Problèmes

### 1. Le GPS n'est pas toujours supprimé (bug de confidentialité)

`createGallery.py:65` : si une photo est déjà assez petite et bien orientée, le script ne la réenregistre pas. Ses métadonnées EXIF, GPS compris, restent donc dans `orig/` et sont publiées. Le docstring et le README promettent pourtant le contraire.

Cas concret : une photo exportée d'un téléphone ou d'une messagerie en 1200 px, avec sa position GPS. Elle passe telle quelle.

**Correction :** ajouter au test d'idempotence une condition « l'image n'a pas d'EXIF », par exemple `and not img.getexif()`. Les photos déjà traitées n'en ont plus, donc le script reste idempotent.

### 2. L'écriture sur place n'est pas atomique

`createGallery.py:69` : le script écrit directement par-dessus l'original. Si le script plante ou si le disque est plein pendant l'écriture, la photo est perdue.

**Correction :** enregistrer d'abord dans un fichier temporaire du même dossier, puis le renommer avec `os.replace()`.

### 3. Un fichier illisible arrête tout le traitement

Il n'y a pas de `try/except` autour de `Image.open`. Un JPEG corrompu, ou un fichier caché macOS `._IMG_xxx.jpg` (fréquent après une copie depuis un Mac ou une clé USB), lève une exception. Le script s'arrête alors au milieu : une partie des photos est traitée et `item.md` n'est pas écrit.

**Correction :** ignorer les fichiers qui commencent par `.` dans `list_photos` et sauter les fichiers illisibles avec un avertissement.

### 4. Les noms de fichiers avec espaces ou parenthèses cassent le Markdown

`createGallery.py:85` : `mini/Photo (2).jpg` donne un lien invalide.

**Correction :** encoder le nom avec `urllib.parse.quote(photo.name)` ou entourer le chemin de `<…>`.

### 5. Front matter YAML fragile

- `createGallery.py:112` : les tags sont écrits sans guillemets. Un tag contenant `:` ou `#`, ou commençant par `-` ou `[`, casse le YAML.
- `createGallery.py:110` : seuls les `"` sont échappés dans le titre et la description, pas les `\`.
- `--date` n'est pas vérifié : un format erroné arrive tel quel dans Grav.

### 6. La date n'est trouvée que pour les noms `IMG_…`

`createGallery.py:75` : les noms `PXL_20260315_…` (Pixel), `20260315_142233.jpg` (Samsung) ou `DSC…` ne sont pas reconnus, et il faut alors passer `--date`.

**Correction :** utiliser une regex plus souple, `(\d{4})(\d{2})(\d{2})_\d{6}`, ou lire l'EXIF `DateTimeOriginal` avant sa suppression.

## Points mineurs

- **Double compression JPEG** : la vignette est faite à partir de l'`orig` déjà réencodé en qualité 85. La perte est négligeable à 816 px.
- **Profil couleur supprimé** : le profil ICC disparaît avec les métadonnées. Les photos d'iPhone (en Display P3) peuvent paraître un peu ternes.
- **`item.md` réécrit à chaque lancement**, même sans changement. Sa date de modification change, ce qui peut invalider le cache de Grav.
- **Plusieurs blocs de galerie** : s'il y en a plusieurs dans `item.md`, ils sont tous remplacés par la galerie complète, qui se retrouve en double.
- **Vignettes orphelines** : une vignette dont la photo a été supprimée reste dans `mini/` et n'est jamais nettoyée. C'est documenté, mais une option `--clean` serait simple à ajouter.
- **Chemin dans le README** : il indique `./createGallery.py` « depuis la racine de Grav », alors que le script est dans `scripts/generateGallery/`.

## Priorités

1. Point 1 (GPS) : fuite de données personnelles.
2. Point 3 (fichiers illisibles) : arrêt du script en plein traitement.
3. Point 2 (écriture atomique) : risque de perte d'une photo.
4. Points 4 à 6, puis les points mineurs.
