# In services/ai_translator.py

import json
from utils.constants import DEFAULT_API_URL

try:
    import requests
except ImportError:
    requests = None

class AITranslator:
    def __init__(self, api_key, model_name="deepseek-chat", api_url=DEFAULT_API_URL):
        self.api_key = api_key
        self.api_url = api_url if api_url and api_url.strip() else DEFAULT_API_URL
        self.model_name = model_name

    def translate(self, text_to_translate, system_prompt):
        if not self.api_key:
            raise ValueError("API Key 未设置。")
        if not requests:
            raise ImportError("requests库未找到。AI翻译功能不可用。")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_translate}
            ],
            "temperature": 0.3,
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and len(result["choices"]) > 0:
                translation = result["choices"][0].get("message", {}).get("content", "").strip()
                return translation
            else:
                error_message = result.get("error", {}).get("message", "Unknown API error structure")
                if not error_message and result.get("choices") and len(result["choices"]) > 0 and "message" not in \
                        result["choices"][0]:
                    error_message = result["choices"][0].get("finish_reason",
                                                             "No content in message")
                raise Exception(f"API Error: {error_message}. Response: {result}")
        except requests.exceptions.Timeout:
            raise Exception("API请求超时。")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络错误或API请求失败: {e}")
        except json.JSONDecodeError:
            raise Exception(
                f"无法解码API响应。响应文本: {response.text if 'response' in locals() else 'No response object'}")
        except Exception as e:
            raise Exception(f"翻译时发生未知错误: {e}")

    def test_connection(self, test_text="Hello, OverWatch.", system_prompt="Translate to Chinese:"):
        try:
            # The test connection now also uses the 'translate' method
            translation = self.translate(test_text, system_prompt)
            return True, f"连接成功。测试翻译 ('{test_text}' -> '{translation[:30]}...')"
        except Exception as e:
            return False, f"连接失败: {e}"