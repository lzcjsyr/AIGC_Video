"""
视频合成器 - 统一的视频合成处理模块（迁移至 core）
整合视频合成、字幕生成、音频混合等功能
"""

import os
import re
import math
from contextlib import suppress
import numpy as np
from typing import Callable, List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# MoviePy 2.x imports (no editor module)
from moviepy import (
    ImageClip,
    VideoClip,
    VideoFileClip,
    ColorClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    AudioFileClip,
    concatenate_audioclips,
)

from core.config import config
from core.domain.subtitles import (
    calculate_subtitle_durations,
    format_subtitle_display_text,
    split_text_for_subtitle,
)
from core.media_gateway import (
    adjust_audio_speed,
    export_video,
    normalize_bgm_loudness,
)
from core.infra.media.three_by_four import PanelOptions, derive_output_path, export_three_by_four_video
from core.shared import logger, handle_video_operation

# ==================== 系统常量 ====================
# 支持的视频格式（系统技术限制，非用户配置项）
SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".m4v"]


def three_by_four_panel_options() -> PanelOptions:
    """当前配置中的3:4贴片样式。"""
    return PanelOptions.from_mapping({
        "theme": getattr(config, "THREE_BY_FOUR_THEME", "ink"),
        "top_share": getattr(config, "THREE_BY_FOUR_TOP_SHARE", 0.5),
        "top_content": getattr(config, "THREE_BY_FOUR_TOP_CONTENT", "title_subtitle"),
        "title_text": getattr(config, "THREE_BY_FOUR_TITLE_TEXT", ""),
        "subtitle_text": getattr(config, "THREE_BY_FOUR_SUBTITLE_TEXT", ""),
        "bottom_content": getattr(config, "THREE_BY_FOUR_BOTTOM_CONTENT", "quote"),
        "bottom_text": getattr(config, "THREE_BY_FOUR_BOTTOM_TEXT", ""),
        "accent_color": getattr(config, "THREE_BY_FOUR_ACCENT_COLOR", "#C45A47"),
    })


class VideoComposer:
    """统一的视频合成器"""
    
    def compose_video(self, image_paths: List[str], audio_paths: List[str], output_path: str,
                     script_data: Dict[str, Any] = None, enable_subtitles: bool = False,
                     bgm_audio_path: Optional[str] = None, bgm_volume: float = 0.15,
                     narration_volume: float = 1.0,
                     opening_image_path: Optional[str] = None,
                     opening_narration_audio_path: Optional[str] = None,
                     image_size: str = "1280x720",
                     opening_quote: bool = True,
                     project_root: Optional[str] = None) -> str:
        """
        合成最终视频

        Args:
            image_paths: 图像文件路径列表
            audio_paths: 音频文件路径列表
            output_path: 输出视频路径
            script_data: 脚本数据，用于生成字幕
            enable_subtitles: 是否启用字幕
            bgm_audio_path: 背景音乐路径
            bgm_volume: 背景音乐音量
            narration_volume: 口播音量
            opening_image_path: 开场素材路径（图片或视频）
            opening_narration_audio_path: 开场口播音频路径
            image_size: 目标图像尺寸，如"1280x720"
            opening_quote: 是否包含开场金句
            project_root: 项目根目录（用于存放响度标准化临时文件）

        Returns:
            str: 输出视频路径
        """
        video_clips: List = []
        audio_clips: List = []
        temp_audio_paths: List[str] = []
        final_video = None

        try:
            if len(image_paths) != len(audio_paths):
                raise ValueError("图像文件数量与音频文件数量不匹配")
            
            # 解析目标尺寸
            target_size = self._parse_image_size(image_size)
            print(f"目标视频尺寸: {target_size[0]}x{target_size[1]}")
            image_zoom_in_ratio = self._resolve_image_zoom_in_ratio()
            if image_zoom_in_ratio > 1.0:
                print(f"🔍 静态图片 Zoom In: 1.00x → {image_zoom_in_ratio:.2f}x（最后一张除外）")

            # 检测是否包含视频素材，决定输出帧率
            has_videos = self._has_video_materials(image_paths)
            configured_output_fps = int(getattr(config, "VIDEO_OUTPUT_FPS", 0) or 0)
            target_fps = configured_output_fps if configured_output_fps > 0 else (30 if has_videos else 15)
            print(f"检测到{'视频' if has_videos else '图片'}素材，使用{target_fps}fps输出")

            narration_speed_factor = float(getattr(config, "NARRATION_SPEED_FACTOR", 1.0) or 1.0)
            if narration_speed_factor <= 0:
                raise ValueError("口播变速系数必须大于0")
            if abs(narration_speed_factor - 1.0) > 1e-3:
                print(f"🎙️ 口播变速系数: {narration_speed_factor:.3f}")
                print("🎧 使用 FFmpeg atempo 保持音高进行口播变速")

            processed_opening_audio_path = None
            if opening_narration_audio_path and os.path.exists(opening_narration_audio_path):
                processed_opening_audio_path = self._ensure_speed_adjusted_audio(
                    opening_narration_audio_path,
                    narration_speed_factor,
                    temp_audio_paths
                )

            # 创建开场片段
            opening_seconds = self._create_opening_segment(
                opening_image_path,
                processed_opening_audio_path,
                video_clips,
                target_size,
                opening_quote,
                image_zoom_in_ratio,
            )

            # 创建主要视频片段
            self._create_main_segments(
                image_paths,
                audio_paths,
                video_clips,
                audio_clips,
                target_size,
                narration_speed_factor,
                temp_audio_paths,
                image_zoom_in_ratio,
            )
            
            # 连接所有视频片段
            print("正在合成最终视频...")
            if config.ENABLE_TRANSITIONS and config.TRANSITION_STYLE != "cut":
                # 使用过渡效果连接视频片段
                final_video = self._concatenate_with_transitions(
                    video_clips,
                    config.TRANSITION_STYLE,
                    config.TRANSITION_DURATION
                )
            else:
                # 简单拼接（无过渡效果）
                final_video = concatenate_videoclips(video_clips, method="chain")
            
            # 添加字幕
            final_video = self._add_subtitles(final_video, script_data, enable_subtitles, 
                                            audio_clips, opening_seconds)
            
            # 调整口播音量
            final_video = self._adjust_narration_volume(final_video, narration_volume)
            
            # 添加视觉效果
            final_video = self._add_visual_effects(final_video, image_paths, target_size)

            # 添加背景音乐
            final_video = self._add_background_music(
                final_video, bgm_audio_path, bgm_volume, project_root,
                temp_audio_paths=temp_audio_paths, audio_clips=audio_clips
            )
            
            # 输出视频
            self._export_video(final_video, output_path, target_fps)

            # 基于已完成的横屏母版向外扩展画布；不重复合成动态画面和字幕。
            if getattr(config, "THREE_BY_FOUR_ENABLED", True):
                self.export_three_by_four(output_path, script_data)
            else:
                print("已关闭3:4贴片版，仅导出横屏母版")
            
            print(f"最终视频已保存: {output_path}")
            return output_path
            
        except Exception as e:
            raise ValueError(f"视频合成错误: {e}")
        finally:
            self._cleanup_resources(video_clips, audio_clips, final_video, temp_audio_paths)
    
    def export_three_by_four(self, master_path: str, script_data: Optional[Dict[str, Any]]) -> str:
        """从横屏母版生成3:4贴片版；贴片样式读取 three_by_four 配置。"""
        panel_font, panel_ttc_index = self.resolve_subtitle_font(
            getattr(config, "SUBTITLE_FONT_FAMILY", "auto"),
            int(getattr(config, "SUBTITLE_FONT_TTC_INDEX", 0) or 0),
        )
        three_by_four_path = derive_output_path(master_path)
        export_three_by_four_video(
            master_path,
            three_by_four_path,
            script_data,
            font_path=panel_font,
            font_ttc_index=panel_ttc_index,
            video_codec=getattr(config, "VIDEO_CODEC", "h264"),
            quality_level=int(getattr(config, "THREE_BY_FOUR_QUALITY_LEVEL", 86) or 86),
            panel=three_by_four_panel_options(),
        )
        print(f"3:4贴片版已保存: {three_by_four_path}")
        return str(three_by_four_path)

    @handle_video_operation("开场片段生成", critical=False, fallback_value=0.0)
    def _create_opening_segment(self, opening_image_path: Optional[str],
                              opening_narration_audio_path: Optional[str],
                              video_clips: List, target_size: Tuple[int, int],
                              opening_quote: bool = True,
                              image_zoom_in_ratio: float = 1.0) -> float:
        """创建开场片段"""
        opening_seconds = 0.0
        opening_voice_clip = None

        # 如果不包含开场金句，直接返回
        if not opening_quote:
            return opening_seconds

        # 计算开场时长
        if opening_narration_audio_path and os.path.exists(opening_narration_audio_path):
            opening_voice_clip = AudioFileClip(opening_narration_audio_path)
            opening_seconds = float(opening_voice_clip.duration)

        if opening_image_path and os.path.exists(opening_image_path) and opening_seconds > 1e-3:
            print("正在创建开场片段…")

            # 检测并处理视频或图片格式
            if self._is_video_file(opening_image_path):
                # 视频素材处理
                print(f"  使用视频素材: {os.path.basename(opening_image_path)}")
                opening_base = VideoFileClip(opening_image_path).without_audio()
                opening_base = self._resize_video(opening_base, target_size)

                # 调整时长到音频长度
                original_duration = opening_base.duration
                print(f"  开场视频时长: {original_duration:.2f}s，目标时长: {opening_seconds:.2f}s")
                opening_base = self._fit_opening_video_duration(
                    opening_base,
                    opening_seconds,
                    clip_label="开场视频",
                )
            else:
                print(f"  使用图片素材: {os.path.basename(opening_image_path)}")
                opening_base = self._create_image_material_clip(
                    opening_image_path,
                    opening_seconds,
                    target_size,
                    image_zoom_in_ratio,
                )
            
            # 绑定开场音频
            if opening_voice_clip is not None:
                opening_base = opening_base.with_audio(opening_voice_clip)

            video_clips.append(opening_base)

        return opening_seconds

    def _ensure_speed_adjusted_audio(self, audio_path: str, speed_factor: float,
                                     temp_audio_paths: List[str]) -> str:
        """使用FFmpeg执行变速并保持音高，返回处理后的音频路径"""
        return adjust_audio_speed(audio_path, speed_factor, temp_audio_paths)

    def _create_text_image_pil(self, text: str, font_size: int, font_path: str,
                               text_color: str, stroke_color: str, stroke_width: int,
                               ttc_index: int = 0, letter_spacing: int = 0) -> Image.Image:
        """
        使用 PIL 渲染文字到图片，完整保留 descender（下伸笔画）

        这个方法解决了 MoviePy TextClip 裁切行楷字体底部笔画的问题

        Args:
            text: 要渲染的文字
            font_size: 字体大小
            font_path: 字体文件路径
            text_color: 文字颜色
            stroke_color: 描边颜色
            stroke_width: 描边宽度

        Returns:
            PIL.Image.Image: 带透明背景的文字图片
        """
        try:
            # 加载字体
            font = ImageFont.truetype(font_path, font_size, index=ttc_index)

            # 使用临时图片测量文字边界框
            temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            letter_spacing = int(letter_spacing or 0)

            # 获取文字边界框 (left, top, right, bottom)
            # textbbox 会包含完整的 descender
            if letter_spacing <= 0 or len(text) <= 1:
                bbox = temp_draw.textbbox((0, 0), text, font=font, anchor='lt', stroke_width=stroke_width)
            else:
                cursor_x = 0.0
                bbox = None
                for idx, char in enumerate(text):
                    char_bbox = temp_draw.textbbox(
                        (cursor_x, 0),
                        char,
                        font=font,
                        anchor='ls',
                        stroke_width=stroke_width,
                    )
                    if bbox is None:
                        bbox = list(char_bbox)
                    else:
                        bbox[0] = min(bbox[0], char_bbox[0])
                        bbox[1] = min(bbox[1], char_bbox[1])
                        bbox[2] = max(bbox[2], char_bbox[2])
                        bbox[3] = max(bbox[3], char_bbox[3])

                    advance = temp_draw.textlength(char, font=font)
                    cursor_x += advance
                    if idx < len(text) - 1:
                        cursor_x += letter_spacing

                bbox = tuple(int(round(v)) for v in (bbox or (0, 0, 1, 1)))

            # 创建带透明背景的图片
            width = max(1, bbox[2] - bbox[0] + stroke_width * 2)
            height = max(1, bbox[3] - bbox[1] + stroke_width * 2)
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 计算绘制位置（考虑 bbox 的偏移）
            draw_x = -bbox[0] + stroke_width
            draw_y = -bbox[1] + stroke_width

            # 转换颜色
            if text_color == 'white':
                fill = (255, 255, 255, 255)
            else:
                fill = text_color

            if stroke_color == 'black':
                stroke = (0, 0, 0, 255)
            else:
                stroke = stroke_color

            # 绘制文字
            if letter_spacing <= 0 or len(text) <= 1:
                draw.text(
                    (draw_x, draw_y),
                    text,
                    font=font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke,
                    anchor='lt'
                )
            else:
                cursor_x = draw_x
                for idx, char in enumerate(text):
                    draw.text(
                        (cursor_x, draw_y),
                        char,
                        font=font,
                        fill=fill,
                        stroke_width=stroke_width,
                        stroke_fill=stroke,
                        anchor='ls'
                    )
                    advance = draw.textlength(char, font=font)
                    cursor_x += advance
                    if idx < len(text) - 1:
                        cursor_x += letter_spacing

            return img

        except Exception as e:
            logger.warning(f"PIL 文字渲染失败: {e}，将返回空图片")
            return Image.new('RGBA', (1, 1), (0, 0, 0, 0))

    def _fit_opening_video_duration(self, video_clip, target_duration: float, clip_label: str):
        """按音频时长调整开场视频：短了定格最后一帧，长了按策略压缩或裁剪。"""
        original_duration = float(getattr(video_clip, "duration", 0.0) or 0.0)
        target_duration = float(target_duration or 0.0)

        if target_duration <= 1e-3 or original_duration <= 1e-3:
            print(f"  {clip_label}时长异常，跳过时长对齐")
            return video_clip

        if abs(original_duration - target_duration) <= 1e-3:
            print(f"  {clip_label}时长匹配，无需调整")
            return video_clip

        if original_duration < target_duration:
            still_duration = target_duration - original_duration
            freeze_time = self._get_last_valid_frame_time(video_clip, original_duration)
            print(f"  {clip_label}较短，定格最后一帧补足 {still_duration:.2f}s")
            frozen_frame = video_clip.get_frame(freeze_time)
            frozen_tail = ImageClip(frozen_frame).with_duration(still_duration)
            return concatenate_videoclips([video_clip, frozen_tail], method="compose")

        return self._align_video_duration(
            video_clip,
            target_duration,
            long_video_mode=self._resolve_long_video_mode(),
            clip_label=clip_label,
        )

    def _get_last_valid_frame_time(self, video_clip, duration: float) -> float:
        """返回可安全取帧的末帧时间，避免取到容器 duration 边界外的空帧。"""
        duration = float(duration or 0.0)
        if duration <= 0:
            return 0.0

        fps = float(getattr(video_clip, "fps", 0.0) or 0.0)
        if fps <= 0:
            return duration

        frame_step = 1.0 / fps
        safe_margin = frame_step * 2

        n_frames = getattr(getattr(video_clip, "reader", None), "n_frames", None)
        if n_frames:
            last_frame_index = max(int(n_frames) - 2, 0)
            last_frame_time = last_frame_index / fps
            return max(0.0, min(duration - safe_margin, last_frame_time))

        estimated_frame_count = max(int(math.floor(duration * fps)), 1)
        last_frame_index = max(estimated_frame_count - 2, 0)
        return max(0.0, last_frame_index / fps)

    def _apply_fade_in(self, clip, duration: float):
        """
        对视频片段应用淡入效果

        Args:
            clip: 要处理的视频片段
            duration: 淡入时长（秒）

        Returns:
            应用淡入效果后的片段
        """
        def fade_in_transform(gf, t):
            if t < duration:
                alpha = t / duration
                return gf(t) * alpha
            return gf(t)

        return clip.transform(fade_in_transform, keep_duration=True)

    def _apply_fade_out(self, clip, duration: float):
        """
        对视频片段应用淡出效果

        Args:
            clip: 要处理的视频片段
            duration: 淡出时长（秒）

        Returns:
            应用淡出效果后的片段
        """
        clip_duration = clip.duration
        fade_start = clip_duration - duration

        def fade_out_transform(gf, t):
            if t > fade_start:
                alpha = 1.0 - ((t - fade_start) / duration)
                return gf(t) * max(0.0, alpha)
            return gf(t)

        return clip.transform(fade_out_transform, keep_duration=True)

    def _create_color_clip(self, duration: float, color: Tuple[int, int, int], size: Tuple[int, int]):
        """
        创建纯色过渡帧

        Args:
            duration: 持续时长（秒）
            color: RGB颜色值
            size: 视频尺寸 (width, height)

        Returns:
            纯色视频片段
        """
        return ColorClip(size=size, color=color, duration=duration)

    def _create_wipe_transition(self, clip1, clip2, duration: float, direction: str):
        """
        创建擦除过渡效果（类似翻书）

        Args:
            clip1: 第一个视频片段
            clip2: 第二个视频片段
            duration: 过渡时长（秒）
            direction: 擦除方向 ('left' 或 'right')

        Returns:
            带过渡效果的组合片段
        """
        # 获取片段尺寸
        width, height = clip1.size

        # 创建过渡片段
        def make_wipe_frame(t):
            # 计算过渡进度 (0 到 1)
            progress = min(1.0, t / duration)

            # 获取两个片段在当前时间的帧
            frame1 = clip1.get_frame(clip1.duration - duration + t)
            frame2 = clip2.get_frame(t)

            # 计算擦除边界
            if direction == "left":
                # 从左向右擦除
                boundary = int(width * progress)
                result = frame1.copy()
                result[:, :boundary] = frame2[:, :boundary]
            else:  # right
                # 从右向左擦除
                boundary = int(width * (1 - progress))
                result = frame1.copy()
                result[:, boundary:] = frame2[:, boundary:]

            return result

        # 创建过渡片段
        from moviepy import VideoClip
        transition_clip = VideoClip(make_wipe_frame, duration=duration)

        # 组合：clip1主体部分 + 过渡 + clip2主体部分
        clip1_main = clip1.subclipped(0, clip1.duration - duration)
        clip2_main = clip2.subclipped(duration, clip2.duration)

        return concatenate_videoclips([clip1_main, transition_clip, clip2_main], method="chain")

    def _create_slide_transition(self, clip1, clip2, duration: float, direction: str):
        """
        创建滑动过渡效果（新片段滑入覆盖旧片段）

        Args:
            clip1: 第一个视频片段
            clip2: 第二个视频片段
            duration: 过渡时长（秒）
            direction: 滑动方向 ('left' 或 'right')

        Returns:
            带过渡效果的组合片段
        """
        # 获取片段尺寸
        width, height = clip1.size

        # 创建过渡片段
        def make_slide_frame(t):
            # 计算过渡进度 (0 到 1)
            progress = min(1.0, t / duration)

            # 获取两个片段在当前时间的帧
            frame1 = clip1.get_frame(clip1.duration - duration + t)
            frame2 = clip2.get_frame(t)

            # 创建结果帧
            result = np.zeros_like(frame1)

            if direction == "left":
                # 从右向左滑动：新片段从右侧滑入
                offset = int(width * (1 - progress))
                # 旧片段向左移动
                if offset > 0:
                    result[:, :width - offset] = frame1[:, offset:]
                # 新片段从右侧进入
                if offset < width:
                    result[:, width - offset:] = frame2[:, :offset]
            else:  # right
                # 从左向右滑动：新片段从左侧滑入
                offset = int(width * progress)
                # 新片段从左侧进入
                if offset > 0:
                    result[:, :offset] = frame2[:, width - offset:]
                # 旧片段向右移动
                if offset < width:
                    result[:, offset:] = frame1[:, :width - offset]

            return result

        # 创建过渡片段
        from moviepy import VideoClip
        transition_clip = VideoClip(make_slide_frame, duration=duration)

        # 组合：clip1主体部分 + 过渡 + clip2主体部分
        clip1_main = clip1.subclipped(0, clip1.duration - duration)
        clip2_main = clip2.subclipped(duration, clip2.duration)

        return concatenate_videoclips([clip1_main, transition_clip, clip2_main], method="chain")

    def _create_zoom_transition(self, clip1, clip2, duration: float, zoom_type: str):
        """
        创建缩放过渡效果

        Args:
            clip1: 第一个视频片段
            clip2: 第二个视频片段
            duration: 过渡时长（秒）
            zoom_type: 缩放类型 ('in' 或 'out')

        Returns:
            带过渡效果的组合片段
        """
        import numpy as np

        # 获取片段尺寸
        width, height = clip1.size

        # 创建过渡片段
        def make_zoom_frame(t):
            # 计算过渡进度 (0 到 1)
            progress = min(1.0, t / duration)

            # 获取两个片段在当前时间的帧
            frame1 = clip1.get_frame(clip1.duration - duration + t)
            frame2 = clip2.get_frame(t)

            if zoom_type == "in":
                # Zoom In: 旧片段放大淡出，新片段淡入
                # 旧片段缩放因子 (1.0 -> 1.5)
                scale1 = 1.0 + 0.5 * progress
                # 新片段透明度 (0 -> 1)
                alpha2 = progress
            else:  # out
                # Zoom Out: 旧片段缩小淡出，新片段淡入
                # 旧片段缩放因子 (1.0 -> 0.5)
                scale1 = 1.0 - 0.5 * progress
                # 新片段透明度 (0 -> 1)
                alpha2 = progress

            # 缩放旧片段
            new_width = int(width * scale1)
            new_height = int(height * scale1)

            # 使用简单的最近邻插值进行缩放
            from PIL import Image
            img1 = Image.fromarray(frame1)
            img1_resized = img1.resize((new_width, new_height), Image.NEAREST)
            frame1_scaled = np.array(img1_resized)

            # 创建结果帧
            result = np.zeros_like(frame2, dtype=float)

            # 将缩放后的旧片段居中放置
            if scale1 > 0:
                y_offset = max(0, (height - new_height) // 2)
                x_offset = max(0, (width - new_width) // 2)

                y_end = min(height, y_offset + new_height)
                x_end = min(width, x_offset + new_width)

                crop_h = y_end - y_offset
                crop_w = x_end - x_offset

                result[y_offset:y_end, x_offset:x_end] = frame1_scaled[:crop_h, :crop_w].astype(float)

            # 混合新片段（使用透明度）
            result = result * (1 - alpha2) + frame2.astype(float) * alpha2

            return result.astype(np.uint8)

        # 创建过渡片段
        from moviepy import VideoClip
        transition_clip = VideoClip(make_zoom_frame, duration=duration)

        # 组合：clip1主体部分 + 过渡 + clip2主体部分
        clip1_main = clip1.subclipped(0, clip1.duration - duration)
        clip2_main = clip2.subclipped(duration, clip2.duration)

        return concatenate_videoclips([clip1_main, transition_clip, clip2_main], method="chain")

    def _concatenate_with_transitions(self, clips: List, style: str, duration: float):
        """
        使用指定过渡效果连接视频片段

        Args:
            clips: 视频片段列表
            style: 过渡样式 (crossfade, fade_white, fade_black, wipe_left, wipe_right)
            duration: 过渡时长（秒）

        Returns:
            连接后的最终视频
        """
        if len(clips) == 0:
            raise ValueError("没有视频片段可以连接")

        if len(clips) == 1:
            return clips[0]

        # 参数验证和限制
        duration = max(0.1, min(duration, 2.0))  # 限制在0.1-2.0秒

        valid_styles = ["crossfade", "fade_white", "fade_black", "wipe_left", "wipe_right",
                       "slide_left", "slide_right", "zoom_in", "zoom_out"]
        if style not in valid_styles:
            logger.warning(f"不支持的过渡样式 '{style}'，使用默认 'crossfade'")
            style = "crossfade"

        try:
            print(f"正在应用 {style} 过渡效果 (时长: {duration}秒)...")

            if style == "crossfade":
                # 使用MoviePy内置的交叉淡化
                return concatenate_videoclips(clips, method="compose", padding=-duration)

            elif style in ["fade_white", "fade_black"]:
                # 通过颜色淡化
                color = (255, 255, 255) if style == "fade_white" else (0, 0, 0)
                composited_clips = []
                current_time = 0

                for i, clip in enumerate(clips):
                    if i > 0:
                        # 添加颜色过渡帧
                        color_clip = self._create_color_clip(duration, color, clip.size)
                        color_clip = color_clip.with_start(current_time)
                        composited_clips.append(color_clip)
                        current_time += duration

                        # 当前片段添加淡入
                        clip = self._apply_fade_in(clip, duration)

                    if i < len(clips) - 1:
                        # 当前片段添加淡出
                        clip = self._apply_fade_out(clip, duration)

                    clip = clip.with_start(current_time)
                    composited_clips.append(clip)
                    current_time += clip.duration

                return CompositeVideoClip(composited_clips)

            elif style in ["wipe_left", "wipe_right"]:
                # 擦除过渡效果
                direction = "left" if style == "wipe_left" else "right"
                result = clips[0]

                for i in range(1, len(clips)):
                    result = self._create_wipe_transition(result, clips[i], duration, direction)

                return result

            elif style in ["slide_left", "slide_right"]:
                # 滑动过渡效果
                direction = "left" if style == "slide_left" else "right"
                result = clips[0]

                for i in range(1, len(clips)):
                    result = self._create_slide_transition(result, clips[i], duration, direction)

                return result

            elif style in ["zoom_in", "zoom_out"]:
                # 缩放过渡效果
                zoom_type = "in" if style == "zoom_in" else "out"
                result = clips[0]

                for i in range(1, len(clips)):
                    result = self._create_zoom_transition(result, clips[i], duration, zoom_type)

                return result

        except Exception as e:
            logger.warning(f"过渡效果应用失败: {e}，回退到简单拼接")
            return concatenate_videoclips(clips, method="chain")

    @staticmethod
    def _resolve_image_zoom_in_ratio() -> float:
        """返回并校验静态图片 Zoom In 终点倍率。"""
        try:
            ratio = float(getattr(config, "IMAGE_ZOOM_IN_RATIO", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("图片 Zoom In 倍率必须是数字") from exc

        if not math.isfinite(ratio) or not 1.0 <= ratio <= 1.15:
            raise ValueError("图片 Zoom In 倍率必须在 1.0-1.15 之间")
        return ratio

    def _create_image_material_clip(
        self,
        image_path: str,
        duration: float,
        target_size: Tuple[int, int],
        zoom_ratio: float,
    ):
        """创建固定画布尺寸的静态图片片段，可选线性中心推近。"""
        duration = float(duration or 0.0)
        zoom_ratio = float(zoom_ratio or 1.0)

        try:
            with Image.open(image_path) as opened_image:
                source_image = opened_image.convert("RGB").copy()

            if zoom_ratio <= 1.0 + 1e-9 or duration <= 1e-9:
                resized_image = self._resize_image_pil(source_image, target_size)
                return ImageClip(np.array(resized_image)).with_duration(duration)

            target_w, target_h = target_size
            source_w, source_h = source_image.size
            target_aspect = target_w / target_h
            source_aspect = source_w / source_h

            if source_aspect > target_aspect:
                crop_h = float(source_h)
                crop_w = crop_h * target_aspect
                crop_x1 = (source_w - crop_w) / 2.0
                crop_y1 = 0.0
            else:
                crop_w = float(source_w)
                crop_h = crop_w / target_aspect
                crop_x1 = 0.0
                crop_y1 = (source_h - crop_h) / 2.0

            center_x = crop_x1 + crop_w / 2.0
            center_y = crop_y1 + crop_h / 2.0

            def make_zoom_frame(t: float) -> np.ndarray:
                progress = max(0.0, min(1.0, float(t) / duration))
                scale = 1.0 + (zoom_ratio - 1.0) * progress
                visible_w = crop_w / scale
                visible_h = crop_h / scale
                crop_box = (
                    center_x - visible_w / 2.0,
                    center_y - visible_h / 2.0,
                    center_x + visible_w / 2.0,
                    center_y + visible_h / 2.0,
                )
                frame = source_image.resize(
                    target_size,
                    Image.Resampling.BICUBIC,
                    box=crop_box,
                )
                return np.array(frame)

            return VideoClip(frame_function=make_zoom_frame, duration=duration)
        except Exception as exc:
            logger.warning(f"PIL处理图片失败，回退到静态画面: {exc}")
            image_clip = ImageClip(image_path).with_duration(duration)
            return self._resize_image(image_clip, target_size)

    def _create_main_segments(self, image_paths: List[str], audio_paths: List[str], 
                            video_clips: List, audio_clips: List, target_size: Tuple[int, int],
                            narration_speed_factor: float, temp_audio_paths: List[str],
                            image_zoom_in_ratio: float = 1.0):
        """创建主要视频片段（支持图片和视频混合）"""
        
        # 1. 并行处理音频变速
        processed_audio_paths = [None] * len(audio_paths)
        
        # 仅当需要变速时才并行处理
        if abs(narration_speed_factor - 1.0) > 1e-3:
            print(f"⚡️ 正在并行处理 {len(audio_paths)} 个音频片段的变速...")
            from concurrent.futures import ThreadPoolExecutor
            
            def process_single_audio(idx_and_path):
                idx, a_path = idx_and_path
                try:
                    p_path = self._ensure_speed_adjusted_audio(
                        a_path,
                        narration_speed_factor,
                        temp_audio_paths # 注意：这里append不是线程安全的，但在Python GIL下list append通常是原子的，或者我们可以改用返回结果再汇总
                    )
                    return idx, p_path
                except Exception as e:
                    logger.warning(f"音频片段 {idx+1} 变速处理失败: {e}")
                    return idx, a_path

            # 使用 max_workers=os.cpu_count() 并行处理
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                # 提交任务
                futures = list(executor.map(process_single_audio, enumerate(audio_paths)))
                
                # 收集结果
                for idx, result_path in futures:
                    processed_audio_paths[idx] = result_path
        else:
            processed_audio_paths = audio_paths

        static_image_indices = [
            index for index, path in enumerate(image_paths)
            if not self._is_video_file(path)
        ]
        last_static_image_index = static_image_indices[-1] if static_image_indices else None

        # 2. 顺序组装视频片段 (MoviePy对象创建通常很快)
        for i, (media_path, processed_audio_path) in enumerate(zip(image_paths, processed_audio_paths)):
            # print(f"正在组装第{i+1}段素材...") # 减少日志输出

            audio_clip = AudioFileClip(processed_audio_path)
            
            if self._is_video_file(media_path):
                # 视频素材处理
                video_clip = self._create_video_segment(media_path, audio_clip, target_size)
            else:
                zoom_ratio = (
                    image_zoom_in_ratio
                    if i != last_static_image_index
                    else 1.0
                )
                image_clip = self._create_image_material_clip(
                    media_path,
                    audio_clip.duration,
                    target_size,
                    zoom_ratio,
                )
                
                video_clip = image_clip.with_audio(audio_clip)
            
            video_clips.append(video_clip)
            audio_clips.append(audio_clip)
    
    @handle_video_operation("字幕添加", critical=False, fallback_value=lambda self, final_video, *args: final_video)
    def _add_subtitles(self, final_video, script_data: Dict[str, Any], enable_subtitles: bool, 
                      audio_clips: List, opening_seconds: float):
        """添加字幕"""
        if enable_subtitles and script_data:
            print("正在添加字幕...")
            # 从独立变量构建字幕配置字典
            subtitle_config = {
                "style": getattr(config, "SUBTITLE_STYLE", "classic"),
                "font_size": config.SUBTITLE_FONT_SIZE,
                "font_family": config.SUBTITLE_FONT_FAMILY,
                "ttc_index": config.SUBTITLE_FONT_TTC_INDEX,
                "color": config.SUBTITLE_COLOR,
                "stroke_color": config.SUBTITLE_STROKE_COLOR,
                "stroke_width": config.SUBTITLE_STROKE_WIDTH,
                "position": config.SUBTITLE_POSITION,
                "margin_bottom": config.SUBTITLE_MARGIN_BOTTOM,
                "max_chars_per_line": config.SUBTITLE_MAX_CHARS_PER_LINE,
                "max_lines": config.SUBTITLE_MAX_LINES,
                "line_spacing": config.SUBTITLE_LINE_SPACING,
                "letter_spacing": config.SUBTITLE_LETTER_SPACING,
                "background_color": config.SUBTITLE_BACKGROUND_COLOR,
                "background_opacity": config.SUBTITLE_BACKGROUND_OPACITY,
                "background_horizontal_padding": config.SUBTITLE_BACKGROUND_H_PADDING,
                "background_vertical_padding": config.SUBTITLE_BACKGROUND_V_PADDING,
                "shadow_enabled": config.SUBTITLE_SHADOW_ENABLED,
                "shadow_color": config.SUBTITLE_SHADOW_COLOR,
                "shadow_offset": config.SUBTITLE_SHADOW_OFFSET,
                "video_size": final_video.size,
                "segment_durations": [ac.duration for ac in audio_clips],
                "offset_seconds": opening_seconds,
            }
            subtitle_clips = self.create_subtitle_clips(script_data, subtitle_config)
            
            if subtitle_clips:
                final_video = CompositeVideoClip([final_video] + subtitle_clips)
                print(f"已添加 {len(subtitle_clips)} 个字幕剪辑")
            else:
                print("未生成任何字幕剪辑")
        
        return final_video
    
    def _adjust_narration_volume(self, final_video, narration_volume: float):
        """调整口播音量"""
        try:
            if final_video.audio is not None and narration_volume is not None:
                narration_audio = final_video.audio
                if isinstance(narration_volume, (int, float)) and abs(float(narration_volume) - 1.0) > 1e-9:
                    narration_audio = narration_audio.with_volume_scaled(float(narration_volume))
                    final_video = final_video.with_audio(narration_audio)
                    print(f"🔊 口播音量调整为: {float(narration_volume)}")
        except Exception as e:
            logger.warning(f"口播音量调整失败: {str(e)}，将使用原始音量")
        
        return final_video
    
    @handle_video_operation("视觉效果添加", critical=False, fallback_value=lambda self, final_video, *args: final_video)
    def _add_visual_effects(self, final_video, image_paths: List[str], target_size: Tuple[int, int]):
        """添加视觉效果（开场渐显和片尾渐隐）"""
        # 性能优化：跳过逐帧开场渐显
        
        # 性能优化：仅添加片尾静帧，不做逐帧渐隐
        tail_seconds = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
        if isinstance(image_paths, list) and len(image_paths) > 0 and tail_seconds > 1e-3:
            last_image_path = image_paths[-1]
            try:
                with Image.open(last_image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    resized_img = self._resize_image_pil(img, target_size)
                    img_array = np.array(resized_img)
                    tail_clip = ImageClip(img_array).with_duration(tail_seconds)
            except Exception as e:
                logger.warning(f"PIL处理片尾图片失败: {e}")
                tail_clip = ImageClip(last_image_path).with_duration(tail_seconds)
                tail_clip = self._resize_image(tail_clip, target_size)
            
            final_video = concatenate_videoclips([final_video, tail_clip], method="chain")
            print(f"🎬 已添加片尾静帧 {tail_seconds}s")
        
        return final_video
    
    @handle_video_operation("背景音乐添加", critical=False, fallback_value=lambda self, final_video, *args: final_video)
    def _add_background_music(self, final_video, bgm_audio_path: Optional[str], bgm_volume: float,
                              project_root: Optional[str] = None,
                              temp_audio_paths: Optional[List[str]] = None,
                              audio_clips: Optional[List] = None):
        """添加背景音乐"""
        if not bgm_audio_path or not os.path.exists(bgm_audio_path):
            if bgm_audio_path:
                print(f"⚠️ 背景音乐文件不存在: {bgm_audio_path}")
            else:
                print("ℹ️ 未指定背景音乐文件")
            return final_video

        print(f"🎵 开始处理背景音乐: {bgm_audio_path}")

        # 如果启用了响度标准化且提供了project_root，先进行标准化处理
        if project_root and getattr(config, "BGM_NORMALIZE_LOUDNESS", False):
            orig_path = bgm_audio_path
            bgm_audio_path = self._normalize_bgm_loudness(bgm_audio_path, project_root)
            if temp_audio_paths is not None and bgm_audio_path != orig_path:
                temp_audio_paths.append(bgm_audio_path)

        bgm_clip = AudioFileClip(bgm_audio_path)
        if audio_clips is not None:
            audio_clips.append(bgm_clip)
        print(f"🎵 BGM加载成功，时长: {bgm_clip.duration:.2f}秒")
        
        # 调整BGM音量
        if isinstance(bgm_volume, (int, float)) and abs(float(bgm_volume) - 1.0) > 1e-9:
            bgm_clip = bgm_clip.with_volume_scaled(float(bgm_volume))
            print(f"🎵 BGM音量调整为: {float(bgm_volume)}")
        
        # 调整BGM长度
        bgm_clip = self._adjust_bgm_duration(bgm_clip, final_video.duration)
        
        if bgm_clip is not None:
            # 应用音频效果
            bgm_clip = self._apply_audio_effects(bgm_clip, final_video)
            
            # 合成音频
            if final_video.audio is not None:
                mixed_audio = CompositeAudioClip([final_video.audio, bgm_clip])
                print("🎵 BGM与口播音频合成完成")
            else:
                mixed_audio = CompositeAudioClip([bgm_clip])
                print("🎵 仅添加BGM音频（无口播音频）")
            
            final_video = final_video.with_audio(mixed_audio)
            print("🎵 背景音乐添加成功！")
        
        return final_video

    def _normalize_bgm_loudness(self, bgm_audio_path: str, project_root: str) -> str:
        """
        使用FFmpeg loudnorm滤镜标准化BGM响度

        Args:
            bgm_audio_path: 原始BGM音频文件路径
            project_root: 项目根目录（用于存放临时文件）

        Returns:
            str: 标准化后的音频文件路径（失败时返回原路径）
        """
        return normalize_bgm_loudness(
            bgm_audio_path,
            project_root,
            target_loudness=float(getattr(config, "BGM_TARGET_LOUDNESS", 20.0)),
            loudness_range=float(getattr(config, "BGM_LOUDNESS_RANGE", 7.0)),
            enabled=bool(getattr(config, "BGM_NORMALIZE_LOUDNESS", False)),
        )

    def _adjust_bgm_duration(self, bgm_clip, target_duration: float):
        """调整BGM时长：优先手动平铺循环，始终铺满并裁剪到目标时长"""
        try:
            print(f"🎵 视频总时长: {target_duration:.2f}秒，BGM时长: {bgm_clip.duration:.2f}秒")

            # 基本校验
            if target_duration <= 0:
                return bgm_clip
            unit_duration = float(bgm_clip.duration)
            if unit_duration <= 1e-6:
                raise RuntimeError("BGM源时长为0")

            # 若BGM长于目标，直接裁剪
            if unit_duration >= target_duration - 1e-6:
                try:
                    return bgm_clip.with_duration(target_duration)
                except Exception:
                    # 兜底：子片段裁剪
                    return bgm_clip.subclipped(0, target_duration)

            # 手动平铺：重复拼接 + 末段精确裁剪
            clips = []
            accumulated = 0.0
            # 先整段重复
            while accumulated + unit_duration <= target_duration - 1e-6:
                clips.append(bgm_clip.subclipped(0, unit_duration))
                accumulated += unit_duration
            # 末段裁剪
            remaining = max(0.0, target_duration - accumulated)
            if remaining > 1e-6:
                clips.append(bgm_clip.subclipped(0, remaining))

            looped = concatenate_audioclips(clips)
            print(f"🎵 BGM长度适配完成（manual loop），最终时长: {looped.duration:.2f}秒")
            return looped

        except Exception as e:
            print(f"⚠️ 背景音乐长度适配失败: {e}，将不添加BGM继续生成")
            logger.warning(f"背景音乐循环/裁剪失败: {e}")
            return None
    
    def _apply_audio_effects(self, bgm_clip, final_video):
        """应用音频效果（Ducking和淡出）"""
        if not getattr(config, "AUDIO_DUCKING_ENABLED", False):
            return bgm_clip
        return self._apply_ducking_effect(bgm_clip, final_video)
    
    def _apply_ducking_effect(self, bgm_clip, final_video):
        """应用自动Ducking效果"""
        strength = float(getattr(config, "AUDIO_DUCKING_STRENGTH", 0.7))
        smooth_sec = float(getattr(config, "AUDIO_DUCKING_SMOOTH_SECONDS", 0.12))
        total_dur = float(final_video.duration)
        
        # 采样频率
        env_fps = 20.0
        num_samples = max(2, int(total_dur * env_fps) + 1)
        times = np.linspace(0.0, total_dur, num_samples)
        
        # 估算口播瞬时幅度
        amp = np.zeros_like(times)
        for i, t in enumerate(times):
            try:
                frame = final_video.audio.get_frame(float(min(max(0.0, t), total_dur - 1e-6)))
                amp[i] = float(np.mean(np.abs(frame)))
            except Exception:
                amp[i] = 0.0
        
        # 平滑处理
        win = max(1, int(smooth_sec * env_fps))
        if win > 1:
            kernel = np.ones(win, dtype=float) / win
            amp = np.convolve(amp, kernel, mode="same")
        
        # 归一化
        max_amp = float(np.max(amp)) if np.max(amp) > 1e-8 else 1.0
        env = amp / max_amp
        
        # 计算ducking增益曲线
        gains = 1.0 - strength * env
        gains = np.clip(gains, 0.0, 1.0)
        
        # 构建时间变增益函数
        def ducking_gain_lookup(t_any):
            def lookup_single(ts: float) -> float:
                if ts <= 0.0:
                    return float(gains[0])
                if ts >= total_dur:
                    return float(gains[-1])
                idx = max(0, min(int(ts * env_fps), gains.shape[0] - 1))
                return float(gains[idx])
            
            if hasattr(t_any, "__len__"):
                return np.array([lookup_single(float(ts)) for ts in t_any])
            return lookup_single(float(t_any))
        
        # 应用时间变增益
        bgm_clip = bgm_clip.transform(
            lambda gf, t: (
                (ducking_gain_lookup(t)[:, None] if hasattr(t, "__len__") else ducking_gain_lookup(t))
                * gf(t)
            ),
            keep_duration=True,
        )
        print(f"🎚️ 已启用自动Ducking（strength={strength}, smooth={smooth_sec}s）")
        
        return bgm_clip
    
    def _export_video(self, final_video, output_path: str, fps: int = 15):
        """导出视频"""
        export_video(
            final_video,
            output_path,
            fps=fps,
            video_codec=getattr(config, "VIDEO_CODEC", "h264"),
            bitrate_mode=getattr(config, "VIDEO_BITRATE_MODE", "auto"),
            quality_level=int(getattr(config, "VIDEO_QUALITY_LEVEL", 65)),
            fade_in_seconds=float(getattr(config, "OPENING_FADEIN_SECONDS", 0.0)),
            ending_fade_seconds=float(getattr(config, "ENDING_FADE_SECONDS", 0.0)),
        )
    
    def _cleanup_resources(self, video_clips: List, audio_clips: List,
                           final_video, temp_audio_paths: Optional[List[str]] = None):
        """释放资源并清理由变速生成的临时文件"""
        for clip in video_clips:
            with suppress(Exception):
                clip.close()
        for aclip in audio_clips:
            with suppress(Exception):
                aclip.close()
        if final_video is not None:
            with suppress(Exception):
                final_video.close()
        if temp_audio_paths:
            for temp_path in temp_audio_paths:
                if temp_path and os.path.exists(temp_path):
                    with suppress(Exception):
                        os.remove(temp_path)
    
    def create_subtitle_clips(self, script_data: Dict[str, Any],
                            subtitle_config: Dict[str, Any] = None) -> List:
        """创建字幕剪辑列表"""
        if subtitle_config is None:
            # 从独立变量构建默认字幕配置
            subtitle_config = {
                "style": getattr(config, "SUBTITLE_STYLE", "classic"),
                "font_size": config.SUBTITLE_FONT_SIZE,
                "font_family": config.SUBTITLE_FONT_FAMILY,
                "ttc_index": config.SUBTITLE_FONT_TTC_INDEX,
                "color": config.SUBTITLE_COLOR,
                "stroke_color": config.SUBTITLE_STROKE_COLOR,
                "stroke_width": config.SUBTITLE_STROKE_WIDTH,
                "position": config.SUBTITLE_POSITION,
                "margin_bottom": config.SUBTITLE_MARGIN_BOTTOM,
                "max_chars_per_line": config.SUBTITLE_MAX_CHARS_PER_LINE,
                "max_lines": config.SUBTITLE_MAX_LINES,
                "line_spacing": config.SUBTITLE_LINE_SPACING,
                "letter_spacing": config.SUBTITLE_LETTER_SPACING,
                "background_color": config.SUBTITLE_BACKGROUND_COLOR,
                "background_opacity": config.SUBTITLE_BACKGROUND_OPACITY,
                "background_horizontal_padding": config.SUBTITLE_BACKGROUND_H_PADDING,
                "background_vertical_padding": config.SUBTITLE_BACKGROUND_V_PADDING,
                "shadow_enabled": config.SUBTITLE_SHADOW_ENABLED,
                "shadow_color": config.SUBTITLE_SHADOW_COLOR,
                "shadow_offset": config.SUBTITLE_SHADOW_OFFSET,
            }
        
        subtitle_clips = []
        current_time = float(subtitle_config.get("offset_seconds", 0.0))
        
        logger.info("开始创建字幕剪辑...")
        
        # 解析字体
        subtitle_style = str(subtitle_config.get("style", "classic") or "classic").strip().lower()
        resolved_font, resolved_ttc_index = self.resolve_subtitle_font(
            subtitle_config.get("font_family"),
            int(subtitle_config.get("ttc_index", 0)),
            subtitle_style,
        )
        subtitle_config["ttc_index"] = resolved_ttc_index
        if not resolved_font:
            logger.warning("未能解析到可用中文字体")
        
        # 读取视频尺寸
        video_size = subtitle_config["video_size"]
        video_width, video_height = video_size
        subtitle_config = self._scale_subtitle_config_for_video(
            subtitle_config,
            video_width,
            video_height,
        )
        
        segment_durations = subtitle_config.get("segment_durations", [])
        
        # 标点替换模式
        punctuation_pattern = r"[,!?;:，。！？；：…、—]+"
        
        for i, segment in enumerate(script_data["segments"], 1):
            content = segment["content"]
            
            # 获取时长 - 优先使用实际音频时长
            duration = float(segment.get("estimated_duration", 0))
            if isinstance(segment_durations, list) and len(segment_durations) >= i:
                duration = float(segment_durations[i-1])  # 实际音频时长覆盖估算值
            
            logger.debug(f"处理第{i}段字幕，时长: {duration}秒")
            
            # 分割文本
            subtitle_texts = self.split_text_for_subtitle(
                content,
                subtitle_config["max_chars_per_line"],
                subtitle_config["max_lines"],
                display_formatter=format_subtitle_display_text if subtitle_style == "editorial" else None,
            )
            
            # 计算每行字幕时长
            subtitle_start_time = current_time
            line_durations = self._calculate_subtitle_durations(subtitle_texts, duration)
            
            for subtitle_text, subtitle_duration in zip(subtitle_texts, line_durations):
                try:
                    # 处理标点
                    if subtitle_style == "editorial":
                        display_text = format_subtitle_display_text(subtitle_text)
                    else:
                        display_text = re.sub(punctuation_pattern, "  ", subtitle_text)
                        display_text = re.sub(r" {3,}", "  ", display_text).rstrip()
                    
                    # 创建字幕剪辑
                    clips_to_add = self._create_subtitle_clips_internal(
                        display_text, subtitle_start_time, subtitle_duration,
                        subtitle_config, resolved_font, video_width, video_height
                    )
                    subtitle_clips.extend(clips_to_add)
                    
                    logger.debug(f"创建字幕: '{subtitle_text[:20]}...' 时间: {subtitle_start_time:.1f}-{subtitle_start_time+subtitle_duration:.1f}s")
                    subtitle_start_time += subtitle_duration
                    
                except Exception as e:
                    logger.warning(f"创建字幕失败: {str(e)}，跳过此字幕")
                    continue
            
            current_time += duration
        
        logger.info(f"字幕创建完成，共创建 {len(subtitle_clips)} 个字幕剪辑")
        return subtitle_clips

    def _scale_subtitle_config_for_video(
        self,
        subtitle_config: Dict[str, Any],
        video_width: int,
        video_height: int,
    ) -> Dict[str, Any]:
        """将字幕视觉参数从 1280x720 基准等比缩放到实际母版尺寸。"""
        scaled = dict(subtitle_config)
        width_scale = max(0.01, float(video_width) / 1280.0)
        height_scale = max(0.01, float(video_height) / 720.0)
        scale = max(0.75, min(2.0, min(width_scale, height_scale)))

        for key, minimum in (
            ("font_size", 18),
            ("stroke_width", 1),
            ("margin_bottom", 0),
            ("line_spacing", 0),
            ("letter_spacing", 0),
            ("background_horizontal_padding", 0),
            ("background_vertical_padding", 0),
            ("baseline_safe_padding", 2),
        ):
            if key in scaled:
                scaled[key] = max(minimum, int(round(float(scaled[key] or 0) * scale)))

        shadow_offset = scaled.get("shadow_offset")
        if isinstance(shadow_offset, (tuple, list)) and len(shadow_offset) == 2:
            scaled["shadow_offset"] = tuple(int(round(float(value) * scale)) for value in shadow_offset)
        return scaled
    
    def _calculate_subtitle_durations(self, subtitle_texts: List[str], total_duration: float) -> List[float]:
        """计算每行字幕的显示时长"""
        return calculate_subtitle_durations(subtitle_texts, total_duration)
    
    def _create_subtitle_clips_internal(self, display_text: str, start_time: float, duration: float,
                                       subtitle_config: Dict, resolved_font: Optional[str], 
                                       video_width: int, video_height: int) -> List:
        """内部字幕剪辑创建函数"""
        clips_to_add = []
        position = subtitle_config["position"]
        margin_bottom = int(subtitle_config.get("margin_bottom", 0))
        anchor_x = position[0] if isinstance(position, tuple) else "center"
        font_path = resolved_font or subtitle_config["font_family"]
        ttc_index = int(subtitle_config.get("ttc_index", 0))
        letter_spacing = int(subtitle_config.get("letter_spacing", 0) or 0)

        if str(subtitle_config.get("style", "classic") or "classic").strip().lower() == "editorial":
            editorial_card = self._create_editorial_subtitle_card(
                text=display_text,
                subtitle_config=subtitle_config,
                font_path=font_path,
                ttc_index=ttc_index,
                video_width=video_width,
            )
            card_clip = ImageClip(np.array(editorial_card))
            y_card = max(0, video_height - margin_bottom - card_clip.h)
            card_clip = (
                card_clip
                .with_start(start_time)
                .with_duration(duration)
                .with_position(("center", y_card))
            )
            return [card_clip]
        
        # 使用 PIL 渲染主要文字（解决 MoviePy TextClip 底部裁切问题）
        text_img = self._create_text_image_pil(
            text=display_text,
            font_size=subtitle_config["font_size"],
            font_path=font_path,
            text_color=subtitle_config["color"],
            stroke_color=subtitle_config["stroke_color"],
            stroke_width=subtitle_config["stroke_width"],
            ttc_index=ttc_index,
            letter_spacing=letter_spacing,
        )
        main_clip = ImageClip(np.array(text_img))
        
        # 添加背景条（需要先计算，确定文字位置）
        bg_color = subtitle_config.get("background_color")
        bg_opacity = float(subtitle_config.get("background_opacity", 0))
        if bg_color and bg_opacity > 0.0:
            bg_height = int(
                subtitle_config["font_size"] * subtitle_config.get("max_lines", 2)
                + subtitle_config.get("line_spacing", 10) 
                + subtitle_config.get("background_vertical_padding", 10)
            )
            text_width = main_clip.w
            bg_padding = int(subtitle_config.get("background_horizontal_padding", 20))
            # 限制背景宽度不超过视频宽度的90%
            max_bg_width = int(video_width * 0.9)
            bg_width = min(text_width + bg_padding, max_bg_width)
            
            # 背景位置
            y_bg = max(0, video_height - margin_bottom - bg_height)
            bg_clip = ColorClip(size=(bg_width, bg_height), color=bg_color)
            if hasattr(bg_clip, "with_opacity"):
                bg_clip = bg_clip.with_opacity(bg_opacity)
            # 先设定时间，再设定位置，避免时间轴属性被覆盖
            bg_clip = bg_clip.with_start(start_time).with_duration(duration).with_position(("center", y_bg))
            
            # 文字在背景中垂直居中
            y_text_centered = y_bg + (bg_height - main_clip.h) // 2
            main_pos = (anchor_x, y_text_centered)
            clips_to_add.append(bg_clip)
        else:
            # 无背景时使用原来的位置计算
            if isinstance(position, tuple) and len(position) == 2 and position[1] == "bottom":
                baseline_safe_padding = int(subtitle_config.get("baseline_safe_padding", 4))
                y_text = max(0, video_height - margin_bottom - main_clip.h - baseline_safe_padding)
                main_pos = (anchor_x, y_text)
            else:
                main_pos = position
        
        # 修复 main_pos 如果有字符串 "center" 的相对偏移计算问题
        # 计算文字具体的 X 和 Y 坐标（为阴影服务）
        actual_x = (video_width - main_clip.w) // 2 if main_pos[0] == "center" else main_pos[0]
        actual_y = main_pos[1] if isinstance(main_pos[1], int) else (video_height - main_clip.h) // 2
        
        # 先设定时间，再设定位置，避免时间轴属性被覆盖
        main_clip = main_clip.with_start(start_time).with_duration(duration).with_position(main_pos)
        
        # 添加阴影
        if subtitle_config.get("shadow_enabled", False):
            shadow_color = subtitle_config.get("shadow_color", "black")
            shadow_offset = subtitle_config.get("shadow_offset", (2, 2))
            
            shadow_img = self._create_text_image_pil(
                text=display_text,
                font_size=subtitle_config["font_size"],
                font_path=font_path,
                text_color=shadow_color,
                stroke_color=shadow_color,
                stroke_width=subtitle_config["stroke_width"],
                ttc_index=ttc_index,
                letter_spacing=letter_spacing,
            )
            shadow_pos = (actual_x + shadow_offset[0], actual_y + shadow_offset[1])
            shadow_clip = ImageClip(np.array(shadow_img)).with_start(start_time).with_duration(duration).with_position(shadow_pos)
            
            clips_to_add.extend([shadow_clip, main_clip])
        else:
            clips_to_add.append(main_clip)
        
        return clips_to_add

    def _create_editorial_subtitle_card(
        self,
        text: str,
        subtitle_config: Dict[str, Any],
        font_path: str,
        ttc_index: int,
        video_width: int,
    ) -> Image.Image:
        """渲染电影编辑部风格的自适应圆角字幕卡。"""
        preferred_size = int(subtitle_config.get("font_size", 66) or 66)
        minimum_size = max(32, int(round(preferred_size * 0.72)))
        letter_spacing = int(subtitle_config.get("letter_spacing", 0) or 0)
        horizontal_padding = max(24, int(round(preferred_size * 0.58)))
        top_padding = max(16, int(round(preferred_size * 0.34)))
        bottom_padding = max(16, int(round(preferred_size * 0.34)))
        max_card_width = max(240, int(video_width * 0.90))
        max_text_width = max(120, max_card_width - horizontal_padding * 2)

        text_image = None
        for size in range(preferred_size, minimum_size - 1, -2):
            candidate = self._create_text_image_pil(
                text=text,
                font_size=size,
                font_path=font_path,
                text_color=(246, 240, 226, 255),
                stroke_color=(35, 30, 28, 255),
                stroke_width=max(1, int(round(size / 64))),
                ttc_index=ttc_index,
                letter_spacing=letter_spacing,
            )
            text_image = candidate
            if candidate.width <= max_text_width:
                break

        if text_image is None:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        card_width = min(max_card_width, text_image.width + horizontal_padding * 2)
        card_height = text_image.height + top_padding + bottom_padding
        card = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        radius = max(12, int(round(preferred_size * 0.27)))
        border_width = max(1, int(round(preferred_size / 34)))
        draw.rounded_rectangle(
            (0, 0, card_width - 1, card_height - 1),
            radius=radius,
            fill=(13, 18, 25, 218),
            outline=(92, 86, 80, 190),
            width=border_width,
        )

        text_x = max(0, (card_width - text_image.width) // 2)
        text_y = top_padding
        card.alpha_composite(text_image, (text_x, text_y))
        return card
    
    def split_text_for_subtitle(
        self,
        text: str,
        max_chars_per_line: int = 20,
        max_lines: int = 2,
        display_formatter: Callable[[str], str] | None = None,
    ) -> List[str]:
        """将长文本分割为适合字幕显示的短句，同时保护成对符号（书名号、引号）"""
        return split_text_for_subtitle(text, max_chars_per_line, max_lines, display_formatter)
    
    def resolve_subtitle_font(
        self,
        preferred: Optional[str],
        preferred_ttc_index: int = 0,
        style: str = "classic",
    ) -> Tuple[Optional[str], int]:
        """解析字幕字体路径和 TTC index。"""
        preferred_text = (preferred or "").strip()
        if preferred_text and preferred_text.lower() != "auto":
            if os.path.exists(preferred_text):
                return preferred_text, int(preferred_ttc_index or 0)
            logger.warning("配置的字幕字体不存在，自动回退到系统字体: %s", preferred_text)

        editorial_fonts = [
            # macOS
            ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),
            # Windows
            ("C:/Windows/Fonts/simsun.ttc", 0),
            ("C:/Windows/Fonts/simkai.ttf", 0),
            # Linux
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
            ("/usr/share/fonts/opentype/adobe-source-han-serif/SourceHanSerifSC-Bold.otf", 0),
        ]
        common_fonts = [
            # macOS
            ("/System/Library/Fonts/PingFang.ttc", 0),
            ("/System/Library/Fonts/STHeiti Light.ttc", 0),
            ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
            # Windows
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("C:/Windows/Fonts/simhei.ttf", 0),
            ("C:/Windows/Fonts/simsun.ttc", 0),
            # Linux
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
        ]

        candidates = editorial_fonts + common_fonts if str(style).lower() == "editorial" else common_fonts
        for font_path, ttc_index in candidates:
            if os.path.exists(font_path):
                return font_path, ttc_index

        return None, 0

    def resolve_font_path(self, preferred: Optional[str]) -> Optional[str]:
        """解析字体路径，保留旧接口兼容测试和外部调用。"""
        font_path, _ = self.resolve_subtitle_font(preferred, 0)
        return font_path
    
    def _is_video_file(self, file_path: str) -> bool:
        """检测是否为视频文件"""
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in SUPPORTED_VIDEO_FORMATS
    
    def _has_video_materials(self, media_paths: List[str]) -> bool:
        """检测是否包含视频素材"""
        return any(self._is_video_file(path) for path in media_paths)

    def _resolve_long_video_mode(self) -> str:
        """解析长视频对齐策略，优先读取新配置并兼容旧配置。"""
        mode = str(getattr(config, "VIDEO_MATERIAL_LONGER_THAN_AUDIO_MODE", "") or "").strip().lower()
        if mode in {"crop", "compress"}:
            return mode

        legacy_mode = str(getattr(config, "VIDEO_MATERIAL_DURATION_ADJUST", "") or "").strip().lower()
        if legacy_mode in {"crop", "compress"}:
            return legacy_mode
        if legacy_mode == "stretch":
            return "compress"

        if mode:
            logger.warning(
                "未知 VIDEO_MATERIAL_LONGER_THAN_AUDIO_MODE=%s，回退为 crop（支持: crop/compress）",
                mode,
            )
        return "crop"

    def _align_video_duration(self, video_clip, target_duration: float, long_video_mode: str, clip_label: str):
        """按目标时长对齐视频：短视频均匀拉长，长视频按策略裁剪或均匀压缩。"""
        original_duration = float(getattr(video_clip, "duration", 0.0) or 0.0)
        target_duration = float(target_duration or 0.0)

        if target_duration <= 1e-3 or original_duration <= 1e-3:
            print(f"  {clip_label}时长异常，跳过时长对齐")
            return video_clip

        if abs(original_duration - target_duration) <= 1e-3:
            print(f"  {clip_label}时长匹配，无需调整")
            return video_clip

        if original_duration < target_duration:
            speed_factor = original_duration / target_duration
            print(f"  {clip_label}较短，均匀拉长系数: {speed_factor:.3f}")
            return video_clip.with_speed_scaled(final_duration=target_duration)

        if long_video_mode == "compress":
            speed_factor = original_duration / target_duration
            print(f"  {clip_label}较长，均匀压缩系数: {speed_factor:.3f}")
            return video_clip.with_speed_scaled(final_duration=target_duration)

        print(f"  {clip_label}较长，从头裁剪到 {target_duration:.2f}s")
        return video_clip.subclipped(0, target_duration)
    
    def _create_video_segment(self, video_path: str, audio_clip, target_size: Tuple[int, int]) -> Any:
        """创建视频片段"""
        print(f"处理视频素材: {os.path.basename(video_path)}")
        
        # 加载视频文件
        video_clip = VideoFileClip(video_path)
        original_duration = video_clip.duration
        target_duration = audio_clip.duration
        
        print(f"  原视频时长: {original_duration:.2f}s，目标时长: {target_duration:.2f}s")
        
        # 按配置移除原音轨（默认移除）
        if bool(getattr(config, "VIDEO_MATERIAL_REMOVE_AUDIO", True)):
            video_clip = video_clip.without_audio()
        video_clip = self._resize_video(video_clip, target_size)

        video_clip = self._align_video_duration(
            video_clip,
            target_duration,
            long_video_mode=self._resolve_long_video_mode(),
            clip_label="段落视频",
        )
        
        return video_clip.with_audio(audio_clip)
    
    def _resize_video(self, video_clip, target_size: Tuple[int, int]) -> Any:
        """调整视频尺寸到指定尺寸"""
        target_w, target_h = target_size
        original_w, original_h = video_clip.size
        
        # 按比例缩放并裁剪
        scale_w = target_w / original_w
        scale_h = target_h / original_h
        
        if scale_w > scale_h:
            video_clip = video_clip.resized(width=target_w)
            if video_clip.h > target_h:
                y_start = (video_clip.h - target_h) // 2
                video_clip = video_clip.cropped(y1=y_start, y2=y_start + target_h)
        else:
            video_clip = video_clip.resized(height=target_h)
            if video_clip.w > target_w:
                x_start = (video_clip.w - target_w) // 2
                video_clip = video_clip.cropped(x1=x_start, x2=x_start + target_w)
        
        return video_clip
    
    def _parse_image_size(self, image_size: str) -> Tuple[int, int]:
        """解析图像尺寸字符串，如 "1024x1024" -> (1024, 1024)"""
        try:
            normalized_size = str(image_size or "1280x720").lower().replace("×", "x").replace("*", "x").replace(" ", "")
            width_str, height_str = normalized_size.split('x')
            width = int(width_str.strip())
            height = int(height_str.strip())
            return (width, height)
        except (ValueError, AttributeError) as e:
            logger.warning(f"无法解析图像尺寸 '{image_size}'，使用默认1280x720: {e}")
            return (1280, 720)
    
    def _resize_image_pil(self, img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """使用PIL调整图片尺寸（性能优化版）"""
        target_w, target_h = target_size
        original_w, original_h = img.size
        
        if original_w == target_w and original_h == target_h:
            return img
            
        # 按比例缩放并裁剪（Aspect Fill）
        scale_w = target_w / original_w
        scale_h = target_h / original_h
        
        if scale_w > scale_h:
            new_w = target_w
            new_h = int(original_h * scale_w)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # 垂直裁剪
            if new_h > target_h:
                y_start = (new_h - target_h) // 2
                img = img.crop((0, y_start, target_w, y_start + target_h))
        else:
            new_h = target_h
            new_w = int(original_w * scale_h)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # 水平裁剪
            if new_w > target_w:
                x_start = (new_w - target_w) // 2
                img = img.crop((x_start, 0, x_start + target_w, target_h))
                
        return img

    def _resize_image(self, image_clip, target_size: Tuple[int, int]) -> Any:
        """调整图片尺寸到指定尺寸"""
        target_w, target_h = target_size
        original_w, original_h = image_clip.size
        
        # 如果原图尺寸已经匹配，直接返回
        if original_w == target_w and original_h == target_h:
            return image_clip
        
        # 按比例缩放并裁剪（与视频处理逻辑一致）
        scale_w = target_w / original_w
        scale_h = target_h / original_h
        
        if scale_w > scale_h:
            image_clip = image_clip.resized(width=target_w)
            if image_clip.h > target_h:
                y_start = (image_clip.h - target_h) // 2
                image_clip = image_clip.cropped(y1=y_start, y2=y_start + target_h)
        else:
            image_clip = image_clip.resized(height=target_h)
            if image_clip.w > target_w:
                x_start = (image_clip.w - target_w) // 2
                image_clip = image_clip.cropped(x1=x_start, x2=x_start + target_w)
        
        return image_clip
    
