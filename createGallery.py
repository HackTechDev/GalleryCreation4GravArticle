#!/usr/bin/env python3
"""Prépare une entrée du site (galerie orig/mini) et génère son item.md.

Usage :
    ./createGallery.py user/pages/03.convention/13.anno_1900_2026 --title "Anno 1900 2026"

Étapes :
  1. Redimensionne les photos de <entrée>/orig/ SUR PLACE (grand côté ≤ ORIG_MAX px).
     Les originaux pleine résolution sont écrasés : garder une copie ailleurs.
  2. Génère <entrée>/mini/ (grand côté ≤ MINI_MAX px) pour chaque photo manquante.
  3. Crée item.md s'il n'existe pas, sinon remplace uniquement la galerie
     entre les marqueurs GALLERY_START / GALLERY_END (le texte écrit à la main est conservé).

Le script est idempotent : une photo déjà à la bonne taille et sans métadonnées n'est pas retouchée.
L'orientation EXIF est appliquée aux pixels et les métadonnées (EXIF, dont le GPS, et XMP)
sont supprimées ; seul le profil couleur ICC est conservé.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps

ORIG_MAX = 1346  # ≈ 33 % d'une photo 4080×3072
MINI_MAX = 816   # ≈ 20 % d'une photo 4080×3072
JPEG_QUALITY = 85
EXTENSIONS = {".jpg", ".jpeg"}
DATE_FORMAT = "%d-%m-%Y %H:%M"

# Erreurs possibles à l'ouverture d'une photo corrompue ou qui n'est pas un JPEG.
IMAGE_ERRORS = (OSError, ValueError, SyntaxError, Image.DecompressionBombError)

GALLERY_START = "<!-- gallery:start -->"
GALLERY_END = "<!-- gallery:end -->"

FRONTMATTER = """---
title: {title}
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
    description: {description}
published: true
---

{intro}

"""


def list_photos(folder):
    # Les noms IMG_AAAAMMJJ_HHMMSS… sont chronologiques : le tri par nom suffit.
    # Les fichiers cachés (._IMG… de macOS, fichiers temporaires) sont ignorés.
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in EXTENSIONS
    )


def resize(src, dest, max_side):
    """Écrit dans dest une version de src dont le grand côté vaut au plus max_side.
    Retourne False si rien n'a été fait (même fichier, déjà à la bonne taille,
    bien orienté et sans métadonnées)."""
    with Image.open(src) as img:
        exif = img.getexif()
        upright = exif.get(0x0112, 1) == 1  # tag EXIF Orientation
        clean = not exif and "xmp" not in img.info
        if src == dest and upright and clean and max(img.size) <= max_side:
            return False
        icc_profile = img.info.get("icc_profile")
        oriented = ImageOps.exif_transpose(img)
        oriented.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        rgb = oriented.convert("RGB")

    # Écriture dans un fichier temporaire puis renommage : si l'enregistrement
    # échoue, la photo d'origine reste intacte.
    tmp = dest.with_name(f".{dest.name}.tmp")
    try:
        save_args = {"quality": JPEG_QUALITY, "optimize": True}
        if icc_profile:
            save_args["icc_profile"] = icc_profile
        rgb.save(tmp, "JPEG", **save_args)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return True


def exif_date(photo):
    """Date de prise de vue (DateTimeOriginal, sinon DateTime) ou None."""
    try:
        with Image.open(photo) as img:
            exif = img.getexif()
            value = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
        return datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
    except (*IMAGE_ERRORS, TypeError):
        return None


def date_from_photos(photos):
    """Date de la première photo, déduite du nom (IMG_/PXL_/… AAAAMMJJ_HHMMSS)
    ou à défaut de l'EXIF. À appeler avant le redimensionnement, qui efface l'EXIF."""
    for photo in photos:
        match = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})_\d{6}", photo.name)
        if match:
            year, month, day = match.groups()
            try:
                return datetime(int(year), int(month), int(day)).strftime(DATE_FORMAT)
            except ValueError:
                pass
    for photo in photos:
        taken = exif_date(photo)
        if taken:
            return taken.strftime("%d-%m-%Y 00:00")
    return None


def yaml_str(value):
    """Chaîne YAML entre guillemets doubles."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def gallery_block(photos):
    lines = [GALLERY_START, ""]
    for photo in photos:
        alt = photo.name.replace("[", "\\[").replace("]", "\\]")
        url = quote(photo.name)
        lines += [f"[![{alt}](mini/{url})](orig/{url})", ""]
    lines.append(GALLERY_END)
    return "\n".join(lines) + "\n"


def write_item(item, photos, args, date):
    gallery = gallery_block(photos)

    if item.exists():
        old = item.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(GALLERY_START) + r".*?" + re.escape(GALLERY_END) + r"\n?", re.S)
        blocks = 0

        def replace(_):
            # Le premier bloc reçoit la galerie, les éventuels doublons sont supprimés.
            nonlocal blocks
            blocks += 1
            return gallery if blocks == 1 else ""

        text = pattern.sub(replace, old)
        if not blocks:
            text = old.rstrip("\n") + "\n\n" + gallery
        if text == old:
            print(f"item.md inchangé ({len(photos)} photos)")
            return
        print(f"item.md mis à jour ({len(photos)} photos)")
    else:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else ["convention"]
        text = FRONTMATTER.format(
            title=yaml_str(args.title),
            date=date,
            tags="\n".join(f"        - {yaml_str(t)}" for t in tags),
            description=yaml_str(args.description or args.title),
            intro=args.intro or f"Visite : {args.title}  \nDate : {date.split()[0].replace('-', '/')}",
        ) + gallery
        print(f"item.md créé ({len(photos)} photos)")

    item.write_text(text, encoding="utf-8")


def clean_minis(mini_dir, photos):
    """Supprime les vignettes dont la photo n'existe plus dans orig/."""
    names = {p.name for p in photos}
    removed = 0
    for mini in list_photos(mini_dir):
        if mini.name not in names:
            mini.unlink()
            removed += 1
    print(f"mini : {removed} vignette(s) orpheline(s) supprimée(s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("entry", type=Path, help="dossier de l'entrée (contenant orig/)")
    parser.add_argument("--title", help="titre de la page (obligatoire à la création de item.md)")
    parser.add_argument("--date", help="'JJ-MM-AAAA HH:MM' (par défaut : date de la première photo)")
    parser.add_argument("--description", help="metadata.description (par défaut : le titre)")
    parser.add_argument("--tags", help="tags séparés par des virgules")
    parser.add_argument("--intro", help="texte d'introduction (par défaut : titre + date)")
    parser.add_argument("--clean", action="store_true", help="supprimer les vignettes de mini/ sans photo dans orig/")
    args = parser.parse_args()

    if args.date:
        try:
            datetime.strptime(args.date, DATE_FORMAT)
        except ValueError:
            sys.exit(f"Date invalide : {args.date!r} (format attendu : 'JJ-MM-AAAA HH:MM').")

    orig_dir = args.entry / "orig"
    mini_dir = args.entry / "mini"
    item = args.entry / "item.md"
    if not orig_dir.is_dir():
        sys.exit(f"Dossier introuvable : {orig_dir}")

    photos = list_photos(orig_dir)
    if not photos:
        sys.exit(f"Aucune photo JPG dans {orig_dir}")

    # Vérifications de création faites avant de toucher aux photos,
    # et date lue avant que le redimensionnement n'efface l'EXIF.
    date = None
    if not item.exists():
        if not args.title:
            sys.exit("item.md n'existe pas : --title est obligatoire pour le créer.")
        date = args.date or date_from_photos(photos)
        if not date:
            sys.exit("Impossible de déduire la date des photos : utiliser --date 'JJ-MM-AAAA HH:MM'.")

    mini_dir.mkdir(exist_ok=True)
    resized = created = 0
    valid = []
    for photo in photos:
        try:
            if resize(photo, photo, ORIG_MAX):
                resized += 1
            mini = mini_dir / photo.name
            if not mini.exists():
                resize(photo, mini, MINI_MAX)
                created += 1
        except IMAGE_ERRORS as error:
            print(f"Ignorée : {photo.name} ({error})", file=sys.stderr)
            continue
        valid.append(photo)
    skipped = len(photos) - len(valid)
    print(f"orig : {resized} redimensionnée(s) / mini : {created} créée(s) / {len(valid)} photos"
          + (f" / {skipped} ignorée(s)" if skipped else ""))

    if args.clean:
        clean_minis(mini_dir, photos)

    if not valid:
        sys.exit("Aucune photo traitée : item.md n'est pas modifié.")
    write_item(item, valid, args, date)


if __name__ == "__main__":
    main()
