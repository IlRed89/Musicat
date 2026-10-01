"""
Unified Audio Tag Editor for Musicat.
Provides comprehensive Mp3tag-grade read/write capabilities across
MP3, FLAC, M4A/AAC, WAV, AIFF, and OGG formats with deep DJ-specific tag support.
"""

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import mutagen
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TALB,
    TPE2,
    TCON,
    TDRC,
    TYER,
    TRCK,
    TPOS,
    TBPM,
    TKEY,
    TPE4,
    TPUB,
    COMM,
    TXXX,
    APIC,
    PictureType,
    ID3NoHeaderError,
)
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
from mutagen.oggvorbis import OggVorbis


SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".aif", ".aiff", ".ogg"}


@dataclass
class CoverArt:
    data: bytes
    mime_type: str = "image/jpeg"
    description: str = ""
    pic_type: int = 3  # 3 = Front Cover


@dataclass
class AudioMetadata:
    filepath: str
    filename: str = ""
    filesize: int = 0
    file_mtime: float = 0.0
    duration: float = 0.0
    bitrate: int = 0
    sample_rate: int = 0
    format: str = ""

    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    year: Optional[int] = None
    genre: str = ""
    track_num: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_num: Optional[int] = None
    bpm: Optional[float] = None
    musical_key: str = ""
    camelot_key: str = ""
    label: str = ""
    remixer: str = ""
    comment: str = ""
    energy_level: Optional[int] = None
    rating: int = 0
    has_cover: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AudioTagEditor:
    """Read, modify, and save audio metadata and artwork across various formats."""

    @staticmethod
    def is_supported(filepath: Union[str, Path]) -> bool:
        return Path(filepath).suffix.lower() in SUPPORTED_EXTENSIONS

    @classmethod
    def read_metadata(cls, filepath: Union[str, Path]) -> AudioMetadata:
        """Reads all technical and tag metadata from an audio file."""
        path_obj = Path(filepath)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = path_obj.suffix.lower()
        stat = path_obj.stat()

        meta = AudioMetadata(
            filepath=str(path_obj.resolve()),
            filename=path_obj.name,
            filesize=stat.st_size,
            file_mtime=stat.st_mtime,
            format=ext.lstrip("."),
        )

        try:
            audio = mutagen.File(str(path_obj))
            if audio is not None and audio.info is not None:
                meta.duration = getattr(audio.info, "length", 0.0)
                meta.bitrate = int(getattr(audio.info, "bitrate", 0) / 1000) if getattr(audio.info, "bitrate", 0) else 0
                meta.sample_rate = getattr(audio.info, "sample_rate", 0)

            if ext == ".mp3":
                cls._read_mp3(path_obj, meta)
            elif ext == ".flac":
                cls._read_flac(path_obj, meta)
            elif ext in (".m4a", ".aac"):
                cls._read_mp4(path_obj, meta)
            elif ext == ".wav":
                cls._read_wav(path_obj, meta)
            elif ext in (".aif", ".aiff"):
                cls._read_aiff(path_obj, meta)
            elif ext == ".ogg":
                cls._read_ogg(path_obj, meta)
        except Exception:
            # Return partial info if tagging header parsing encountered minor issues
            pass

        return meta

    @classmethod
    def _read_mp3(cls, path_obj: Path, meta: AudioMetadata) -> None:
        try:
            tags = ID3(str(path_obj))
        except (ID3NoHeaderError, Exception):
            return

        cls._extract_id3_tags(tags, meta)

    @classmethod
    def _extract_id3_tags(cls, tags: ID3, meta: AudioMetadata) -> None:
        if "TIT2" in tags:
            meta.title = str(tags["TIT2"].text[0]) if tags["TIT2"].text else ""
        if "TPE1" in tags:
            meta.artist = str(tags["TPE1"].text[0]) if tags["TPE1"].text else ""
        if "TALB" in tags:
            meta.album = str(tags["TALB"].text[0]) if tags["TALB"].text else ""
        if "TPE2" in tags:
            meta.album_artist = str(tags["TPE2"].text[0]) if tags["TPE2"].text else ""
        if "TCON" in tags:
            meta.genre = str(tags["TCON"].text[0]) if tags["TCON"].text else ""
        if "TPE4" in tags:
            meta.remixer = str(tags["TPE4"].text[0]) if tags["TPE4"].text else ""
        if "TPUB" in tags:
            meta.label = str(tags["TPUB"].text[0]) if tags["TPUB"].text else ""

        # Year
        for ykey in ("TDRC", "TYER"):
            if ykey in tags and tags[ykey].text:
                raw_year = str(tags[ykey].text[0])
                m = re.search(r"\b(\d{4})\b", raw_year)
                if m:
                    meta.year = int(m.group(1))
                    break

        # Track number
        if "TRCK" in tags and tags["TRCK"].text:
            raw_tr = str(tags["TRCK"].text[0])
            parts = raw_tr.split("/")
            if parts[0].isdigit():
                meta.track_num = int(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                meta.total_tracks = int(parts[1])

        # Disc number
        if "TPOS" in tags and tags["TPOS"].text:
            raw_disc = str(tags["TPOS"].text[0])
            parts = raw_disc.split("/")
            if parts[0].isdigit():
                meta.disc_num = int(parts[0])

        # BPM
        if "TBPM" in tags and tags["TBPM"].text:
            try:
                meta.bpm = round(float(tags["TBPM"].text[0]), 1)
            except Exception:
                pass

        # Musical Key
        if "TKEY" in tags and tags["TKEY"].text:
            meta.musical_key = str(tags["TKEY"].text[0])

        # TXXX frames (INITIALKEY, EnergyLevel, etc.)
        for key, frame in tags.items():
            if isinstance(frame, TXXX):
                desc = frame.desc.upper()
                text = frame.text[0] if frame.text else ""
                if desc in ("INITIALKEY", "INITIAL KEY", "CAMELOT", "CAMELOT_KEY"):
                    meta.camelot_key = str(text)
                elif desc in ("ENERGY", "ENERGYLEVEL", "ENERGY_LEVEL"):
                    try:
                        meta.energy_level = int(text)
                    except Exception:
                        pass
                elif desc == "REMIXER" and not meta.remixer:
                    meta.remixer = str(text)
                elif desc == "LABEL" and not meta.label:
                    meta.label = str(text)

        # Comments
        for key, frame in tags.items():
            if isinstance(frame, COMM):
                meta.comment = str(frame.text[0]) if frame.text else ""
                break

        # Artwork detection
        for key, frame in tags.items():
            if isinstance(frame, APIC):
                meta.has_cover = True
                break

    @classmethod
    def _read_flac(cls, path_obj: Path, meta: AudioMetadata) -> None:
        audio = FLAC(str(path_obj))
        if audio.pictures:
            meta.has_cover = True

        def get_field(k: str) -> str:
            vals = audio.get(k, [])
            return str(vals[0]) if vals else ""

        meta.title = get_field("TITLE")
        meta.artist = get_field("ARTIST")
        meta.album = get_field("ALBUM")
        meta.album_artist = get_field("ALBUMARTIST") or get_field("ALBUM ARTIST")
        meta.genre = get_field("GENRE")
        meta.remixer = get_field("REMIXER")
        meta.label = get_field("LABEL") or get_field("ORGANIZATION")
        meta.comment = get_field("COMMENT") or get_field("DESCRIPTION")

        date_val = get_field("DATE") or get_field("YEAR")
        m = re.search(r"\b(\d{4})\b", date_val)
        if m:
            meta.year = int(m.group(1))

        tr_val = get_field("TRACKNUMBER")
        if tr_val.isdigit():
            meta.track_num = int(tr_val)
        tr_tot = get_field("TRACKTOTAL") or get_field("TOTALTRACKS")
        if tr_tot.isdigit():
            meta.total_tracks = int(tr_tot)

        disc_val = get_field("DISCNUMBER")
        if disc_val.isdigit():
            meta.disc_num = int(disc_val)

        bpm_val = get_field("BPM") or get_field("TBPM")
        try:
            if bpm_val:
                meta.bpm = round(float(bpm_val), 1)
        except Exception:
            pass

        meta.musical_key = get_field("KEY") or get_field("TKEY")
        meta.camelot_key = get_field("INITIALKEY") or get_field("CAMELOT") or get_field("CAMELOT_KEY")
        en_val = get_field("ENERGYLEVEL") or get_field("ENERGY")
        if en_val.isdigit():
            meta.energy_level = int(en_val)

    @classmethod
    def _read_mp4(cls, path_obj: Path, meta: AudioMetadata) -> None:
        audio = MP4(str(path_obj))

        def get_field(k: str) -> str:
            vals = audio.get(k, [])
            if isinstance(vals, list) and vals:
                return str(vals[0])
            return str(vals) if vals else ""

        meta.title = get_field("\xa9nam")
        meta.artist = get_field("\xa9ART")
        meta.album = get_field("\xa9alb")
        meta.album_artist = get_field("aART")
        meta.genre = get_field("\xa9gen")
        meta.comment = get_field("\xa9cmt")

        day_val = get_field("\xa9day")
        m = re.search(r"\b(\d{4})\b", day_val)
        if m:
            meta.year = int(m.group(1))

        if "trkn" in audio and audio["trkn"]:
            trkn = audio["trkn"][0]
            if len(trkn) > 0 and trkn[0]:
                meta.track_num = trkn[0]
            if len(trkn) > 1 and trkn[1]:
                meta.total_tracks = trkn[1]

        if "disk" in audio and audio["disk"]:
            disk = audio["disk"][0]
            if len(disk) > 0 and disk[0]:
                meta.disc_num = disk[0]

        if "tmpo" in audio and audio["tmpo"]:
            tempo = audio["tmpo"][0]
            if tempo:
                meta.bpm = float(tempo)

        # Freeform tags
        for key, val in audio.items():
            if key.startswith("----:com.apple.iTunes:"):
                tag_name = key.split(":")[-1].upper()
                text = val[0].decode("utf-8", "ignore") if isinstance(val[0], bytes) else str(val[0])
                if tag_name in ("INITIALKEY", "CAMELOT"):
                    meta.camelot_key = text
                elif tag_name in ("KEY", "MUSICALKEY"):
                    meta.musical_key = text
                elif tag_name in ("REMIXER",):
                    meta.remixer = text
                elif tag_name in ("LABEL", "PUBLISHER"):
                    meta.label = text
                elif tag_name in ("ENERGYLEVEL", "ENERGY"):
                    if text.isdigit():
                        meta.energy_level = int(text)

        if "covr" in audio and audio["covr"]:
            meta.has_cover = True

    @classmethod
    def _read_wav(cls, path_obj: Path, meta: AudioMetadata) -> None:
        try:
            audio = WAVE(str(path_obj))
            if audio.tags:
                cls._extract_id3_tags(audio.tags, meta)
        except Exception:
            pass

    @classmethod
    def _read_aiff(cls, path_obj: Path, meta: AudioMetadata) -> None:
        try:
            audio = AIFF(str(path_obj))
            if audio.tags:
                cls._extract_id3_tags(audio.tags, meta)
        except Exception:
            pass

    @classmethod
    def _read_ogg(cls, path_obj: Path, meta: AudioMetadata) -> None:
        try:
            audio = OggVorbis(str(path_obj))
            cls._read_flac(path_obj, meta)  # Vorbis comments schema is identical
        except Exception:
            pass

    # ================= WRITING / SAVING TAGS =================

    @classmethod
    def write_metadata(cls, filepath: Union[str, Path], tags_to_write: Dict[str, Any]) -> bool:
        """
        Updates tags on the given file.
        `tags_to_write` keys can be:
        title, artist, album, album_artist, year, genre, track_num, total_tracks,
        bpm, musical_key, camelot_key, label, remixer, comment, energy_level
        """
        path_obj = Path(filepath)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Clear Windows read-only flag if set
        try:
            os.chmod(str(path_obj), 0o666)
        except Exception:
            pass

        ext = path_obj.suffix.lower()

        if ext == ".mp3":
            return cls._write_mp3(path_obj, tags_to_write)
        elif ext == ".flac":
            return cls._write_flac(path_obj, tags_to_write)
        elif ext in (".m4a", ".aac"):
            return cls._write_mp4(path_obj, tags_to_write)
        elif ext == ".wav":
            return cls._write_wav(path_obj, tags_to_write)
        elif ext in (".aif", ".aiff"):
            return cls._write_aiff(path_obj, tags_to_write)
        elif ext == ".ogg":
            return cls._write_ogg(path_obj, tags_to_write)
        return False

    @classmethod
    def _write_mp3(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        try:
            tags = ID3(str(path_obj))
        except ID3NoHeaderError:
            tags = ID3()

        if "title" in tags_dict:
            tags.setall("TIT2", [TIT2(encoding=3, text=[str(tags_dict["title"])])])
        if "artist" in tags_dict:
            tags.setall("TPE1", [TPE1(encoding=3, text=[str(tags_dict["artist"])])])
        if "album" in tags_dict:
            tags.setall("TALB", [TALB(encoding=3, text=[str(tags_dict["album"])])])
        if "album_artist" in tags_dict:
            tags.setall("TPE2", [TPE2(encoding=3, text=[str(tags_dict["album_artist"])])])
        if "genre" in tags_dict:
            tags.setall("TCON", [TCON(encoding=3, text=[str(tags_dict["genre"])])])
        if "year" in tags_dict and tags_dict["year"]:
            yr_str = str(tags_dict["year"])
            tags.setall("TDRC", [TDRC(encoding=3, text=[yr_str])])
            tags.setall("TYER", [TYER(encoding=3, text=[yr_str])])
        if "track_num" in tags_dict:
            tr_str = str(tags_dict["track_num"])
            if tags_dict.get("total_tracks"):
                tr_str += f"/{tags_dict['total_tracks']}"
            tags.setall("TRCK", [TRCK(encoding=3, text=[tr_str])])
        if "bpm" in tags_dict and tags_dict["bpm"] is not None:
            bpm_val = tags_dict["bpm"]
            tags.setall("TBPM", [TBPM(encoding=3, text=[f"{bpm_val:.1f}" if isinstance(bpm_val, float) else str(bpm_val)])])
        if "musical_key" in tags_dict:
            tags.setall("TKEY", [TKEY(encoding=3, text=[str(tags_dict["musical_key"])])])
        if "camelot_key" in tags_dict:
            tags.delall("TXXX:INITIALKEY")
            tags.add(TXXX(encoding=3, desc="INITIALKEY", text=[str(tags_dict["camelot_key"])]))
        if "remixer" in tags_dict:
            tags.setall("TPE4", [TPE4(encoding=3, text=[str(tags_dict["remixer"])])])
        if "label" in tags_dict:
            tags.setall("TPUB", [TPUB(encoding=3, text=[str(tags_dict["label"])])])
        if "energy_level" in tags_dict and tags_dict["energy_level"] is not None:
            tags.delall("TXXX:EnergyLevel")
            tags.add(TXXX(encoding=3, desc="EnergyLevel", text=[str(tags_dict["energy_level"])]))
        if "comment" in tags_dict:
            tags.setall("COMM", [COMM(encoding=3, lang="eng", desc="", text=[str(tags_dict["comment"])])])

        tags.save(str(path_obj), v2_version=3)
        return True

    @classmethod
    def _write_flac(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        audio = FLAC(str(path_obj))

        mapping = {
            "title": "TITLE",
            "artist": "ARTIST",
            "album": "ALBUM",
            "album_artist": "ALBUMARTIST",
            "genre": "GENRE",
            "year": "DATE",
            "track_num": "TRACKNUMBER",
            "total_tracks": "TRACKTOTAL",
            "bpm": "BPM",
            "musical_key": "KEY",
            "camelot_key": "INITIALKEY",
            "remixer": "REMIXER",
            "label": "LABEL",
            "energy_level": "ENERGYLEVEL",
            "comment": "COMMENT",
        }

        for k, v in tags_dict.items():
            flac_key = mapping.get(k)
            if flac_key and v is not None:
                audio[flac_key] = [str(v)]

        audio.save()
        return True

    @classmethod
    def _write_mp4(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        audio = MP4(str(path_obj))

        if "title" in tags_dict:
            audio["\xa9nam"] = [str(tags_dict["title"])]
        if "artist" in tags_dict:
            audio["\xa9ART"] = [str(tags_dict["artist"])]
        if "album" in tags_dict:
            audio["\xa9alb"] = [str(tags_dict["album"])]
        if "album_artist" in tags_dict:
            audio["aART"] = [str(tags_dict["album_artist"])]
        if "genre" in tags_dict:
            audio["\xa9gen"] = [str(tags_dict["genre"])]
        if "year" in tags_dict and tags_dict["year"]:
            audio["\xa9day"] = [str(tags_dict["year"])]
        if "track_num" in tags_dict:
            tr_num = int(tags_dict["track_num"])
            tr_tot = int(tags_dict.get("total_tracks") or 0)
            audio["trkn"] = [(tr_num, tr_tot)]
        if "bpm" in tags_dict and tags_dict["bpm"] is not None:
            audio["tmpo"] = [int(round(float(tags_dict["bpm"])))]
        if "comment" in tags_dict:
            audio["\xa9cmt"] = [str(tags_dict["comment"])]

        # Custom iTunes frames
        if "camelot_key" in tags_dict:
            audio["----:com.apple.iTunes:INITIALKEY"] = [str(tags_dict["camelot_key"]).encode("utf-8")]
        if "musical_key" in tags_dict:
            audio["----:com.apple.iTunes:KEY"] = [str(tags_dict["musical_key"]).encode("utf-8")]
        if "remixer" in tags_dict:
            audio["----:com.apple.iTunes:REMIXER"] = [str(tags_dict["remixer"]).encode("utf-8")]
        if "label" in tags_dict:
            audio["----:com.apple.iTunes:LABEL"] = [str(tags_dict["label"]).encode("utf-8")]
        if "energy_level" in tags_dict and tags_dict["energy_level"] is not None:
            audio["----:com.apple.iTunes:ENERGYLEVEL"] = [str(tags_dict["energy_level"]).encode("utf-8")]

        audio.save()
        return True

    @classmethod
    def _write_wav(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        audio = WAVE(str(path_obj))
        if audio.tags is None:
            audio.add_tags()
        # WAV with ID3 chunk uses ID3 tags
        cls._write_id3_to_mutagen_object(audio.tags, tags_dict)
        audio.save()
        return True

    @classmethod
    def _write_aiff(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        audio = AIFF(str(path_obj))
        if audio.tags is None:
            audio.add_tags()
        cls._write_id3_to_mutagen_object(audio.tags, tags_dict)
        audio.save()
        return True

    @classmethod
    def _write_ogg(cls, path_obj: Path, tags_dict: Dict[str, Any]) -> bool:
        return cls._write_flac(path_obj, tags_dict)

    @classmethod
    def _write_id3_to_mutagen_object(cls, tags: ID3, tags_dict: Dict[str, Any]) -> None:
        if "title" in tags_dict:
            tags.setall("TIT2", [TIT2(encoding=3, text=[str(tags_dict["title"])])])
        if "artist" in tags_dict:
            tags.setall("TPE1", [TPE1(encoding=3, text=[str(tags_dict["artist"])])])
        if "album" in tags_dict:
            tags.setall("TALB", [TALB(encoding=3, text=[str(tags_dict["album"])])])
        if "album_artist" in tags_dict:
            tags.setall("TPE2", [TPE2(encoding=3, text=[str(tags_dict["album_artist"])])])
        if "genre" in tags_dict:
            tags.setall("TCON", [TCON(encoding=3, text=[str(tags_dict["genre"])])])
        if "year" in tags_dict and tags_dict["year"]:
            yr_str = str(tags_dict["year"])
            tags.setall("TDRC", [TDRC(encoding=3, text=[yr_str])])
        if "track_num" in tags_dict:
            tr_str = str(tags_dict["track_num"])
            if tags_dict.get("total_tracks"):
                tr_str += f"/{tags_dict['total_tracks']}"
            tags.setall("TRCK", [TRCK(encoding=3, text=[tr_str])])
        if "bpm" in tags_dict and tags_dict["bpm"] is not None:
            tags.setall("TBPM", [TBPM(encoding=3, text=[f"{float(tags_dict['bpm']):.1f}"])])
        if "musical_key" in tags_dict:
            tags.setall("TKEY", [TKEY(encoding=3, text=[str(tags_dict["musical_key"])])])
        if "camelot_key" in tags_dict:
            tags.delall("TXXX:INITIALKEY")
            tags.add(TXXX(encoding=3, desc="INITIALKEY", text=[str(tags_dict["camelot_key"])]))
        if "remixer" in tags_dict:
            tags.setall("TPE4", [TPE4(encoding=3, text=[str(tags_dict["remixer"])])])
        if "label" in tags_dict:
            tags.setall("TPUB", [TPUB(encoding=3, text=[str(tags_dict["label"])])])
        if "energy_level" in tags_dict and tags_dict["energy_level"] is not None:
            tags.delall("TXXX:EnergyLevel")
            tags.add(TXXX(encoding=3, desc="EnergyLevel", text=[str(tags_dict["energy_level"])]))
        if "comment" in tags_dict:
            tags.setall("COMM", [COMM(encoding=3, lang="eng", desc="", text=[str(tags_dict["comment"])])])

    # ================= ARTWORK ENGINE =================

    @classmethod
    def get_artwork(cls, filepath: Union[str, Path]) -> Optional[CoverArt]:
        """Extracts embedded cover artwork from audio file."""
        path_obj = Path(filepath)
        ext = path_obj.suffix.lower()

        try:
            if ext in (".mp3", ".wav", ".aif", ".aiff"):
                tags = ID3(str(path_obj))
                for frame in tags.values():
                    if isinstance(frame, APIC):
                        return CoverArt(
                            data=frame.data,
                            mime_type=frame.mime,
                            description=frame.desc,
                            pic_type=frame.type,
                        )
            elif ext in (".flac", ".ogg"):
                audio = FLAC(str(path_obj)) if ext == ".flac" else OggVorbis(str(path_obj))
                if getattr(audio, "pictures", None):
                    pic = audio.pictures[0]
                    return CoverArt(
                        data=pic.data,
                        mime_type=pic.mime,
                        description=pic.desc,
                        pic_type=pic.type,
                    )
            elif ext in (".m4a", ".aac"):
                audio = MP4(str(path_obj))
                if "covr" in audio and audio["covr"]:
                    cover = audio["covr"][0]
                    mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
                    return CoverArt(data=bytes(cover), mime_type=mime)
        except Exception:
            pass

        # Check local folder for cover.jpg / folder.jpg / front.jpg
        parent = path_obj.parent
        for candidate_name in ("cover.jpg", "folder.jpg", "front.jpg", "cover.png", "folder.png"):
            cand = parent / candidate_name
            if cand.exists():
                try:
                    mime = "image/png" if cand.suffix.lower() == ".png" else "image/jpeg"
                    return CoverArt(data=cand.read_bytes(), mime_type=mime, description="Local folder artwork")
                except Exception:
                    pass

        return None

    @classmethod
    def set_artwork(
        cls,
        filepath: Union[str, Path],
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        description: str = "Front Cover",
        write_folder_copy: bool = False,
        folder_filename: str = "cover.jpg",
    ) -> bool:
        """Embeds cover artwork into audio file and optionally writes local folder copy.

        Args:
            filepath (Union[str, Path]): Target audio file path.
            image_bytes (bytes): Binary image data.
            mime_type (str): Image MIME type ('image/jpeg' or 'image/png').
            description (str): Frame description.
            write_folder_copy (bool): If True, also writes cover.jpg in the track folder.
            folder_filename (str): Name for local image copy (default: 'cover.jpg').

        Returns:
            bool: True on success, False on error.
        """
        path_obj = Path(filepath)
        ext = path_obj.suffix.lower()
        success = False

        try:
            if ext in (".mp3", ".wav", ".aif", ".aiff"):
                try:
                    tags = ID3(str(path_obj))
                except ID3NoHeaderError:
                    tags = ID3()
                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=3,
                        mime=mime_type,
                        type=PictureType.COVER_FRONT,
                        desc=description,
                        data=image_bytes,
                    )
                )
                tags.save(str(path_obj), v2_version=3)
                success = True
            elif ext == ".flac":
                audio = FLAC(str(path_obj))
                pic = Picture()
                pic.data = image_bytes
                pic.type = PictureType.COVER_FRONT
                pic.mime = mime_type
                pic.desc = description
                audio.clear_pictures()
                audio.add_picture(pic)
                audio.save()
                success = True
            elif ext in (".m4a", ".aac"):
                audio = MP4(str(path_obj))
                fmt = MP4Cover.FORMAT_PNG if "png" in mime_type.lower() else MP4Cover.FORMAT_JPEG
                audio["covr"] = [MP4Cover(image_bytes, imageformat=fmt)]
                audio.save()
                success = True
        except Exception:
            success = False

        if success and write_folder_copy:
            try:
                (path_obj.parent / folder_filename).write_bytes(image_bytes)
            except Exception:
                pass

        return success

    @classmethod
    def remove_artwork(cls, filepath: Union[str, Path]) -> bool:
        """Removes embedded cover artwork from audio file."""
        path_obj = Path(filepath)
        ext = path_obj.suffix.lower()

        try:
            if ext in (".mp3", ".wav", ".aif", ".aiff"):
                tags = ID3(str(path_obj))
                tags.delall("APIC")
                tags.save(str(path_obj), v2_version=3)
                return True
            elif ext == ".flac":
                audio = FLAC(str(path_obj))
                audio.clear_pictures()
                audio.save()
                return True
            elif ext in (".m4a", ".aac"):
                audio = MP4(str(path_obj))
                if "covr" in audio:
                    del audio["covr"]
                    audio.save()
                    return True
        except Exception:
            pass
        return False
