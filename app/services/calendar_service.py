from datetime import date
from lunar_python import Solar
from lunar_python.util import HolidayUtil


def get_date_info(year: int, month: int, day: int) -> dict:
    """
    获取指定日期的详细信息。
    返回字典包含：阳历、农历、干支、生肖、节气、节日、假期等。
    """
    solar = Solar.fromYmd(year, month, day)
    lunar = solar.getLunar()

    # 1. 基础信息
    solar_str = f"{year}年{month}月{day}日"
    week_str = "星期" + "日一二三四五六"[solar.getWeek()]
    
    # 2. 农历信息
    lunar_year = lunar.getYearInGanZhi() + "年"
    lunar_month = lunar.getMonthInChinese() + "月"
    lunar_day = lunar.getDayInChinese()
    zodiac = lunar.getYearShengXiao() + "年"
    lunar_str = f"{lunar_year} {lunar_month}{lunar_day}"

    # 3. 节气
    jieqi = lunar.getJieQi()
    if not jieqi:
        # 有些日期在当天或前后一天有节气，这里简单取当天的
        jieqi = ""

    # 4. 节日（公历 + 农历）
    festivals = []
    # 农历节日
    festivals.extend(lunar.getFestivals())
    # 公历节日
    festivals.extend(solar.getFestivals())
    # 额外节气作为节日展示
    if jieqi and jieqi not in festivals:
        festivals.append(jieqi)
    
    # 去重并过滤空字符串
    festivals = list(dict.fromkeys([f for f in festivals if f]))

    # 5. 假期/调休信息
    holiday_name = ""
    is_holiday = False
    is_workday = False
    
    try:
        # HolidayUtil 获取当天假期信息
        holiday = HolidayUtil.getHoliday(year, month, day)
        if holiday:
            holiday_name = holiday.getName()
            if not holiday.isWork():
                is_holiday = True
            else:
                is_workday = True
    except Exception:
        pass

    # 判断是否周末
    is_weekend = solar.getWeek() in (0, 6)

    return {
        "solar_str": solar_str,
        "week_str": week_str,
        "lunar_str": lunar_str,
        "zodiac": zodiac,
        "jieqi": jieqi,
        "festivals": festivals,
        "holiday_name": holiday_name,
        "is_holiday": is_holiday,
        "is_workday": is_workday,
        "is_weekend": is_weekend,
        "lunar_day": lunar_day,
        "lunar_month": lunar_month,
    }


def get_month_festivals(year: int, month: int) -> dict[int, list[str]]:
    """
    获取指定月份中所有有特殊节日或节气的日期。
    返回：{ 日: ["国庆节", "寒露"] } 格式的字典。
    """
    import calendar
    _, days_in_month = calendar.monthrange(year, month)
    
    month_data = {}
    for day in range(1, days_in_month + 1):
        info = get_date_info(year, month, day)
        tags = []
        if info["jieqi"]:
            tags.append(info["jieqi"])
        if info["festivals"]:
            tags.extend(info["festivals"])
        
        # 假期（如国庆、春节）也标记出来
        if info["holiday_name"] and info["is_holiday"]:
            if info["holiday_name"] not in tags:
                tags.append(info["holiday_name"])
                
        if tags:
            month_data[day] = list(dict.fromkeys(tags))
            
    return month_data