"""
视频合成器 - 统一的视频合成处理模块（迁移至 core）
整合视频合成、字幕生成、音频混合等功能
"""

import os
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# MoviePy 2.x imports (no editor module)
from moviepy import (
    ImageClip,
    TextClip,
    ColorClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    AudioFileClip,
    concatenate_audioclips,
)

from config import config
from utils import logger, FileProcessingError
from prompts import IMAGE_STYLE_PRESETS as IMAGE_STYLE_PRESETS_PROMPTS


class VideoComposer:
    """统一的视频合成器"""
    
    def __init__(self):
        """初始化视频合成器"""
        pass
    
    def compose_video(self, image_paths: List[str], audio_paths: List[str], output_path: str, 
                     script_data: Dict[str, Any] = None, enable_subtitles: bool = False,
                     bgm_audio_path: Optional[str] = None, bgm_volume: float = 0.15,
                     narration_volume: float = 1.0,
                     opening_image_path: Optional[str] = None,
                     opening_golden_quote: Optional[str] = None,
                     opening_narration_audio_path: Optional[str] = None) -> str:
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
            opening_image_path: 开场图片路径
            opening_golden_quote: 开场金句
            opening_narration_audio_path: 开场口播音频路径
        
        Returns:
            str: 输出视频路径
        """
        try:
            if len(image_paths) != len(audio_paths):
                raise ValueError("图像文件数量与音频文件数量不匹配")
            
            video_clips = []
            audio_clips = []
            
            # 创建开场片段
            opening_seconds = self._create_opening_segment(
                opening_image_path, opening_golden_quote, 
                opening_narration_audio_path, video_clips
            )
            
            # 创建主要视频片段
            self._create_main_segments(image_paths, audio_paths, video_clips, audio_clips)
            
            # 连接所有视频片段
            print("正在合成最终视频...")
            final_video = concatenate_videoclips(video_clips, method="compose")
            
            # 添加字幕
            final_video = self._add_subtitles(final_video, script_data, enable_subtitles, 
                                            audio_clips, opening_seconds)
            
            # 调整口播音量
            final_video = self._adjust_narration_volume(final_video, narration_volume)
            
            # 添加视觉效果
            final_video = self._add_visual_effects(final_video, image_paths)
            
            # 添加背景音乐
            final_video = self._add_background_music(final_video, bgm_audio_path, bgm_volume)
            
            # 输出视频
            self._export_video(final_video, output_path)
            
            # 释放资源
            self._cleanup_resources(video_clips, audio_clips, final_video)
            
            print(f"最终视频已保存: {output_path}")
            return output_path
            
        except Exception as e:
            raise ValueError(f"视频合成错误: {e}")
    
    def _create_opening_segment(self, opening_image_path: Optional[str], 
                              opening_golden_quote: Optional[str],
                              opening_narration_audio_path: Optional[str], 
                              video_clips: List) -> float:
        """创建开场片段"""
        opening_seconds = 0.0
        opening_voice_clip = None
        
        # 计算开场时长
        try:
            if opening_narration_audio_path and os.path.exists(opening_narration_audio_path):
                opening_voice_clip = AudioFileClip(opening_narration_audio_path)
                hold_after = float(getattr(config, "OPENING_HOLD_AFTER_NARRATION_SECONDS", 2.0))
                opening_seconds = float(opening_voice_clip.duration) + max(0.0, hold_after)
        except Exception as e:
            logger.warning(f"开场口播音频加载失败: {e}，将退回固定时长开场")
            opening_voice_clip = None
        
        if opening_image_path and os.path.exists(opening_image_path) and opening_seconds > 1e-3:
            try:
                print("正在创建开场片段…")
                opening_base = ImageClip(opening_image_path).with_duration(opening_seconds)
                
                # 添加开场金句
                if opening_golden_quote and opening_golden_quote.strip():
                    opening_clip = self._add_opening_quote(opening_base, opening_golden_quote, opening_seconds)
                else:
                    opening_clip = opening_base
                
                # 绑定开场音频
                if opening_voice_clip is not None:
                    try:
                        opening_clip = opening_clip.with_audio(opening_voice_clip)
                    except Exception as e:
                        logger.warning(f"为开场片段绑定音频失败: {e}")
                
                # 添加渐隐效果
                opening_clip = self._add_opening_fade_effect(opening_clip, opening_voice_clip, opening_seconds)
                
                video_clips.append(opening_clip)
                
            except Exception as e:
                logger.warning(f"开场片段生成失败: {e}，将跳过开场")
        
        return opening_seconds
    
    def _add_opening_quote(self, opening_base, opening_golden_quote: str, opening_seconds: float):
        """添加开场金句文字叠加"""
        subtitle_config = config.SUBTITLE_CONFIG.copy()
        resolved_font = self.resolve_font_path(subtitle_config.get("font_family"))
        
        quote_style = getattr(config, "OPENING_QUOTE_STYLE", {}) or {}
        base_font = int(config.SUBTITLE_CONFIG.get("font_size", 36))
        scale = float(quote_style.get("font_scale", 1.3))
        font_size = int(quote_style.get("font_size", base_font * scale))
        text_color = quote_style.get("color", config.SUBTITLE_CONFIG.get("color", "white"))
        stroke_color = quote_style.get("stroke_color", config.SUBTITLE_CONFIG.get("stroke_color", "black"))
        stroke_width = int(quote_style.get("stroke_width", max(3, int(config.SUBTITLE_CONFIG.get("stroke_width", 3)))))
        pos = quote_style.get("position", ("center", "center"))
        
        # 处理文字换行
        try:
            max_chars = int(quote_style.get("max_chars_per_line", 18))
            max_q_lines = int(quote_style.get("max_lines", 4))
            candidate_lines = self.split_text_for_subtitle(opening_golden_quote, max_chars, max_q_lines)
            wrapped_quote = "\n".join(candidate_lines[:max_q_lines]) if candidate_lines else opening_golden_quote
        except Exception:
            wrapped_quote = opening_golden_quote
        
        # 创建文字剪辑
        text_clip = TextClip(
            text=wrapped_quote,
            font_size=font_size,
            color=text_color,
            font=resolved_font or config.SUBTITLE_CONFIG.get("font_family"),
            stroke_color=stroke_color,
            stroke_width=stroke_width
        ).with_position(pos).with_duration(opening_seconds)
        
        return CompositeVideoClip([opening_base, text_clip])
    
    def _add_opening_fade_effect(self, opening_clip, opening_voice_clip, opening_seconds: float):
        """添加开场渐隐效果"""
        try:
            if opening_voice_clip is not None:
                hold_after = float(getattr(config, "OPENING_HOLD_AFTER_NARRATION_SECONDS", 2.0))
                if hold_after > 1e-3:
                    voice_duration = float(opening_voice_clip.duration)
                    fade_start_time = voice_duration
                    fade_duration = hold_after
                    
                    def _opening_fade_out(gf, t):
                        try:
                            if t < fade_start_time:
                                return gf(t)
                            elif t >= opening_seconds:
                                return 0.0 * gf(t)
                            else:
                                fade_progress = (t - fade_start_time) / fade_duration
                                alpha = max(0.0, 1.0 - fade_progress)
                                return alpha * gf(t)
                        except Exception:
                            return gf(t)
                    
                    opening_clip = opening_clip.transform(_opening_fade_out, keep_duration=True)
                    print(f"🎬 已为开场片段添加{hold_after}s渐隐效果")
        except Exception as e:
            logger.warning(f"开场片段渐隐效果添加失败: {e}")
        
        return opening_clip
    
    def _create_main_segments(self, image_paths: List[str], audio_paths: List[str], 
                            video_clips: List, audio_clips: List):
        """创建主要视频片段"""
        for i, (image_path, audio_path) in enumerate(zip(image_paths, audio_paths)):
            print(f"正在处理第{i+1}段视频...")
            
            # 加载音频获取时长
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # 创建图像剪辑
            image_clip = ImageClip(image_path).with_duration(duration)
            
            # 组合图像和音频
            video_clip = image_clip.with_audio(audio_clip)
            video_clips.append(video_clip)
            audio_clips.append(audio_clip)
    
    def _add_subtitles(self, final_video, script_data: Dict[str, Any], enable_subtitles: bool, 
                      audio_clips: List, opening_seconds: float):
        """添加字幕"""
        effective_subtitles = bool(enable_subtitles) and bool(getattr(config, "SUBTITLE_CONFIG", {}).get("enabled", True))
        if effective_subtitles and script_data:
            print("正在添加字幕...")
            try:
                subtitle_config = config.SUBTITLE_CONFIG.copy()
                subtitle_config["video_size"] = final_video.size
                subtitle_config["segment_durations"] = [ac.duration for ac in audio_clips]
                subtitle_config["offset_seconds"] = opening_seconds
                subtitle_clips = self.create_subtitle_clips(script_data, subtitle_config)
                
                if subtitle_clips:
                    final_video = CompositeVideoClip([final_video] + subtitle_clips)
                    print(f"已添加 {len(subtitle_clips)} 个字幕剪辑")
                else:
                    print("未生成任何字幕剪辑")
            except Exception as e:
                logger.warning(f"添加字幕失败: {str(e)}，继续生成无字幕视频")
        
        return final_video
    
    def _adjust_narration_volume(self, final_video, narration_volume: float):
        """调整口播音量"""
        try:
            if final_video.audio is not None and narration_volume is not None:
                narration_audio = final_video.audio
                if isinstance(narration_volume, (int, float)) and abs(float(narration_volume) - 1.0) > 1e-9:
                    try:
                        # MoviePy 1.x
                        narration_audio = narration_audio.volumex(float(narration_volume))
                    except Exception:
                        try:
                            # MoviePy 2.x unified transform
                            narration_audio = narration_audio.transform(lambda gf, t: float(narration_volume) * gf(t), keep_duration=True)
                        except Exception:
                            pass
                    final_video = final_video.with_audio(narration_audio)
                    print(f"🔊 口播音量调整为: {float(narration_volume)}")
        except Exception as e:
            logger.warning(f"口播音量调整失败: {str(e)}，将使用原始音量")
        
        return final_video
    
    def _add_visual_effects(self, final_video, image_paths: List[str]):
        """添加视觉效果（开场渐显和片尾渐隐）"""
        # 开场渐显
        try:
            fade_in_seconds = float(getattr(config, "OPENING_FADEIN_SECONDS", 0.0))
            if fade_in_seconds > 1e-3:
                def _fade_in_frame(gf, t):
                    try:
                        alpha = min(1.0, max(0.0, float(t) / float(fade_in_seconds)))
                    except Exception:
                        alpha = 1.0
                    return alpha * gf(t)
                
                final_video = final_video.transform(_fade_in_frame, keep_duration=True)
                print(f"🎬 已添加开场渐显 {fade_in_seconds}s")
        except Exception as e:
            logger.warning(f"开场渐显效果添加失败: {e}")
        
        # 片尾渐隐
        try:
            tail_seconds = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
            if isinstance(image_paths, list) and len(image_paths) > 0 and tail_seconds > 1e-3:
                last_image_path = image_paths[-1]
                tail_clip = ImageClip(last_image_path).with_duration(tail_seconds)
                
                def _fade_frame(gf, t):
                    try:
                        alpha = max(0.0, 1.0 - float(t) / float(tail_seconds))
                    except Exception:
                        alpha = 0.0
                    return alpha * gf(t)
                
                tail_clip = tail_clip.transform(_fade_frame, keep_duration=True)
                final_video = concatenate_videoclips([final_video, tail_clip], method="compose")
                print(f"🎬 已添加片尾静帧 {tail_seconds}s 并渐隐")
        except Exception as e:
            logger.warning(f"片尾静帧添加失败: {e}")
        
        return final_video
    
    def _add_background_music(self, final_video, bgm_audio_path: Optional[str], bgm_volume: float):
        """添加背景音乐"""
        if not bgm_audio_path or not os.path.exists(bgm_audio_path):
            if bgm_audio_path:
                print(f"⚠️ 背景音乐文件不存在: {bgm_audio_path}")
            else:
                print("ℹ️ 未指定背景音乐文件")
            return final_video
        
        try:
            print(f"🎵 开始处理背景音乐: {bgm_audio_path}")
            bgm_clip = AudioFileClip(bgm_audio_path)
            print(f"🎵 BGM加载成功，时长: {bgm_clip.duration:.2f}秒")
            
            # 调整BGM音量
            if isinstance(bgm_volume, (int, float)) and abs(float(bgm_volume) - 1.0) > 1e-9:
                try:
                    bgm_clip = bgm_clip.volumex(float(bgm_volume))
                except Exception:
                    try:
                        bgm_clip = bgm_clip.transform(lambda gf, t: float(bgm_volume) * gf(t), keep_duration=True)
                    except Exception:
                        pass
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
        
        except Exception as e:
            print(f"❌ 背景音乐处理异常: {str(e)}")
            logger.warning(f"背景音乐处理失败: {str(e)}，将继续生成无背景音乐的视频")
        
        return final_video
    
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
                    return bgm_clip.subclip(0, target_duration)

            # 手动平铺：重复拼接 + 末段精确裁剪
            clips = []
            accumulated = 0.0
            # 先整段重复
            while accumulated + unit_duration <= target_duration - 1e-6:
                clips.append(bgm_clip.subclip(0, unit_duration))
                accumulated += unit_duration
            # 末段裁剪
            remaining = max(0.0, target_duration - accumulated)
            if remaining > 1e-6:
                clips.append(bgm_clip.subclip(0, remaining))

            looped = concatenate_audioclips(clips)
            print(f"🎵 BGM长度适配完成（manual loop），最终时长: {looped.duration:.2f}秒")
            return looped

        except Exception as e:
            print(f"⚠️ 背景音乐长度适配失败: {e}，将不添加BGM继续生成")
            logger.warning(f"背景音乐循环/裁剪失败: {e}")
            return None
    
    def _apply_audio_effects(self, bgm_clip, final_video):
        """应用音频效果（Ducking和淡出）"""
        # 自动Ducking
        if getattr(config, "AUDIO_DUCKING_ENABLED", False) and final_video.audio is not None:
            try:
                bgm_clip = self._apply_ducking_effect(bgm_clip, final_video)
            except Exception as e:
                logger.warning(f"自动Ducking失败: {e}，将使用恒定音量BGM")
        
        # 片尾淡出
        try:
            total_dur = float(final_video.duration)
            fade_tail = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
            fade_gain = self._create_linear_fade_out_gain(total_dur, fade_tail)
            bgm_clip = bgm_clip.transform(
                lambda gf, t: ((fade_gain(t)[:, None]) if hasattr(t, "__len__") else fade_gain(t)) * gf(t),
                keep_duration=True,
            )
            print(f"🎚️ 已添加BGM片尾{fade_tail}s淡出")
        except Exception as e:
            logger.warning(f"BGM淡出应用失败: {e}")
        
        return bgm_clip
    
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
        def _gain_lookup(t_any):
            def _lookup_scalar(ts: float) -> float:
                if ts <= 0.0:
                    return float(gains[0])
                if ts >= total_dur:
                    return float(gains[-1])
                idx = int(ts * env_fps)
                idx = max(0, min(idx, gains.shape[0] - 1))
                return float(gains[idx])
            
            if hasattr(t_any, "__len__"):
                return np.array([_lookup_scalar(float(ts)) for ts in t_any])
            return _lookup_scalar(float(t_any))
        
        # 应用时间变增益
        bgm_clip = bgm_clip.transform(
            lambda gf, t: (
                (_gain_lookup(t)[:, None] if hasattr(t, "__len__") else _gain_lookup(t))
                * gf(t)
            ),
            keep_duration=True,
        )
        print(f"🎚️ 已启用自动Ducking（strength={strength}, smooth={smooth_sec}s）")
        
        return bgm_clip
    
    def _create_linear_fade_out_gain(self, total: float, tail: float):
        """创建线性淡出增益函数"""
        cutoff = max(0.0, total - tail)
        
        def _gain_any(t_any):
            def _scalar(ts: float) -> float:
                if ts <= cutoff:
                    return 1.0
                if ts >= total:
                    return 0.0
                return max(0.0, 1.0 - (ts - cutoff) / tail)
            
            if hasattr(t_any, "__len__"):
                return np.array([_scalar(float(ts)) for ts in t_any])
            return _scalar(float(t_any))
        
        return _gain_any
    
    def _export_video(self, final_video, output_path: str):
        """导出视频"""
        moviepy_logger = 'bar'
        
        try:
            # 优先尝试macOS硬件编码
            final_video.write_videofile(
                output_path,
                fps=15,
                codec='h264_videotoolbox',
                audio_codec='aac',
                bitrate='5M',
                ffmpeg_params=['-pix_fmt', 'yuv420p', '-movflags', '+faststart'],
                logger=moviepy_logger
            )
        except Exception as e:
            print(f"⚠️ 硬件编码不可用或失败，回退到软件编码: {e}")
            # 回退到软件编码
            final_video.write_videofile(
                output_path,
                fps=15,
                codec='libx264',
                audio_codec='aac',
                preset='veryfast',
                threads=os.cpu_count() or 4,
                ffmpeg_params=['-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'],
                logger=moviepy_logger
            )
    
    def _cleanup_resources(self, video_clips: List, audio_clips: List, final_video):
        """释放资源"""
        for clip in video_clips:
            clip.close()
        for aclip in audio_clips:
            aclip.close()
        final_video.close()
    
    def create_subtitle_clips(self, script_data: Dict[str, Any], 
                            subtitle_config: Dict[str, Any] = None) -> List:
        """创建字幕剪辑列表"""
        if subtitle_config is None:
            subtitle_config = config.SUBTITLE_CONFIG.copy()
        
        subtitle_clips = []
        current_time = float(subtitle_config.get("offset_seconds", 0.0))
        
        logger.info("开始创建字幕剪辑...")
        
        # 解析字体
        resolved_font = self.resolve_font_path(subtitle_config.get("font_family"))
        if not resolved_font:
            logger.warning("未能解析到可用中文字体")
        
        # 读取视频尺寸
        video_size = subtitle_config.get("video_size", (1280, 720))
        video_width, video_height = video_size
        
        segment_durations = subtitle_config.get("segment_durations", [])
        
        # 标点替换模式
        punctuation_pattern = r"[-.,!?;:\"，。！？；：（）()\[\]{}【】—…–、]+"
        
        for i, segment in enumerate(script_data["segments"], 1):
            content = segment["content"]
            
            # 获取时长
            duration = None
            if isinstance(segment_durations, list) and len(segment_durations) >= i:
                duration = float(segment_durations[i-1])
            if duration is None:
                duration = float(segment.get("estimated_duration", 0))
            
            logger.debug(f"处理第{i}段字幕，时长: {duration}秒")
            
            # 分割文本
            subtitle_texts = self.split_text_for_subtitle(
                content,
                subtitle_config["max_chars_per_line"],
                subtitle_config["max_lines"]
            )
            
            # 计算每行字幕时长
            subtitle_start_time = current_time
            line_durations = self._calculate_subtitle_durations(subtitle_texts, duration)
            
            for subtitle_text, subtitle_duration in zip(subtitle_texts, line_durations):
                try:
                    # 处理标点
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
    
    def _calculate_subtitle_durations(self, subtitle_texts: List[str], total_duration: float) -> List[float]:
        """计算每行字幕的显示时长"""
        if len(subtitle_texts) == 0:
            return [total_duration]
        
        lengths = [max(1, len(t)) for t in subtitle_texts]
        total_len = sum(lengths)
        line_durations = []
        acc = 0.0
        
        for idx, L in enumerate(lengths):
            if idx < len(lengths) - 1:
                d = total_duration * (L / total_len)
                line_durations.append(d)
                acc += d
            else:
                line_durations.append(max(0.0, total_duration - acc))
        
        return line_durations
    
    def _create_subtitle_clips_internal(self, display_text: str, start_time: float, duration: float,
                                       subtitle_config: Dict, resolved_font: Optional[str], 
                                       video_width: int, video_height: int) -> List:
        """内部字幕剪辑创建函数"""
        clips_to_add = []
        position = subtitle_config["position"]
        margin_bottom = int(subtitle_config.get("margin_bottom", 0))
        anchor_x = position[0] if isinstance(position, tuple) else "center"
        
        # 创建主要文字剪辑
        main_clip = TextClip(
            text=display_text,
            font_size=subtitle_config["font_size"],
            color=subtitle_config["color"],
            font=resolved_font or subtitle_config["font_family"],
            stroke_color=subtitle_config["stroke_color"],
            stroke_width=subtitle_config["stroke_width"]
        )
        
        # 添加背景条（需要先计算，确定文字位置）
        bg_color = subtitle_config.get("background_color")
        bg_opacity = float(subtitle_config.get("background_opacity", 0))
        if bg_color and bg_opacity > 0.0:
            bg_height = int(
                subtitle_config["font_size"] * subtitle_config.get("max_lines", 2)
                + subtitle_config.get("line_spacing", 10) + 4
            )
            text_width = main_clip.w
            bg_padding = int(subtitle_config.get("background_padding", 20))
            bg_width = text_width + bg_padding
            
            # 背景位置
            y_bg = max(0, video_height - margin_bottom - bg_height)
            bg_clip = ColorClip(size=(bg_width, bg_height), color=bg_color)
            if hasattr(bg_clip, "with_opacity"):
                bg_clip = bg_clip.with_opacity(bg_opacity)
            bg_clip = bg_clip.with_position(("center", y_bg)).with_start(start_time).with_duration(duration)
            
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
        
        main_clip = main_clip.with_position(main_pos).with_start(start_time).with_duration(duration)
        
        # 添加阴影
        if subtitle_config.get("shadow_enabled", False):
            shadow_color = subtitle_config.get("shadow_color", "black")
            shadow_offset = subtitle_config.get("shadow_offset", (2, 2))
            shadow_x = main_pos[0] if isinstance(main_pos[0], int) else 0
            shadow_y = main_pos[1] if isinstance(main_pos[1], int) else 0
            
            try:
                shadow_pos = (shadow_x + shadow_offset[0], shadow_y + shadow_offset[1])
            except:
                shadow_pos = main_pos
            
            shadow_clip = TextClip(
                text=display_text,
                font_size=subtitle_config["font_size"],
                color=shadow_color,
                font=resolved_font or subtitle_config["font_family"]
            ).with_position(shadow_pos).with_start(start_time).with_duration(duration)
            
            clips_to_add.extend([shadow_clip, main_clip])
        else:
            clips_to_add.append(main_clip)
        
        return clips_to_add
    
    def split_text_for_subtitle(self, text: str, max_chars_per_line: int = 20, max_lines: int = 2) -> List[str]:
        """将长文本分割为适合字幕显示的短句"""
        if len(text) <= max_chars_per_line:
            return [text]
        
        # 第一层：按主要标点切分
        heavy_punctuation = ['。', '！', '？', '.', '!', '?', '，', ',', '；', ';']
        segments = []
        current_segment = ""
        
        for char in text:
            current_segment += char
            if char in heavy_punctuation:
                segments.append(current_segment.strip())
                current_segment = ""
        
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        # 第二层：处理超长片段
        final_parts = []
        for segment in segments:
            if len(segment) <= max_chars_per_line:
                final_parts.append(segment)
            else:
                # 按逗号进一步切分
                comma_parts = []
                light_punctuation = ['、', ';', '；']
                current_part = ""
                
                for char in segment:
                    current_part += char
                    if char in light_punctuation and len(current_part) >= max_chars_per_line * 0.6:
                        comma_parts.append(current_part.strip())
                        current_part = ""
                
                if current_part.strip():
                    comma_parts.append(current_part.strip())
                
                # 第三层：硬切分
                for part in comma_parts:
                    if len(part) <= max_chars_per_line:
                        final_parts.append(part)
                    else:
                        final_parts.extend(self._split_text_evenly(part, max_chars_per_line))
        
        return final_parts
    
    def _split_text_evenly(self, text: str, max_chars_per_line: int) -> List[str]:
        """将文本均匀切分"""
        if len(text) <= max_chars_per_line:
            return [text]
        
        total_chars = len(text)
        num_segments = (total_chars + max_chars_per_line - 1) // max_chars_per_line
        
        base_length = total_chars // num_segments
        remainder = total_chars % num_segments
        
        result = []
        start = 0
        
        for i in range(num_segments):
            length = base_length + (1 if i < remainder else 0)
            end = start + length
            result.append(text[start:end])
            start = end
        
        return result
    
    def resolve_font_path(self, preferred: Optional[str]) -> Optional[str]:
        """解析字体路径"""
        if preferred and os.path.exists(preferred):
            return preferred
        
        # 常见中文字体路径
        common_fonts = [
            "/System/Library/Fonts/STHeiti Light.ttc",  # macOS
            "/System/Library/Fonts/PingFang.ttc",       # macOS
            "/Windows/Fonts/simhei.ttf",                # Windows
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
        ]
        
        for font_path in common_fonts:
            if os.path.exists(font_path):
                return font_path
        
        return None
    
    def get_image_style(self, style_name: str = "style05") -> str:
        """获取图像风格字符串（来源于 prompts.IMAGE_STYLE_PRESETS）"""
        try:
            return IMAGE_STYLE_PRESETS_PROMPTS.get(
                style_name,
                next(iter(IMAGE_STYLE_PRESETS_PROMPTS.values()))
            )
        except Exception:
            # 兜底，返回空字符串避免崩溃
            return ""