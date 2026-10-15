"""MoviePy video export parameter selection and fallback handling."""

import os
from pathlib import Path


def export_video(
    final_video,
    output_path: str,
    *,
    fps: int = 15,
    video_codec: str = "h264",
    bitrate_mode: str = "auto",
    quality_level: int = 65,
    fade_in_seconds: float = 0.0,
    ending_fade_seconds: float = 0.0,
) -> None:
    """Export a MoviePy video with hardware-first encoding and software fallback.

    The video is encoded beside the destination and moved into place only when encoding
    finishes, so an interrupted export never replaces the previous video with a truncated one.
    """
    destination = Path(output_path)
    temporary_output = destination.with_name(f".{destination.stem}.tmp{destination.suffix or '.mp4'}")
    temporary_audio = destination.with_name(f".{destination.stem}.tmp_audio.mp4")
    # A killed export leaves these behind; MoviePy would otherwise drop its audio in the working folder.
    for leftover in (temporary_output, temporary_audio):
        leftover.unlink(missing_ok=True)
    try:
        _write_video(
            final_video,
            str(temporary_output),
            str(temporary_audio),
            fps=fps,
            video_codec=video_codec,
            bitrate_mode=bitrate_mode,
            quality_level=quality_level,
            fade_in_seconds=fade_in_seconds,
            ending_fade_seconds=ending_fade_seconds,
        )
        if not temporary_output.is_file():
            raise RuntimeError("视频编码完成但未生成输出文件")
        os.replace(temporary_output, destination)
    finally:
        temporary_output.unlink(missing_ok=True)
        temporary_audio.unlink(missing_ok=True)


def _write_video(
    final_video,
    output_path: str,
    temp_audiofile: str,
    *,
    fps: int,
    video_codec: str,
    bitrate_mode: str,
    quality_level: int,
    fade_in_seconds: float,
    ending_fade_seconds: float,
) -> None:
    moviepy_logger = "bar"
    vf_filter = _build_fade_filter(final_video, fade_in_seconds, ending_fade_seconds)

    try:
        codec_name = "h264_videotoolbox"
        bitrate_param = None
        ffmpeg_extra_params = []

        video_codec = (video_codec or "h264").lower()
        bitrate_mode = (bitrate_mode or "auto").lower()

        if video_codec == "hevc":
            codec_name = "hevc_videotoolbox"
            ffmpeg_extra_params.extend(["-tag:v", "hvc1"])
        else:
            codec_name = "h264_videotoolbox"

        audio_bitrate = "256k"

        ffmpeg_extra_params.extend(["-nostdin", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
        if vf_filter:
            ffmpeg_extra_params.extend(["-vf", vf_filter])

        width = int(getattr(final_video, "w", 0) or 0)
        height = int(getattr(final_video, "h", 0) or 0)

        if video_codec != "hevc":
            ffmpeg_extra_params.extend(_h264_profile_level_params(width, height))

        if bitrate_mode == "quality":
            ffmpeg_extra_params.extend(["-q:v", str(quality_level)])
            bitrate_param = None
            print(f"🎞️ 使用硬件编码 ({codec_name}) 导出视频 [质量优先: {quality_level}]...")
        else:
            bitrate_val = "8M" if fps == 30 else "3M"
            bufsize = "12M" if fps == 30 else "6M"
            bitrate_param = bitrate_val
            ffmpeg_extra_params.extend(["-maxrate", bitrate_val, "-bufsize", bufsize])
            print(f"🎞️ 使用硬件编码 ({codec_name}) 导出视频 [固定码率: {bitrate_val}]...")

        final_video.write_videofile(
            output_path,
            fps=fps,
            codec=codec_name,
            audio_codec="aac",
            audio_bitrate=audio_bitrate,
            bitrate=bitrate_param,
            ffmpeg_params=ffmpeg_extra_params,
            threads=os.cpu_count() or 4,
            temp_audiofile=temp_audiofile,
            logger=moviepy_logger,
        )
    except Exception as exc:
        print(f"⚠️ 硬件编码不可用或失败，回退到软件编码: {exc}")
        audio_bitrate = "256k"
        crf = "20" if fps == 30 else "25"
        preset = "medium"
        print("🎞️ 改用软件编码 (libx264) 导出视频…")
        final_video.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate=audio_bitrate,
            preset=preset,
            threads=os.cpu_count() or 4,
            ffmpeg_params=(
                ["-nostdin", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
                + (["-vf", vf_filter] if vf_filter else [])
            ),
            temp_audiofile=temp_audiofile,
            logger=moviepy_logger,
        )


def _build_fade_filter(final_video, fade_in_seconds: float, ending_fade_seconds: float) -> str | None:
    total_duration = float(getattr(final_video, "duration", 0.0) or 0.0)
    vf_parts = []

    if fade_in_seconds > 1e-3:
        vf_parts.append(f"fade=t=in:st=0:d={fade_in_seconds}")
    if ending_fade_seconds > 1e-3 and total_duration > 0.0:
        fade_out_start = max(0.0, total_duration - ending_fade_seconds)
        vf_parts.append(f"fade=t=out:st={fade_out_start}:d={ending_fade_seconds}")

    return ",".join(vf_parts) if vf_parts else None


def _h264_profile_level_params(width: int, height: int) -> list[str]:
    if width and height:
        if width > 3840 or height > 2160:
            return ["-profile:v", "high", "-level", "5.2"]
        if width > 2560 or height > 1440:
            return ["-profile:v", "high", "-level", "5.2"]
        if width > 1920 or height > 1080:
            return ["-profile:v", "high", "-level", "5.1"]
        if width > 1280 or height > 720:
            return ["-profile:v", "main", "-level", "4.1"]
        return ["-profile:v", "main", "-level", "3.1"]

    return ["-profile:v", "main"]
