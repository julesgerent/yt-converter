import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
import flet as ft
import imageio_ffmpeg

APP_VERSION = "v1.0.0"


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "--:--"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def parse_timecode(raw: str) -> float | None:
    """Convertit 'SS', 'MM:SS' ou 'HH:MM:SS' en secondes."""
    text = raw.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Format de timecode invalide : {text}")
    total = 0.0
    for part in parts:
        val = float(part)
        if val < 0:
            raise ValueError("Le timecode ne peut pas être négatif.")
        total = total * 60 + val
    return total


def parse_version_tuple(tag: str) -> tuple[int, ...]:
    cleaned = tag.strip().lstrip("vV")
    nums = []
    for part in cleaned.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums)



def main(page: ft.Page):
    page.title = "yt-converter"
    page.window.width = 1000
    page.window.height = 720
    page.window.min_width = 750
    page.window.min_height = 580
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0F1115"
    page.padding = 28

    default_downloads = str(Path.home() / "Downloads")
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()


    latest_release_url = f"https://github.com/julesgerent/yt-converter/releases/latest"

    update_label = ft.Text("", size=13, weight=ft.FontWeight.W_500, expand=True)
    update_btn = ft.Button(
        "Télécharger",
        icon=ft.Icons.OPEN_IN_NEW,
        height=34,
        on_click=lambda _: webbrowser.open(latest_release_url),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            bgcolor="#2563EB",
            color="#FFFFFF",
        ),
    )
    update_banner = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SYSTEM_UPDATE_ALT, color="#60A5FA", size=20),
                update_label,
                update_btn,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=12,
        border_radius=10,
        bgcolor="#172554",
        border=ft.Border.all(1, "#1D4ED8"),
        visible=False,
    )


    url_input = ft.TextField(
        label="Lien YouTube",
        hint_text="https://www.youtube.com/watch?v=...",
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        focused_border_color="#4F8CFF",
        expand=True,
    )

    format_dropdown = ft.Dropdown(
        label="Format",
        value="mp4",
        width=165,
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        options=[
            ft.dropdown.Option("mp4", "MP4 (Vidéo)"),
            ft.dropdown.Option("mov", "MOV (Vidéo)"),
            ft.dropdown.Option("mp3", "MP3 (Audio)"),
            ft.dropdown.Option("wav", "WAV (Audio Lossless)"),
        ],
    )

    quality_dropdown = ft.Dropdown(
        label="Qualité",
        value="best",
        width=230,
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        options=[
            ft.dropdown.Option("best", "Meilleure disponible"),
            ft.dropdown.Option("1080", "1080p Full HD"),
            ft.dropdown.Option("720", "720p HD"),
        ],
    )

    start_time_input = ft.TextField(
        label="Début*",
        hint_text="00:30",
        width=145,
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        focused_border_color="#4F8CFF",
    )

    end_time_input = ft.TextField(
        label="Fin*",
        hint_text="01:45",
        width=145,
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        focused_border_color="#4F8CFF",
    )

    output_dir_input = ft.TextField(
        label="Dossier de destination",
        value=default_downloads,
        border_radius=10,
        bgcolor="#181B20",
        border_color="#2A2F3A",
        expand=True,
    )

    thumb_image = ft.Image(
        src="",
        width=160,
        height=90,
        fit=ft.BoxFit.COVER,
        border_radius=8,
        visible=False,
    )
    video_title = ft.Text(
        "Collez le lien de la vidéo à télécharger ci-dessus",
        size=15,
        weight=ft.FontWeight.W_600,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    video_meta = ft.Text(
        "puis cliquez sur 'Télécharger & convertir'.",
        size=12,
        color="#8E96A4",
    )

    preview_card = ft.Container(
        content=ft.Row(
            controls=[
                thumb_image,
                ft.Column(
                    controls=[video_title, video_meta],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=14,
        border_radius=12,
        bgcolor="#16191F",
        border=ft.Border.all(1, "#242933"),
    )

    progress_bar = ft.ProgressBar(
        value=0,
        color="#4F8CFF",
        bgcolor="#222732",
        height=8,
        border_radius=4,
    )
    status_text = ft.Text("Prêt", size=13, color="#A0A8B8")

    def on_format_change(e):
        fmt = format_dropdown.value
        if fmt in ("mp4", "mov"):
            quality_dropdown.options = [
                ft.dropdown.Option("best", "Meilleure disponible"),
                ft.dropdown.Option("1080", "1080p Full HD"),
                ft.dropdown.Option("720", "720p HD"),
            ]
            quality_dropdown.value = "best"
            quality_dropdown.disabled = False
        elif fmt == "mp3":
            quality_dropdown.options = [
                ft.dropdown.Option("320", "320 kbps (Haute qualité)"),
                ft.dropdown.Option("192", "192 kbps (Standard)"),
            ]
            quality_dropdown.value = "320"
            quality_dropdown.disabled = False
        else:
            quality_dropdown.options = [
                ft.dropdown.Option("pcm", "PCM non compressé"),
            ]
            quality_dropdown.value = "pcm"
            quality_dropdown.disabled = True
        page.update()

    format_dropdown.on_select = on_format_change

    async def pick_folder(e):
        selected_path = await ft.FilePicker().get_directory_path(
            dialog_title="Choisir le dossier de sortie"
        )
        if selected_path:
            output_dir_input.value = selected_path
            page.update()

    def set_controls_disabled(state: bool):
        url_input.disabled = state
        format_dropdown.disabled = state
        if format_dropdown.value != "wav":
            quality_dropdown.disabled = state
        start_time_input.disabled = state
        end_time_input.disabled = state
        output_dir_input.disabled = state
        analyze_btn.disabled = state
        download_btn.disabled = state
        folder_btn.disabled = state
        page.update()

    async def check_updates():
        nonlocal latest_release_url

        if getattr(sys, "frozen", False):
            import yt_dlp

            ytdlp_ver = yt_dlp.version.__version__
            api_url = f"https://api.github.com/repos/julesgerent/yt-converter/releases/latest"

            def _fetch_latest_release():
                req = urllib.request.Request(
                    api_url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "yt-converter-app",
                    },
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            try:
                data = await asyncio.to_thread(_fetch_latest_release)
                remote_tag = data.get("tag_name", "")
                html_url = data.get("html_url")
                if html_url:
                    latest_release_url = html_url

                if remote_tag and parse_version_tuple(remote_tag) > parse_version_tuple(
                    APP_VERSION
                ):
                    update_label.value = (
                        f"Nouvelle version {remote_tag} disponible (actuelle : {APP_VERSION})"
                    )
                    update_banner.visible = True
                    status_text.value = f"Prêt - Mise à jour {remote_tag} disponible"
                    status_text.color = "#60A5FA"
                else:
                    status_text.value = (
                        f"Prêt - App à jour ({APP_VERSION}) - yt-dlp {ytdlp_ver}"
                    )
                    status_text.color = "#4ADE80"
            except (urllib.error.URLError, Exception):
                status_text.value = f"Prêt - {APP_VERSION} - yt-dlp {ytdlp_ver}"
                status_text.color = "#A0A8B8"

            page.update()
            return

        uv_bin = shutil.which("uv")
        if not uv_bin:
            status_text.value = "Prêt (uv introuvable pour la MAJ auto)"
            page.update()
            return

        set_controls_disabled(True)
        progress_bar.value = None
        status_text.value = "Vérification des mises à jour de yt-dlp..."
        status_text.color = "#A0A8B8"
        page.update()

        project_dir = Path(__file__).resolve().parent

        def _run_update():
            return subprocess.run(
                [uv_bin, "sync", "--upgrade-package", "yt-dlp"],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )

        try:
            result = await asyncio.to_thread(_run_update)
            import yt_dlp

            version = yt_dlp.version.__version__
            if result.returncode == 0:
                status_text.value = f"Prêt - yt-dlp à jour ({version})"
                status_text.color = "#4ADE80"
            else:
                status_text.value = f"Prêt - MAJ ignorée ({version})"
                status_text.color = "#A0A8B8"
        except Exception:
            status_text.value = "Prêt (mode hors ligne)"
            status_text.color = "#A0A8B8"
        finally:
            progress_bar.value = 0
            set_controls_disabled(False)

    async def analyze_video(e):
        url = (url_input.value or "").strip()
        if not url:
            status_text.value = "Erreur : URL YouTube invalide."
            status_text.color = "#FF6B6B"
            page.update()
            return

        set_controls_disabled(True)
        status_text.value = "Récupération des métadonnées..."
        status_text.color = "#A0A8B8"
        progress_bar.value = None
        page.update()

        def _extract_info():
            import yt_dlp

            opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.to_thread(_extract_info)
            video_title.value = info.get("title", "Titre inconnu")
            uploader = info.get("uploader", "Chaîne inconnue")
            duration = format_duration(info.get("duration"))
            video_meta.value = f"{uploader}  -  Durée : {duration}"

            thumb = info.get("thumbnail")
            if thumb:
                thumb_image.src = thumb
                thumb_image.visible = True

            status_text.value = "Vidéo prête à être convertie."
            status_text.color = "#4ADE80"
        except Exception as ex:
            status_text.value = f"Échec de l'analyse : {ex}"
            status_text.color = "#FF6B6B"
        finally:
            progress_bar.value = 0
            set_controls_disabled(False)

    async def start_download(e):
        url = (url_input.value or "").strip()
        out_dir = Path((output_dir_input.value or default_downloads).strip())
        fmt = format_dropdown.value
        quality = quality_dropdown.value

        if not url:
            status_text.value = "Erreur : collez un lien YouTube avant de lancer."
            status_text.color = "#FF6B6B"
            page.update()
            return

        try:
            start_sec = parse_timecode(start_time_input.value or "")
            end_sec = parse_timecode(end_time_input.value or "")
        except ValueError as err:
            status_text.value = f"Erreur de timecode : {err}"
            status_text.color = "#FF6B6B"
            page.update()
            return

        has_clip = start_sec is not None or end_sec is not None
        if has_clip:
            clip_start = start_sec if start_sec is not None else 0.0
            clip_end = end_sec if end_sec is not None else float("inf")
            if clip_end <= clip_start:
                status_text.value = "Erreur : le timecode de fin doit être après celui de début."
                status_text.color = "#FF6B6B"
                page.update()
                return


        out_dir.mkdir(parents=True, exist_ok=True)
        set_controls_disabled(True)
        progress_bar.value = 0
        status_text.value = "Initialisation du téléchargement..."
        status_text.color = "#A0A8B8"
        page.update()

        def progress_hook(d: dict):
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    ratio = min(downloaded / total, 1.0)
                    progress_bar.value = ratio
                    speed = d.get("_speed_str", "").strip()
                    eta = d.get("_eta_str", "").strip()
                    status_text.value = (
                        f"Téléchargement : {ratio * 100:.1f}%  ({speed} - ETA {eta})"
                    )
                else:
                    progress_bar.value = None
                    status_text.value = "Téléchargement de l'extrait en cours..."

                page.update()
            elif status == "finished":
                progress_bar.value = None
                status_text.value = "Conversion / assemblage FFmpeg en cours..."
                page.update()

        def _run_ytdlp():
            import yt_dlp
            
            from yt_dlp.utils import download_range_func

            filename_tpl = (
                "%(title)s [extrait].%(ext)s" if has_clip else "%(title)s.%(ext)s"
            )


            ydl_opts: dict = {
                "ffmpeg_location": ffmpeg_path,
                "outtmpl": str(out_dir / filename_tpl),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [progress_hook],
            }

            if has_clip:
                ydl_opts["download_ranges"] = download_range_func(
                    None, [(clip_start, clip_end)]
                )
                ydl_opts["force_keyframes_at_cuts"] = True

            if fmt == "mp4":
                if quality == "1080":
                    ydl_opts["format"] = (
                        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
                        "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
                    )
                elif quality == "720":
                    ydl_opts["format"] = (
                        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                        "bestvideo[height<=720]+bestaudio/best[height<=720]"
                    )
                else:
                    ydl_opts["format"] = (
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                    )
                ydl_opts["merge_output_format"] = "mp4"

            elif fmt == "mov":
                if quality == "1080":
                    ydl_opts["format"] = (
                        "bestvideo[height<=1080][vcodec^=avc]+bestaudio[ext=m4a]/"
                        "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
                    )
                elif quality == "720":
                    ydl_opts["format"] = (
                        "bestvideo[height<=720][vcodec^=avc]+bestaudio[ext=m4a]/"
                        "bestvideo[height<=720]+bestaudio/best[height<=720]"
                    )
                else:
                    ydl_opts["format"] = (
                        "bestvideo[vcodec^=avc]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                    )
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mov",
                    }
                ]

            elif fmt == "mp3":
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": quality,
                    }
                ]

            elif fmt == "wav":
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",
                    }
                ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info.get("title", "Fichier")

        try:
            title = await asyncio.to_thread(_run_ytdlp)
            progress_bar.value = 1.0
            suffix = " [extrait]" if has_clip else ""
            status_text.value = f"Terminé : « {title}{suffix}.{fmt} » enregistré." 
            status_text.color = "#4ADE80"
        except Exception as ex:
            progress_bar.value = 0
            status_text.value = f"Erreur : {ex}"
            status_text.color = "#FF6B6B"
        finally:
            set_controls_disabled(False)

    analyze_btn = ft.Button(
        "Recherche",
        icon=ft.Icons.SEARCH,
        on_click=analyze_video,
        height=48,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            bgcolor="#232834",
            color="#FFFFFF",
        ),
    )

    folder_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        tooltip="Choisir un dossier",
        on_click=pick_folder,
        icon_color="#A0A8B8",
    )

    download_btn = ft.Button(
        "Télécharger & convertir",
        icon=ft.Icons.DOWNLOAD,
        on_click=start_download,
        height=50,
        expand=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            bgcolor="#4F8CFF",
            color="#FFFFFF",
        ),
    )

    page.add(
        ft.Column(
            controls=[
                ft.Text(
                    "yt-converter",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=6),
                ft.Row(
                    controls=[url_input, analyze_btn],
                    spacing=10,
                ),
                preview_card,
                ft.Row(
                    controls=[format_dropdown, quality_dropdown],
                    spacing=12,
                ),
                ft.Row(
                    controls=[
                        start_time_input,
                        end_time_input,
                        ft.Text(
                            "* = optionnel, format HH:MM:SS ou MM:SS ou SS",
                            size=12,
                            color="#8E96A4",
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[output_dir_input, folder_btn],
                    spacing=8,
                ),
                ft.Container(height=4),
                ft.Row(controls=[download_btn]),
                ft.Container(height=4),
                progress_bar,
                status_text,
            ],
            spacing=12,
        )
    )

    page.run_task(check_updates)



if __name__ == "__main__":
    ft.run(main)