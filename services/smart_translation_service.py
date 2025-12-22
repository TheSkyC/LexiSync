# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import random
import json
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class SmartTranslationService:

    # 配置常量
    SAMPLING_CONFIG = {
        'default_size': 100,
        'bucket_ratios': {
            'long': 0.4,
            'medium': 0.4,
            'short': 0.2
        },
        'importance_weights': {
            'length_optimal': 3,
            'length_good': 2,
            'length_basic': 1,
            'special_chars': 2,
            'ui_verbs': 2,
            'capitalized': 1
        }
    }

    UI_VERBS = {
        'click', 'save', 'load', 'open', 'close', 'delete', 'add',
        'remove', 'edit', 'create', 'update', 'submit', 'cancel',
        'start', 'stop', 'play', 'pause', 'search', 'find', 'view',
        'select', 'choose', 'enable', 'disable', 'upload', 'download'
    }

    @staticmethod
    def intelligent_sampling(translatable_objects, sample_size=100):
        """
        智能采样算法：分层 + 词汇多样性 + 重要性加权

        Args:
            translatable_objects: 可翻译对象列表
            sample_size: 目标样本数量

        Returns:
            采样后的对象列表
        """
        if not translatable_objects:
            return []

        # 1. 预处理候选项
        candidates = SmartTranslationService._preprocess_candidates(translatable_objects)

        if not candidates:
            logger.warning("No valid candidates found after preprocessing")
            return []

        # 2. 动态分桶
        buckets = SmartTranslationService._create_dynamic_buckets(candidates)

        # 3. 计算配额
        quotas = SmartTranslationService._calculate_quotas(buckets, sample_size)

        # 4. 加权贪心采样
        final_samples = SmartTranslationService._greedy_sampling(buckets, quotas)

        # 5. 补充不足（如果需要）
        if len(final_samples) < sample_size:
            final_samples = SmartTranslationService._fill_remaining(
                candidates, final_samples, sample_size
            )

        logger.info(f"Sampling completed: {len(final_samples)}/{len(translatable_objects)} items selected")
        return final_samples

    @staticmethod
    def _preprocess_candidates(translatable_objects):
        """预处理候选项：过滤、去重、计算特征"""
        candidates = []
        seen_texts = set()

        for ts in translatable_objects:
            text = ts.original_semantic.strip()

            # 基本过滤
            if not text or text in seen_texts or len(text) < 2:
                continue
            if text.isdigit() or text.isspace():
                continue

            seen_texts.add(text)
            tokens = set(re.findall(r'\w+', text.lower()))

            if not tokens:
                continue

            # 计算重要性分数
            importance = SmartTranslationService._calculate_importance(text, tokens)

            candidates.append({
                'obj': ts,
                'text': text,
                'tokens': tokens,
                'length': len(tokens),
                'importance': importance
            })

        return candidates

    @staticmethod
    def _calculate_importance(text, tokens):
        """计算文本重要性分数"""
        weights = SmartTranslationService.SAMPLING_CONFIG['importance_weights']
        importance = 0
        word_count = len(tokens)

        # 因素1: 长度适中性（UI文本通常在3-15词之间）
        if 3 <= word_count <= 15:
            importance += weights['length_optimal']
        elif word_count > 15 or word_count == 2:
            importance += weights['length_good']
        else:
            importance += weights['length_basic']

        # 因素2: 包含特殊字符（技术术语或格式化文本）
        if re.search(r'[%{}\[\]<>]', text):
            importance += weights['special_chars']

        # 因素3: 首字母大写（可能是标题或重要UI元素）
        if text[0].isupper():
            importance += weights['capitalized']

        # 因素4: 包含UI动词（功能性文本）
        text_lower = text.lower()
        if any(verb in text_lower for verb in SmartTranslationService.UI_VERBS):
            importance += weights['ui_verbs']

        return importance

    @staticmethod
    def _create_dynamic_buckets(candidates):
        """根据实际分布创建动态分桶"""
        if not candidates:
            return {'long': [], 'medium': [], 'short': []}

        lengths = [c['length'] for c in candidates]
        avg_len = sum(lengths) / len(lengths)

        buckets = {
            'long': [c for c in candidates if c['length'] > avg_len * 1.5],
            'medium': [c for c in candidates if avg_len * 0.5 <= c['length'] <= avg_len * 1.5],
            'short': [c for c in candidates if c['length'] < avg_len * 0.5]
        }

        logger.debug(f"Bucket distribution - Long: {len(buckets['long'])}, "
                     f"Medium: {len(buckets['medium'])}, Short: {len(buckets['short'])}")

        return buckets

    @staticmethod
    def _calculate_quotas(buckets, sample_size):
        """计算各桶的配额"""
        ratios = SmartTranslationService.SAMPLING_CONFIG['bucket_ratios']

        quotas = {
            'long': max(
                int(sample_size * ratios['long']),
                min(10, len(buckets['long']))  # 至少10个长文本
            ),
            'medium': int(sample_size * ratios['medium']),
            'short': int(sample_size * ratios['short'])
        }

        return quotas

    @staticmethod
    def _greedy_sampling(buckets, quotas):
        """加权贪心采样"""
        final_samples = []
        global_seen_tokens = set()

        for bucket_name in ['long', 'medium', 'short']:
            pool = buckets[bucket_name][:]
            quota = quotas[bucket_name]

            if not pool:
                continue

            # 如果池子小于配额，全部取出
            if len(pool) <= quota:
                for c in pool:
                    final_samples.append(c['obj'])
                    global_seen_tokens.update(c['tokens'])
                continue

            # 贪心选择
            for _ in range(quota):
                if not pool:
                    break

                best_candidate = None
                best_score = -1.0

                for cand in pool:
                    # 新词数量
                    new_tokens = len(cand['tokens'] - global_seen_tokens)

                    # 综合分数 = 词汇多样性(×2) + 重要性权重
                    score = new_tokens * 2 + cand['importance']

                    if score > best_score:
                        best_score = score
                        best_candidate = cand

                if best_candidate:
                    final_samples.append(best_candidate['obj'])
                    global_seen_tokens.update(best_candidate['tokens'])
                    pool.remove(best_candidate)
                else:
                    # 如果所有候选都没有新词，随机选一个
                    if pool:
                        fallback = random.choice(pool)
                        final_samples.append(fallback['obj'])
                        pool.remove(fallback)

        return final_samples

    @staticmethod
    def _fill_remaining(candidates, current_samples, target_size):
        """补充剩余样本"""
        if len(current_samples) >= target_size:
            return current_samples

        remaining = [c['obj'] for c in candidates if c['obj'] not in current_samples]
        needed = min(target_size - len(current_samples), len(remaining))

        if needed > 0:
            current_samples.extend(random.sample(remaining, needed))

        return current_samples

    @staticmethod
    def generate_style_guide_prompt(samples, source_lang, target_lang):
        sample_texts = [ts.original_semantic for ts in samples[:50]]
        sample_text = "\n".join([f"- {text}" for text in sample_texts])

        return (
            f"You are a Senior Localization Lead analyzing {len(samples)} software/game UI texts.\n"
            f"Source Language: {source_lang}\n"
            f"Target Language: {target_lang}\n\n"

            f"Sample Texts:\n{sample_text}\n\n"

            "Create a concise Translation Style Guide (100-150 words) in this EXACT format:\n\n"

            "## Style Guide\n"
            "- **Tone**: [emotional tone, e.g., 'casual and friendly', 'formal and professional']\n"
            "- **Domain**: [specific domain, e.g., 'Gaming RPG', 'Business SaaS', 'Social Media']\n"
            "- **Formality**: [formality level, e.g., 'Use informal you/你', 'Avoid passive voice']\n"
            "- **Key Rules**: [2-3 specific translation rules]\n"
            "- **Terminology**: [strategy for proper nouns, e.g., 'Keep brand names in English']\n\n"
            "- **Recommended Temperature**: [0.1 - 1.0] (e.g., 0.3 for UI, 0.8 for creative text)\n\n"

            "## Critical Constraints:\n"
            "1. Focus ONLY on linguistic style and cultural adaptation\n"
            "2. Do NOT mention technical aspects (placeholders, HTML, variables, formatting)\n"
            "3. Be specific and actionable for translators\n"
            "4. Output ONLY the bulleted guide with the exact format above\n"
            "5. No preamble, no explanations, just the style guide"
        )

    @staticmethod
    def extract_terms_frequency_based(translatable_objects, top_n=100):
        """
        快速模式：统计高频词作为候选术语
        """
        all_text = " ".join([ts.original_semantic for ts in translatable_objects])

        words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())

        stopwords = {
            'the', 'and', 'for', 'that', 'this', 'with', 'you', 'not', 'are',
            'from', 'have', 'will', 'can', 'all', 'one', 'has', 'but', 'into'
        }

        filtered_words = [w for w in words if w not in stopwords]
        counter = Counter(filtered_words)

        return [word for word, count in counter.most_common(top_n)]

    @staticmethod
    def filter_and_translate_terms_prompt(candidate_list_str, target_lang):
        return (
            f"Here is a list of high-frequency words from a software project:\n{candidate_list_str}\n\n"
            "Task 1: Filter. Select only the words that are likely to be **domain-specific terms**, **UI elements**, or **technical jargon**. Discard common verbs/adjectives.\n"
            f"Task 2: Translate. Translate the selected terms into {target_lang}.\n\n"
            "Output a Markdown table with columns 'Source' and 'Target'. No other text."
        )

    @staticmethod
    def extract_terms_batch_prompt(text_batch):
        return (
            f"Analyze these texts:\n{text_batch}\n\n"
            "Extract key domain terms, proper nouns, and UI labels. Return as a JSON list of strings. "
            "Exclude common words. Output JSON only."
        )




    @staticmethod
    def extract_terms_prompt(samples):
        sample_texts = [ts.original_semantic for ts in samples]
        sample_text = "\n".join([f"- {text}" for text in sample_texts])

        return (
            f"Analyze these UI texts and extract domain-specific terms:\n\n"
            f"{sample_text}\n\n"

            "Task: Identify 10-25 key terms that require consistent translation:\n"
            "- Technical terms (API, Database, Server, etc.)\n"
            "- Domain-specific jargon\n"
            "- Proper nouns (product names, feature names)\n"
            "- UI elements that appear frequently\n"
            "- Acronyms and abbreviations\n\n"

            "Exclusions (DO NOT include):\n"
            "- Common words (the, is, click, button, etc.)\n"
            "- Generic verbs (open, close, save, etc.)\n"
            "- Single-character strings\n"
            "- Numbers or pure symbols\n\n"

            "Output Format Requirements:\n"
            "1. Return ONLY a valid JSON array of strings\n"
            "2. Format: [\"Term1\", \"Term2\", \"Term3\"]\n"
            "3. Do NOT wrap in markdown code blocks\n"
            "4. Do NOT add any explanatory text\n"
            "5. Output the raw JSON array only\n\n"

            "Example output:\n"
            '["Dashboard", "Authentication", "API Key", "User Profile"]'
        )

    @staticmethod
    def translate_terms_prompt(terms_list_str, target_lang):
        return (
            f"Translate these domain-specific terms into {target_lang}.\n\n"
            f"Terms to translate: {terms_list_str}\n\n"

            "Translation Requirements:\n"
            "1. Maintain professional terminology standards\n"
            "2. Keep proper nouns unchanged if commonly used internationally\n"
            "3. Use industry-standard translations where applicable\n"
            "4. Consider UI space constraints (prefer concise alternatives)\n"
            "5. Ensure consistency with common localization practices\n\n"

            "Output Format (MANDATORY):\n"
            "Create a markdown table with this EXACT format:\n\n"
            "| Source | Target |\n"
            "|--------|--------|\n"
            "| term1  | 翻译1  |\n"
            "| term2  | 翻译2  |\n\n"

            "Critical Rules:\n"
            "- Output ONLY the table, no preamble\n"
            "- No explanations before or after the table\n"
            "- Use the exact header format shown above\n"
            "- One term per row\n"
            "- Do NOT wrap in code blocks"
        )

    @staticmethod
    def clean_ai_response(response_text, expected_format="json"):
        if not response_text:
            return ""

        text = response_text.strip()

        try:
            if expected_format == "json":
                text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*```$', '', text)
                # 移除可能的前缀文本，定位到第一个 [
                if '[' in text:
                    start_idx = text.index('[')
                    text = text[start_idx:]
                # 截断到最后一个 ]
                if ']' in text:
                    end_idx = text.rindex(']') + 1
                    text = text[:end_idx]
                # 验证是否为有效JSON
                json.loads(text)

            elif expected_format == "markdown":
                text = re.sub(r'^```(?:markdown|md)?\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*```$', '', text)
                lines = text.split('\n')
                table_start = 0
                for i, line in enumerate(lines):
                    if '|' in line:
                        table_start = i
                        break

                if table_start > 0:
                    text = '\n'.join(lines[table_start:])

        except Exception as e:
            logger.warning(f"Failed to clean AI response: {e}")
            pass

        return text.strip()

    @staticmethod
    def validate_terms_json(json_str):
        try:
            cleaned = SmartTranslationService.clean_ai_response(json_str, "json")
            terms_list = json.loads(cleaned)

            if not isinstance(terms_list, list):
                return False, "Expected a JSON array"

            # 过滤无效项
            valid_terms = [
                term for term in terms_list
                if isinstance(term, str) and term.strip() and len(term.strip()) > 1
            ]

            return True, valid_terms

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"