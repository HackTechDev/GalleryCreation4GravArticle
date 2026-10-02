#!/usr/bin/env python3
"""Prépare une entrée du site (galerie orig/mini) et génère son item.md.

Usage :
    ./createGallery.py user/pages/04.conventions/01.anno_1900_2026 --title "Anno 1900 2026"

Étapes :
  1. Redimensionne les photos de <entrée>/orig/ SUR PLACE (grand côté ≤ ORIG_MAX px).
     Les originaux pleine résolution sont écrasés : garder une copie ailleurs.
  2. Génère <entrée>/mini/ (grand côté ≤ MINI_MAX px) pour chaque photo manquante.
  3. Crée item.md s'il n'existe pas, sinon remplace uniquement la galerie
     entre les marqueurs GALLERY_START / GALLERY_END (le texte écrit à la main est conservé).

Le script est idempotent : une photo déjà à la bonne taille n'est pas retouchée.
L'orientation EXIF est appliquée aux pixels et les métadonnées (dont le GPS) sont supprimées.
"""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ORIG_MAX = 1346  # ≈ 33 % d'une photo 4080×3072
MINI_MAX = 816   # ≈ 20 % d'une photo 4080×3072
JPEG_QUALITY = 85
EXTENSIONS = {".jpg", ".jpeg"}

GALLERY_START = "<!-- gallery:start -->"
GALLERY_END = "<!-- gallery:end -->"

FRONTMATTER = """---
title: "{title}"
date: '{date}'
publish_date: '{date}'
dateformat: 'd-m-Y H:i'
hero_classes: 'text-light title-h1h2 overlay-dark-gradient hero-large parallax'
show_sidebar: true
taxonomy:
    tag:
{tags}
feed:
    limit: 10
metadata:
    description: "{description}"
published: true
---

{intro}

"""


def list_photos(folder):
    # Les noms IMG_AAAAMMJJ_HHMMSS… sont chronologiques : le tri par nom suffit.
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)


def resize(src, dest, max_side):
    """Écrit dans dest une version de src dont le grand côté vaut au plus max_side.
    Retourne False si rien n'a été fait (déjà à la bonne taille et même fichier)."""
    with Image.open(src) as img:
        upright = img.getexif().get(0x0112, 1) == 1  # tag EXIF Orientation
        if src == dest and upright and max(img.size) <= max_side:
            return False
        oriented = ImageOps.exif_transpose(img)
        oriented.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        oriented.convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return True


def date_from_photos(photos):
    for photo in photos:
        match = re.match(r"IMG_(\d{4})(\d{2})(\d{2})_", photo.name)
        if match:
            year, month, day = match.groups()
            return f"{day}-{month}-{year} 00:00"
    return None


def gallery_block(photos):
    lines = [GALLERY_START, ""]
    for photo in photos:
        lines += [f"[![{photo.name}](mini/{photo.name})](orig/{photo.name})", ""]
    lines.append(GALLERY_END)
    return "\n".join(lines) + "\n"


def write_item(entry, photos, args):
    item = entry / "item.md"
    gallery = gallery_block(photos)

    if item.exists():
        text = item.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(GALLERY_START) + r".*?" + re.escape(GALLERY_END) + r"\n?", re.S)
        if pattern.search(text):
            text = pattern.sub(lambda _: gallery, text)
        else:
            text = text.rstrip("\n") + "\n\n" + gallery
        print(f"item.md mis à jour ({len(photos)} photos)")
    else:
        if not args.title:
            sys.exit("item.md n'existe pas : --title est obligatoire pour le créer.")
        date = args.date or date_from_photos(photos)
        if not date:
            sys.exit("Impossible de déduire la date des noms de fichiers : utiliser --date 'JJ-MM-AAAA HH:MM'.")
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        text = FRONTMATTER.format(
            title=args.title.replace('"', '\\"'),
            date=date,
            tags="\n".join(f"        - {t}" for t in tags) or "        - convention",
            description=(args.description or args.title).replace('"', '\\"'),
            intro=args.intro or f"Visite : {args.title}  \nDate : {date.split()[0].replace('-', '/')}",
        ) + gallery
        print(f"item.md créé ({len(photos)} photos)")

    item.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("entry", type=Path, help="dossier de l'entrée (contenant orig/)")
    parser.add_argument("--title", help="titre de la page (obligatoire à la création de item.md)")
    parser.add_argument("--date", help="'JJ-MM-AAAA HH:MM' (par défaut : date de la première photo)")
    parser.add_argument("--description", help="metadata.description (par défaut : le titre)")
    parser.add_argument("--tags", help="tags séparés par des virgules")
    parser.add_argument("--intro", help="texte d'introduction (par défaut : titre + date)")
    args = parser.parse_args()

    orig_dir = args.entry / "orig"
    mini_dir = args.entry / "mini"
    if not orig_dir.is_dir():
        sys.exit(f"Dossier introuvable : {orig_dir}")
    mini_dir.mkdir(exist_ok=True)

    photos = list_photos(orig_dir)
    if not photos:
        sys.exit(f"Aucune photo JPG dans {orig_dir}")

    resized = created = 0
    for photo in photos:
        if resize(photo, photo, ORIG_MAX):
            resized += 1
        mini = mini_dir / photo.name
        if not mini.exists():
            resize(photo, mini, MINI_MAX)
            created += 1
    print(f"orig : {resized} redimensionnée(s) / mini : {created} créée(s) / {len(photos)} photos")

    write_item(args.entry, photos, args)


if __name__ == "__main__":
    main()
