import os
import re
from typing import List, Tuple

_WORD_CHAR_RE = re.compile(r"[a-z0-9_]")      # 英文单词字符
_ASCII_WORD_RE = re.compile(r"^[a-z0-9_]+$")  # 敏感词本身是否为“纯英文单词”

# ✨ 新增：Leetspeak (火星文) 映射表，防混淆变体 (例如把 a$$ 识别为 ass)
_LEET_MAP = {
    '0': 'o', '1': 'i', '3': 'e', '4': 'a',
    '5': 's', '7': 't', '@': 'a', '$': 's',
    '!': 'i'
}

class SensitiveFilter:
    def __init__(self):
        # 原始 DFA：匹配所有敏感词（含中文等）
        self.keyword_chains = {}
        # ASCII DFA：只放纯英文词（用于 normalize 去除符号后防绕过）
        self.ascii_keyword_chains = {}

        self.delimit = '\x00'
        # 确保 sensitive_words.txt 和 utils.py 在同一个目录下
        self.path = os.path.join(os.path.dirname(__file__), 'sensitive_words.txt')
        self._parse()

    def _parse(self):
        if not os.path.exists(self.path):
            print(f"⚠️ Warning: Sensitive words file not found at {self.path}")
            return

        with open(self.path, encoding='utf-8') as f:
            for keyword in f:
                kw = keyword.strip()
                if not kw:
                    continue
                self._add(kw)

    def _add(self, keyword: str):
        kw = keyword.strip().lower()
        if not kw:
            return

        # 1. 加入总 DFA (中英文全量)
        self._add_to_chain(self.keyword_chains, kw)

        # 2. 仅纯英文词加入 ASCII DFA（用于防 f*u*c*k 这种混淆）
        if _ASCII_WORD_RE.match(kw):
            self._add_to_chain(self.ascii_keyword_chains, kw)

    def _add_to_chain(self, chain: dict, keyword: str):
        level = chain
        for ch in keyword:
            if ch not in level:
                level[ch] = {}
            level = level[ch]
        level[self.delimit] = 0

    def _is_word_boundary_ok_on_text(self, text_lower: str, start: int, end: int) -> bool:
        """
        判断 [start, end) 是否是“独立单词”：左右两侧不能是 [a-z0-9_]
        核心作用：防止正常单词 class 被误杀成 cl***
        """
        left_ok = True
        right_ok = True

        if start - 1 >= 0:
            left_ok = _WORD_CHAR_RE.match(text_lower[start - 1]) is None
        if end < len(text_lower):
            right_ok = _WORD_CHAR_RE.match(text_lower[end]) is None

        return left_ok and right_ok

    def _find_matches_longest(self, text_lower: str, chain: dict) -> List[Tuple[int, int]]:
        """
        纯粹的 DFA 扫描核心，只负责找匹配，不负责逻辑判断。
        """
        matches = []
        start = 0

        while start < len(text_lower):
            level = chain
            matched_len = 0
            last_match_len = 0

            for idx in range(start, len(text_lower)):
                ch = text_lower[idx]
                if ch not in level:
                    break
                level = level[ch]
                matched_len += 1
                if self.delimit in level:
                    last_match_len = matched_len

            if last_match_len > 0:
                end = start + last_match_len
                matches.append((start, end))
                start = end
            else:
                start += 1

        return matches

    def filter(self, message: str, repl: str = "*") -> Tuple[bool, str]:
        if not message:
            return False, message

        original = message
        lower_message = message.lower()
        mask = [False] * len(original)

        # =========================================================
        # 第一阶段：普通匹配 (对原文做 DFA，处理中文和正常拼写的英文)
        # =========================================================
        normal_matches = self._find_matches_longest(lower_message, self.keyword_chains)
        
        for s, e in normal_matches:
            hit = lower_message[s:e]
            if _ASCII_WORD_RE.match(hit):
                # 英文单词需要检查原文边界
                if not self._is_word_boundary_ok_on_text(lower_message, s, e):
                    continue # 边界不干净 (比如 class)，直接跳过不打码
            
            for i in range(s, e):
                mask[i] = True

        # =========================================================
        # 第二阶段：Normalize 匹配 (降维打击 f*u*c*k / a$$ 这种混淆)
        # =========================================================
        norm_chars = []
        idx_map = []
        
        # 核心：无情剔除所有标点和空格，并进行 Leetspeak 映射
        for i, ch in enumerate(lower_message):
            # ✨ 转换 Leetspeak 字符 (比如把 '$' 变成 's')
            mapped_ch = _LEET_MAP.get(ch, ch)
            
            # 使用转换后的字符判断是否是字母/数字
            if mapped_ch.isascii() and mapped_ch.isalnum():
                norm_chars.append(mapped_ch)
                idx_map.append(i)
                
        norm = ''.join(norm_chars)

        if norm and self.ascii_keyword_chains:
            norm_matches = self._find_matches_longest(norm, self.ascii_keyword_chains)
            
            for ns, ne in norm_matches:
                # 利用 idx_map 回溯到原字符串的具体位置
                orig_s = idx_map[ns]
                orig_e_minus_1 = idx_map[ne - 1]
                orig_e = orig_e_minus_1 + 1  

                hit = norm[ns:ne]
                if _ASCII_WORD_RE.match(hit):
                    # ✨ 核心魔法：使用原字符串的上下文去验证边界！
                    if not self._is_word_boundary_ok_on_text(lower_message, orig_s, orig_e):
                        continue # 发现是 c*l*a*s*s 里的 a*s*s，直接放行

                # 验证通过，对原字符串的跨度进行精准打码 (连带中间的符号一起变成星星)
                for i in range(orig_s, orig_e):
                    mask[i] = True

        # =========================================================
        # 组装结果
        # =========================================================
        is_sensitive = any(mask)
        if not is_sensitive:
            return False, original

        filtered = ''.join(repl if mask[i] else original[i] for i in range(len(original)))
        return True, filtered

# 初始化单例：项目启动加载一次
sensitive_filter = SensitiveFilter()