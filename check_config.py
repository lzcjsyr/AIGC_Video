#!/usr/bin/env python3
"""
智能视频制作系统 - 配置检查工具
用于验证API密钥配置是否正确
"""

import os
from config import config

def check_api_keys():
    """检查API密钥配置状态"""
    print("🔍 正在检查API密钥配置...")
    print("=" * 50)
    
    # 验证API密钥
    validation = config.validate_api_keys()
    
    # 检查结果
    print("📋 API密钥配置状态：")
    for service, is_configured in validation.items():
        status = "✅ 已配置" if is_configured else "❌ 缺失"
        print(f"  {service:12}: {status}")
    
    print("\n" + "=" * 50)
    
    # 根据当前默认配置检查所需密钥
    required_keys = config.get_required_keys_for_config(
        llm_server="openrouter",
        image_server="doubao", 
        tts_server="bytedance"
    )
    
    print("🎯 当前默认配置所需的API密钥：")
    all_required_available = True
    
    for key in required_keys:
        value = getattr(config, key, None)
        is_available = bool(value)
        status = "✅ 已配置" if is_available else "❌ 缺失"
        print(f"  {key:20}: {status}")
        if not is_available:
            all_required_available = False
    
    print("\n" + "=" * 50)
    
    if all_required_available:
        print("🎉 恭喜！所有必需的API密钥都已正确配置")
        print("✨ 现在可以运行 python main.py 开始制作视频了！")
    else:
        print("⚠️  还有API密钥未配置，请按以下步骤完成配置：")
        print("\n📝 配置步骤：")
        
        if "OPENROUTER_API_KEY" in required_keys and not config.OPENROUTER_API_KEY:
            print("1. 获取OpenRouter API密钥：")
            print("   - 访问 https://openrouter.ai/")
            print("   - 注册账号并充值")
            print("   - 在API Keys页面创建密钥")
            print("   - 将密钥填入 .env 文件的 OPENROUTER_API_KEY=")
            print()
        
        if "SEEDREAM_API_KEY" in required_keys and not config.SEEDREAM_API_KEY:
            print("2. 获取火山引擎方舟API密钥：")
            print("   - 访问 https://console.volcengine.com/ark")
            print("   - 实名认证并开通服务")
            print("   - 在API密钥管理创建密钥")
            print("   - 将密钥填入 .env 文件的 SEEDREAM_API_KEY=")
            print("   - 确保已开通 Seedream 3.0 和 TTS 服务")
            print()
        
        if "BYTEDANCE_TTS_APPID" in required_keys and not config.BYTEDANCE_TTS_APPID:
            print("3. 获取字节语音合成大模型配置：")
            print("   - 访问 https://console.volcengine.com/")
            print("   - 开通语音合成服务")
            print("   - 获取APPID和ACCESS_TOKEN")
            print("   - 将配置填入 .env 文件的 BYTEDANCE_TTS_APPID= 和 BYTEDANCE_TTS_ACCESS_TOKEN=")
            print()
        
        if "AIHUBMIX_API_KEY" in required_keys and not config.AIHUBMIX_API_KEY:
            print("4. 获取aihubmix代理API密钥：")
            print("   - 访问 https://aihubmix.com/")
            print("   - 注册账号并充值")
            print("   - 获取API密钥")
            print("   - 将密钥填入 .env 文件的 AIHUBMIX_API_KEY=")
            print("   - base_url已经在配置文件中固定为 https://aihubmix.com/v1")
            print()
        
        print("5. 保存 .env 文件后重新运行此脚本验证")
    
    return all_required_available

def check_alternative_configs():
    """检查其他可用的配置方案"""
    print("\n🔄 检查其他可用的配置方案...")
    print("=" * 50)
    
    # 方案1: SiliconFlow + Bytedance
    siliconflow_keys = config.get_required_keys_for_config(
        llm_server="siliconflow",
        image_server="doubao",
        tts_server="bytedance"
    )
    siliconflow_available = all(getattr(config, key, None) for key in siliconflow_keys)
    
    # 方案2: OpenAI代理 + Bytedance
    openai_keys = config.get_required_keys_for_config(
        llm_server="openai", 
        image_server="doubao",
        tts_server="bytedance"
    )
    openai_available = all(getattr(config, key, None) for key in openai_keys)
    
    print("📋 备选配置方案：")
    
    if siliconflow_available:
        print("✅ 方案A: SiliconFlow + 豆包 - 可用")
        print("   修改 main.py 中的 llm_server='siliconflow'")
    else:
        print("❌ 方案A: SiliconFlow + 豆包 - 不可用（缺少密钥）")
    
    if openai_available:
        print("✅ 方案B: aihubmix代理 + 豆包 - 可用")
        print("   修改 main.py 中的 llm_server='openai'")
    else:
        print("❌ 方案B: aihubmix代理 + 豆包 - 不可用（缺少密钥）")

if __name__ == "__main__":
    print("🚀 智能视频制作系统 - 配置检查工具")
    print("=" * 50)
    
    try:
        is_ready = check_api_keys()
        
        if not is_ready:
            check_alternative_configs()
        
        print("\n" + "=" * 50)
        print("💡 提示：如需帮助，请查看 .env.example 文件中的详细说明")
        
    except Exception as e:
        print(f"❌ 检查过程中发生错误: {e}")
        print("💡 请确保已正确安装所有依赖包：pip install -r requirements.txt")