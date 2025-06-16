from difflib import SequenceMatcher


def diff_and_merge_strings(old_strings, new_strings, similarity_threshold=0.95):
    old_strings_map = {s.original_semantic: s for s in old_strings}
    merged_strings = []

    for new_s in new_strings:
        if new_s.original_semantic in old_strings_map:
            old_s = old_strings_map[new_s.original_semantic]
            new_s.translation = old_s.translation
            new_s.is_ignored = old_s.is_ignored
            new_s.is_reviewed = old_s.is_reviewed
            new_s.comment = old_s.comment
            merged_strings.append(new_s)
            continue

        best_match_score = 0
        best_match_old_s = None

        for old_s in old_strings:
            score = SequenceMatcher(None, new_s.original_semantic, old_s.original_semantic).ratio()
            if score > best_match_score:
                best_match_score = score
                best_match_old_s = old_s

        if best_match_score >= similarity_threshold and best_match_old_s:
            new_s.translation = best_match_old_s.translation
            new_s.is_ignored = best_match_old_s.is_ignored
            new_s.is_reviewed = False
            new_s.comment = f"[继承自相似度 {best_match_score:.2f}% 的原文] {best_match_old_s.comment}".strip()
            merged_strings.append(new_s)
            continue
        merged_strings.append(new_s)
    return merged_strings