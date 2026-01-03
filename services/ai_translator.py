# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
from urllib.parse import urlparse, urlunparse
from utils.constants import DEFAULT_API_URL
from utils.localization import _, lang_manager

try:
    import requests
except ImportError:
    requests = None

class AITranslator:
    def __init__(self, api_key, model_name="deepseek-chat", api_url=DEFAULT_API_URL):
        self.api_key = api_key
        self.api_url = api_url if api_url and api_url.strip() else DEFAULT_API_URL
        self.model_name = model_name

    def translate(self, text_to_translate, system_prompt, temperature=None, timeout=60):
        if not self.api_key:
            raise ValueError(_("API Key not set."))
        if not requests:
            raise ImportError(_("'requests' library not found. AI translation feature is unavailable."))
        full_url = self._normalize_url(self.api_url)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        final_temp = temperature if temperature is not None else 0.3
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_translate}
            ],
            "temperature": final_temp,
        }

        try:
            response = requests.post(full_url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and len(result["choices"]) > 0:
                translation = result["choices"][0].get("message", {}).get("content", "").strip()
                return translation
            else:
                error_message = result.get("error", {}).get("message", _("Unknown API error structure"))
                if not error_message and result.get("choices") and len(result["choices"]) > 0 and "message" not in \
                        result["choices"][0]:
                    error_message = result["choices"][0].get("finish_reason",
                                                             _("No content in message"))
                raise Exception(f"{_('API Error')}: {error_message}. {_('Response')}: {result}")
        except requests.exceptions.Timeout:
            raise Exception(_("API request timed out."))
        except requests.exceptions.RequestException as e:
            raise Exception(f"{_('Network error or API request failed')}: {e}")
        except json.JSONDecodeError:
            raise Exception(
                f"{_('Could not decode API response. Response text')}: {response.text if 'response' in locals() else _('No response object')}")
        except Exception as e:
            raise Exception(f"{_('Unknown error occurred during translation')}: {e}")

    def translate_stream(self, text_to_translate, system_prompt, temperature=None, timeout=45):
        if not self.api_key: raise ValueError(_("API Key not set."))
        if not requests: raise ImportError(_("'requests' library not found."))
        full_url = self._normalize_url(self.api_url)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        final_temp = temperature if temperature is not None else 0.3
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_translate}
            ],
            "temperature": final_temp,
            "stream": True
        }

        try:
            response = requests.post(full_url, headers=headers, json=payload, timeout=timeout, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        data_str = decoded_line[6:]  # 去掉 'data: '
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data_json = json.loads(data_str)
                            delta = data_json.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise Exception(f"{_('Stream Error')}: {e}")

    def test_connection(self):
        current_ui_lang = lang_manager.get_current_language()
        source_text = "Hello, World!"
        target_lang_name = current_ui_lang
        if current_ui_lang.startswith('en'):
            source_text = "你好，世界！"
            target_lang_name = "English"


        system_prompt = f"You are a professional translator. Translate the following text to {target_lang_name}. Output ONLY the translated text, no explanations."

        try:
            translation = self.translate(source_text, system_prompt)
            return True, f"{_('Connection successful. Test translation')} ('{source_text}' -> '{translation[:30]}')"
        except Exception as e:
            return False, f"{_('Connection failed')}:\n{str(e)}"


    @staticmethod
    def _normalize_url(url):
        url = url.strip()

        if url.endswith('#'):
            return url[:-1]

        parsed = urlparse(url)
        original_path = parsed.path

        path_lower = original_path.lower().rstrip('/')

        # Case A: 已经是完整路径 (e.g., .../chat/completions 或 .../Chat/Completions)
        if path_lower.endswith('/chat/completions'):
            # 已经是完美的了，直接返回原 URL
            return url
        # Case B: 用户只写了一半 (e.g., .../v1/chat 或 .../chat)
        elif path_lower.endswith('/chat'):
            new_path = original_path.rstrip('/') + '/completions'
        else:
            new_path = original_path.rstrip('/') + '/chat/completions'

        return urlunparse(parsed._replace(path=new_path))