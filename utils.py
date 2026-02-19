import os

class SensitiveFilter:
    def __init__(self):
        self.keyword_chains = {}
        self.delimit = '\x00'
        # 定位到同一目录下的 sensitive_words.txt
        self.path = os.path.join(os.path.dirname(__file__), 'sensitive_words.txt')
        self._parse()

    def _parse(self):
        """加载敏感词库并构建 DFA 树"""
        if not os.path.exists(self.path):
            print(f"⚠️ Warning: Sensitive words file not found at {self.path}")
            return

        with open(self.path, encoding='utf-8') as f:
            for keyword in f:
                self._add(keyword.strip())

    def _add(self, keyword):
        """将单个词加入树中"""
        keyword = keyword.lower()  # 统一转小写，实现不区分大小写过滤
        chars = keyword.strip()
        if not chars:
            return
        level = self.keyword_chains
        for i in range(len(chars)):
            if chars[i] in level:
                level = level[chars[i]]
            else:
                if not isinstance(level, dict):
                    break
                for j in range(i, len(chars)):
                    level[chars[j]] = {}
                    last_level, last_char = level, chars[j]
                    level = level[chars[j]]
                last_level[last_char] = {self.delimit: 0}
                break
        if i == len(chars) - 1:
            level[self.delimit] = 0

    def filter(self, message, repl="*"):
        """
        过滤敏感词
        """
        if not message:
            return False, message

        message = message.lower()
        ret = []
        start = 0
        is_sensitive = False

        while start < len(message):
            level = self.keyword_chains
            step_ins = 0
            for char in message[start:]:
                if char in level:
                    step_ins += 1
                    if self.delimit not in level[char]:
                        level = level[char]
                    else:
                        # 发现敏感词
                        ret.append(repl * step_ins)
                        start += step_ins - 1
                        is_sensitive = True
                        break
                else:
                    ret.append(message[start])
                    break
            else:
                ret.append(message[start])
            start += 1

        return is_sensitive, ''.join(ret)

# 初始化一个单例对象，随项目启动加载一次即可，不用每次请求都读文件
sensitive_filter = SensitiveFilter()