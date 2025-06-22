# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
from utils.constants import STRUCTURAL, STATIC, DYNAMIC


def generate_prompt_from_structure(prompt_structure, placeholders):
    final_prompt_parts = []
    numbered_instruction_index = 1
    placeholder_pattern = re.compile(r'\[([a-zA-Z\s_]+)\]')

    for part in prompt_structure:
        if not part.get("enabled", True):
            continue

        content = part["content"]
        part_type = part["type"]

        # Check for dynamic content validity
        if part_type == DYNAMIC:
            found_placeholders = placeholder_pattern.findall(content)
            is_valid = True
            for ph in found_placeholders:
                full_ph = f"[{ph}]"
                # If a dynamic placeholder is in the content but its value is empty, skip this part
                if not placeholders.get(full_ph, "").strip():
                    is_valid = False
                    break
            if not is_valid:
                continue

        # Replace placeholders in content
        for ph_full, ph_value in placeholders.items():
            content = content.replace(ph_full, ph_value)

        if part_type == STRUCTURAL:
            final_prompt_parts.append(content)
        elif part_type in [STATIC, DYNAMIC]:
            final_prompt_parts.append(f"{numbered_instruction_index}. {content}")
            numbered_instruction_index += 1

    return "\n".join(final_prompt_parts)