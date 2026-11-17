from PySide6.QtCore import QObject, QRunnable, Signal

from app.services import weather_service


class WeatherWorkerSignals(QObject):
    # 结果字典：{city, days, geo, forecast, error}
    finished = Signal(dict)


class WeatherWorker(QRunnable):
    """在 QThreadPool 线程中执行天气请求，不阻塞 UI。"""

    def __init__(self, city: str, days: int):
        super().__init__()
        self.city = city
        self.days = days
        self.signals = WeatherWorkerSignals()

    def run(self):
        result = {
            "city": self.city,
            "days": self.days,
            "geo": None,
            "forecast": None,
            "error": None,
        }
        try:
            geo = weather_service.geocode_city(self.city)
            if not geo:
                result["error"] = f"未找到城市「{self.city}」，请检查名称"
                return
            result["geo"] = geo

            forecast = weather_service.fetch_daily_forecast(
                geo["latitude"], geo["longitude"], self.days
            )
            if not forecast:
                result["error"] = "天气数据获取失败，请检查网络连接后重试"
                return
            result["forecast"] = forecast
        except Exception as exc:  # 兜底：任何异常都不让 UI 崩
            result["error"] = f"请求发生异常：{exc}"
        finally:
            # 任何路径都只 emit 一次
            self.signals.finished.emit(result)