# createGallery.py

Prépare une entrée du site (galerie photo `orig/` + `mini/`) et génère ou met à jour son `item.md`.

## Prérequis

- Python 3
- [Pillow](https://pypi.org/project/pillow/) : `pip install pillow` (ou `apt install python3-pil`)

## Utilisation

Depuis la racine de Grav :

```sh
./createGallery.py user/pages/04.conventions/01.anno_1900_2026 --title "Anno 1900 2026"
```

Le dossier de l'entrée doit contenir un sous-dossier `orig/` avec les photos JPG (`.jpg` / `.jpeg`).

### Options

| Option | Rôle | Défaut |
|---|---|---|
| `entry` (positionnel) | Dossier de l'entrée, contenant `orig/` | — |
| `--title` | Titre de la page | **obligatoire** à la création de `item.md` |
| `--date` | Date au format `'JJ-MM-AAAA HH:MM'` | déduite du nom de la première photo (`IMG_AAAAMMJJ_…`), à `00:00` |
| `--description` | `metadata.description` | le titre |
| `--tags` | Tags séparés par des virgules | `convention` |
| `--intro` | Texte d'introduction sous le front matter | `Visite : <titre>` + `Date : JJ/MM/AAAA` |

Les options `--title`, `--date`, `--description`, `--tags` et `--intro` ne servent qu'à la **création** de `item.md` ; elles sont ignorées s'il existe déjà.

## Ce que fait le script

1. **Redimensionne `orig/` sur place** : grand côté ramené à 1346 px au plus (≈ 33 % d'une photo 4080×3072), JPEG qualité 85.
2. **Génère `mini/`** : une vignette par photo (grand côté ≤ 816 px, ≈ 20 %), uniquement pour les photos qui n'en ont pas encore.
3. **Écrit `item.md`** :
   - s'il n'existe pas, il est créé avec le front matter (titre, dates, hero, tags, description…), l'intro et la galerie ;
   - s'il existe, seule la galerie entre `<!-- gallery:start -->` et `<!-- gallery:end -->` est remplacée ; le texte écrit à la main est conservé. Sans marqueurs, la galerie est ajoutée en fin de fichier.

Chaque photo de la galerie est une vignette cliquable vers l'image `orig/` :

```md
[![IMG_20260315_142233.jpg](mini/IMG_20260315_142233.jpg)](orig/IMG_20260315_142233.jpg)
```

Les photos sont triées par nom de fichier, donc chronologiquement pour les noms `IMG_AAAAMMJJ_HHMMSS…`.

## À savoir

- ⚠️ **Les originaux pleine résolution sont écrasés.** Garder une copie ailleurs avant de lancer le script.
- L'orientation EXIF est appliquée aux pixels, puis **toutes les métadonnées sont supprimées** (dont la position GPS).
- Le script est **idempotent** : une photo déjà à la bonne taille et correctement orientée n'est pas retouchée, et une vignette existante n'est pas régénérée. On peut donc le relancer après avoir ajouté des photos dans `orig/`.
- Pour régénérer une vignette (photo remplacée, recadrée…), supprimer le fichier correspondant dans `mini/` puis relancer.
- Après avoir supprimé une photo de `orig/`, relancer le script pour la retirer de la galerie ; penser à supprimer aussi sa vignette dans `mini/`.

## Exemple complet

```sh
mkdir -p user/pages/04.conventions/02.mon_salon_2026/orig
cp ~/Photos/salon/*.jpg user/pages/04.conventions/02.mon_salon_2026/orig/
./createGallery.py user/pages/04.conventions/02.mon_salon_2026 \
    --title "Mon Salon 2026" \
    --tags "convention,horreur" \
    --description "Photos du Mon Salon 2026"
```

Sortie :

```
orig : 42 redimensionnée(s) / mini : 42 créée(s) / 42 photos
item.md créé (42 photos)
```
