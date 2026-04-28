import time
from collections import deque
from threading import Lock

class KisThrottle:
    """KIS API 초당 20건 제한 대응 슬라이딩 윈도우 쓰로틀러"""

    def __init__(self, max_calls: int = 19, period: float = 1.0):
        self.max_calls = max_calls  # 안전 마진으로 19건 사용
        self.period = period
        self.calls = deque()
        self.lock = Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            # 윈도우 밖 타임스탬프 제거
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()

            if len(self.calls) >= self.max_calls:
                sleep_for = self.period - (now - self.calls[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)

            self.calls.append(time.monotonic())

# 전역 쓰로틀러 인스턴스 (모든 KIS 호출에서 공유)
throttle = KisThrottle()
