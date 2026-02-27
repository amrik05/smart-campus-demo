from datetime import datetime, timedelta, timezone


class DemoClock:
    def __init__(self, start_ts: datetime, speed: float = 60.0) -> None:
        self.start_ts = start_ts
        self.speed = speed
        self.ticks = 0

    def now(self) -> datetime:
        return self.start_ts + timedelta(seconds=self.ticks * self.speed)

    def tick(self) -> datetime:
        self.ticks += 1
        return self.now()


def utc_now_floor() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
