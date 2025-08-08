# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
from utils.constants import DEFAULT_API_URL
from utils.localization import _

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
            raise ValueError(_("API Key not set."))
        if not requests:
            raise ImportError(_("'requests' library not found. AI translation feature is unavailable."))

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

    def test_connection(self, test_text="你好，世界！", system_prompt="Translate to English:"):
        try:
            translation = self.translate(test_text, system_prompt)
            return True, f"{_('Connection successful. Test translation')} ('{test_text}' -> '{translation[:30]}...')"
        except Exception as e:
            return False, f"{_('Connection failed')}: {e}"