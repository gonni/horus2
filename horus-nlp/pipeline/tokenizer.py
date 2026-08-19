from typing import List, Set
from kiwipiepy import Kiwi

class KoreanTokenizer:
    def __init__(self, user_dict_path: str = None):
        self.kiwi = Kiwi(num_workers=2)
        if user_dict_path:
            try:
                self.kiwi.load_user_dictionary(user_dict_path)
            except Exception:
                pass

        # 기본 불용어 목록
        self.stopwords: Set[str] = {
            "기자", "뉴스", "앵커", "리포트", "보도", "지난", "오늘", "내일", "관련", "대해",
            "이번", "경우", "위해", "통해", "때문", "사진", "출처", "제공", "연합뉴스", "무단",
            "전재", "배포", "금지", "댓글", "구독", "좋아요", "저작권", "일보", "신문"
        }

    def add_stopwords(self, words: List[str]):
        self.stopwords.update(words)

    def extract_nouns(self, text: str, min_length: int = 2) -> List[str]:
        if not text:
            return []
        
        result = self.kiwi.tokenize(text)
        nouns = []
        for token in result:
            # NNG: 일반명사, NNP: 고유명사, SL: 외국어(알파벳/티커)
            if token.tag in ["NNG", "NNP", "SL"]:
                word = token.form.strip()
                if len(word) >= min_length and word not in self.stopwords:
                    nouns.append(word)
        return nouns

tokenizer = KoreanTokenizer()
