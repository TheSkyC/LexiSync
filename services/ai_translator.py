import requests
import json
from utils import constants

class AITranslator:
    def __init__(self, api_key, model_name="deepseek-chat", api_url=constants.DEFAULT_API_URL):
        self.api_key = api_key
        self.api_url = api_url if api_url and api_url.strip() else constants.DEFAULT_API_URL
        self.model_name = model_name

    def translate(self, text_to_translate, target_language, system_prompt_template,
                  context_str="", original_context_str="", custom_instructions="", termbase_mappings=""):
        if not self.api_key:
            raise ValueError("API Key not set.")
        if not requests:
            raise ImportError("requests library not found. AI translation is unavailable.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        final_system_prompt = system_prompt_template.replace("[Target Language]", target_language)
        final_system_prompt = final_system_prompt.replace("[Custom Translate]", custom_instructions if custom_instructions.strip() else "None")
        final_system_prompt = final_system_prompt.replace("[Translated Context]", context_str if context_str.strip() else "None")
        final_system_prompt = final_system_prompt.replace("[Original Untranslated Context]", original_context_str if original_context_str.strip() else "None")
        final_system_prompt = final_system_prompt.replace("[Termbase Mappings]", termbase_mappings if termbase_mappings.strip() else "None")

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": final_system_prompt},
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
                raise Exception(f"API Error: {error_message}. Response: {result}")
        except requests.exceptions.Timeout:
            raise Exception("API request timed out.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error or API request failed: {e}")
        except json.JSONDecodeError:
            raise Exception(f"Failed to decode API response. Response text: {response.text if 'response' in locals() else 'No response object'}")
        except Exception as e:
            raise Exception(f"An unknown error occurred during translation: {e}")

    def test_connection(self, test_text="Hello, OverWatch.", target_lang="中文", system_prompt_template="Translate to [Target Language]:"):
        try:
            test_prompt = system_prompt_template.replace("[Target Language]", target_lang)
            test_prompt = test_prompt.replace("[Translated Context]", "N/A")
            test_prompt = test_prompt.replace("[Original Untranslated Context]", "N/A")
            test_prompt = test_prompt.replace("[Custom Translate]", "N/A")
            test_prompt = test_prompt.replace("[Termbase Mappings]", "N/A")

            translation = self.translate(test_text, target_lang, test_prompt)
            return True, f"Connection successful. Test translation ('{test_text}' -> '{translation[:30]}...')"
        except Exception as e:
            return False, f"Connection failed: {e}"