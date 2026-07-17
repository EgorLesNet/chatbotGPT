import os
import json
import logging
import asyncio
import re
import math
import httpx
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, NotFoundError, RateLimitError, APIStatusError
from utils.materials_db import get_materials_context
from utils.storage import get_user_rates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Правила цен для импортных материалов по стране происхождения + категории
# ---------------------------------------------------------------------------
_IMPORT_PRICE_RULES: list[dict] = [
    {"countries": ["польш", "poland", "польск"], "keywords": ["кварцвинил", "vinyl", "lvt", "ламинат", "laminate"], "min_price": 3500, "unit": "м²"},
    {"countries": ["герман", "germany", "deutsch"], "keywords": ["кварцвинил", "vinyl", "lvt", "ламинат", "laminate", "паркет", "parquet"], "min_price": 4000, "unit": "м²"},
    {"countries": ["бельги", "belgium"], "keywords": ["ламинат", "laminate", "паркет"], "min_price": 3800, "unit": "м²"},
    {"countries": ["итали", "italy", "italian"], "keywords": ["плитк", "tile", "керам", "porcel"], "min_price": 2500, "unit": "м²"},
    {"countries": ["испани", "spain", "spanish"], "keywords": ["плитк", "tile", "керам"], "min_price": 2000, "unit": "м²"},
    {"countries": ["финлянд", "finland", "финск"], "keywords": ["краск", "paint", "эмаль"], "min_price": 800, "unit": "л"},
    {"countries": ["герман", "germany", "deutsch"], "keywords": ["краск", "paint", "эмаль"], "min_price": 900, "unit": "л"},
]

_MIN_WORKS_RATIO = 0.25
_MIN_TIER_GAP_PCT = 0.25
_ECONOM_FLOOR_MAX_PRICE = 1900
_FLOOR_COVERING_KEYWORDS = ["кварцвинил", "ламинат", "линолеум", "vinyl", "laminate", "lvt", "покрытие пол", "напольн"]
_SELF_DOUBT_PHRASES = [
    "требует уточнения", "неуверен в цифрах", "приблизительно", "возможно неточно",
    "данные могут отличаться", "рекомендуется уточнить", "уточните у специалиста",
    "не могу гарантировать точность", "ориентировочные данные",
]

_CONTRACTOR_MARGIN_NOTE = (
    "Расчёт отражает стоимость материалов и прямых работ без учёта маржи подрядной организации "
    "(обычно +15–30%). Цены строительных компаний «под ключ» включают накладные расходы и прибыль."
)

# ---------------------------------------------------------------------------
# Сантехприборы по вариантам (эконом / оптимальный / премиум)
# ---------------------------------------------------------------------------
_PLUMBING_FIXTURES: dict[str, list[dict]] = {
    "эконом": [
        {"name": "Унитаз напольный", "brand": "Эконом-класс", "unit": "шт", "qty": 1, "unit_price": 5500, "total": 5500},
        {"name": "Раковина для ванной", "brand": "Эконом-класс", "unit": "шт", "qty": 1, "unit_price": 2500, "total": 2500},
        {"name": "Смеситель для ванной/душа", "brand": "Эконом-класс", "unit": "шт", "qty": 1, "unit_price": 2000, "total": 2000},
        {"name": "Смеситель для кухни", "brand": "Эконом-класс", "unit": "шт", "qty": 1, "unit_price": 1500, "total": 1500},
        {"name": "Ванна акриловая или душевой поддон", "brand": "Эконом-класс", "unit": "шт", "qty": 1, "unit_price": 8000, "total": 8000},
    ],
    "оптимальный": [
        {"name": "Унитаз напольный", "brand": "Средний класс", "unit": "шт", "qty": 1, "unit_price": 9000, "total": 9000},
        {"name": "Раковина для ванной", "brand": "Средний класс", "unit": "шт", "qty": 1, "unit_price": 4500, "total": 4500},
        {"name": "Смеситель для ванной/душа", "brand": "Средний класс", "unit": "шт", "qty": 1, "unit_price": 4500, "total": 4500},
        {"name": "Смеситель для кухни", "brand": "Средний класс", "unit": "шт", "qty": 1, "unit_price": 3000, "total": 3000},
        {"name": "Ванна акриловая или душевая кабина", "brand": "Средний класс", "unit": "шт", "qty": 1, "unit_price": 18000, "total": 18000},
    ],
    "премиум": [
        {"name": "Унитаз подвесной", "brand": "Премиум-класс", "unit": "шт", "qty": 1, "unit_price": 22000, "total": 22000},
        {"name": "Раковина встроенная", "brand": "Премиум-класс", "unit": "шт", "qty": 1, "unit_price": 12000, "total": 12000},
        {"name": "Смеситель для ванной/душа", "brand": "Премиум-класс", "unit": "шт", "qty": 1, "unit_price": 12000, "total": 12000},
        {"name": "Смеситель для кухни", "brand": "Премиум-класс", "unit": "шт", "qty": 1, "unit_price": 7000, "total": 7000},
        {"name": "Душевая кабина или ванна отдельностоящая", "brand": "Премиум-класс", "unit": "шт", "qty": 1, "unit_price": 55000, "total": 55000},
    ],
}

# ---------------------------------------------------------------------------
# Детализация электрощита по вариантам
# ---------------------------------------------------------------------------
_ELECTRICAL_PANEL_ITEMS: dict[str, list[dict]] = {
    "эконом": [
        {"name": "Щит распределительный (бокс)", "brand": "На 24 модуля", "unit": "шт", "qty": 1, "unit_price": 1500, "total": 1500},
        {"name": "Вводной автомат 40А", "brand": "IEK / EKF", "unit": "шт", "qty": 1, "unit_price": 800, "total": 800},
        {"name": "Автоматы групповые 16А", "brand": "IEK / EKF (6–8 шт)", "unit": "шт", "qty": 7, "unit_price": 350, "total": 2450},
        {"name": "УЗО 25А/30мА", "brand": "IEK / EKF", "unit": "шт", "qty": 2, "unit_price": 1200, "total": 2400},
    ],
    "оптимальный": [
        {"name": "Щит распределительный (бокс)", "brand": "Legrand / ABB на 32 модуля", "unit": "шт", "qty": 1, "unit_price": 3500, "total": 3500},
        {"name": "Вводной автомат 50А", "brand": "Legrand / ABB", "unit": "шт", "qty": 1, "unit_price": 1800, "total": 1800},
        {"name": "Автоматы групповые 16–25А", "brand": "Legrand / ABB (8 шт)", "unit": "шт", "qty": 8, "unit_price": 650, "total": 5200},
        {"name": "УЗО 25А/30мА", "brand": "Legrand / ABB", "unit": "шт", "qty": 2, "unit_price": 2500, "total": 5000},
    ],
    "премиум": [
        {"name": "Щит распределительный (бокс)", "brand": "Schneider / Hager на 48 мод.", "unit": "шт", "qty": 1, "unit_price": 8000, "total": 8000},
        {"name": "Вводной автомат 63А", "brand": "Schneider Electric", "unit": "шт", "qty": 1, "unit_price": 3500, "total": 3500},
        {"name": "Автоматы групповые 16–32А", "brand": "Schneider Electric (10 шт)", "unit": "шт", "qty": 10, "unit_price": 1200, "total": 12000},
        {"name": "УЗО/дифавтоматы 25А/30мА", "brand": "Schneider Electric", "unit": "шт", "qty": 3, "unit_price": 4500, "total": 13500},
    ],
}

# ---------------------------------------------------------------------------
# Маппинг категорий → разрешённые разделы для постобработки
# Если категория не в списке CATEGORY_ALLOWED_SECTIONS — постобработка
# не добавляет электрику/сантехнику/плинтусы автоматически.
# ---------------------------------------------------------------------------
_CATEGORY_ALLOWS_ELECTRICAL = {"wiring", "full_renovation", "kitchen", "balcony"}
_CATEGORY_ALLOWS_PLUMBING = {"plumbing", "full_renovation", "bathroom", "kitchen"}
_CATEGORY_ALLOWS_SKIRTING = {"floor", "full_renovation", "cosmetic", "kitchen", "balcony", "bathroom"}
_CATEGORY_ALLOWS_PRIMER_PLASTER = {"full_renovation", "ceiling", "painting", "wallpaper", "cosmetic", "bathroom", "kitchen"}

# ---------------------------------------------------------------------------
# Категорийные системные промпты — строго по выбранному типу
# ---------------------------------------------------------------------------
_CATEGORY_SYSTEM_PROMPTS: dict[str, str] = {
    "floor": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для замены напольного покрытия.\n"
        "ЗАПРЕЩЕНО включать: электрику, сантехнику, отделку стен/потолков, двери, окна.\n"
        "Разрешённые разделы: демонтаж старого покрытия, подготовка основания (стяжка/выравнивание если нужно), "
        "грунтовка, укладка финишного покрытия (ламинат/кварцвинил/паркет/плитка/линолеум), установка плинтусов, порожки.\n"
        "Эконом: покрытие не дороже 1 900 ₽/м². Для каждого типа покрытия — отдельная строка работы и материала.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом. Удаляй строки с qty=0 или unit_price=0.\n"
    ),
    "wiring": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для замены электропроводки.\n"
        "ЗАПРЕЩЕНО включать: сантехнику, отделку стен/полов/потолков, двери, окна, напольные покрытия.\n"
        "Разрешённые разделы: демонтаж старой проводки, штробление стен и потолков, прокладка кабелей "
        "(освещение и розетки), заделка штроб, монтаж щитка, установка розеток и выключателей.\n"
        "Обязательно раздельными строками: кабель ВВГнг-LS 3×2.5, кабель ВВГнг-LS 3×1.5, бокс щитка, "
        "вводной автомат, групповые автоматы (6–8 шт), УЗО (2 шт), розетки, выключатели.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "ceiling": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для ремонта/замены потолка.\n"
        "ЗАПРЕЩЕНО включать: сантехнику, электрощиток, отделку стен, полы, двери.\n"
        "Разрешённые разделы: демонтаж старого покрытия, грунтовка, штукатурка/шпаклёвка, покраска "
        "ИЛИ натяжной потолок (монтаж профиля + полотно + светильники) ИЛИ ГКЛ (каркас + листы + шпаклёвка + покраска).\n"
        "Штукатурка потолка на 20–40% дороже стен. Перед штукатуркой — грунтовка обязательна.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "wallpaper": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для поклейки обоев.\n"
        "ЗАПРЕЩЕНО включать: сантехнику, электрику, полы, потолки (кроме побелки если упомянуто), двери.\n"
        "Разрешённые разделы: снятие старых обоев, грунтовка, шпаклёвка (если нужна), поклейка обоев.\n"
        "Обои рассчитывай по площади с запасом +10% на раппорт. Клей — по норме расхода.\n"
        "Эконом: бумажные/флизелиновые 300–800 ₽/рулон. Оптимальный: 800–2000 ₽/рулон. Премиум: 2000+ ₽/рулон.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "tiles": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для укладки плитки.\n"
        "ЗАПРЕЩЕНО включать: электрощиток, проводку, сантехприборы (унитаз/ванну), напольные ламинат/кварцвинил.\n"
        "Разрешённые разделы: подготовка основания, гидроизоляция (обязательно при влажных помещениях), "
        "укладка плитки на пол, укладка плитки на стены (если применимо), затирка швов, уголки/бордюры/плинтусы.\n"
        "Материалы: плитка (м²), клей плиточный (кг, норма 5–8 кг/м²), гидроизоляция, затирка, уголки.\n"
        "Эконом: 500–1500 ₽/м². Оптимальный: 1500–3000 ₽/м². Премиум: керамогранит от 2500 ₽/м².\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "bathroom": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для ремонта ванной комнаты.\n"
        "ЗАПРЕЩЕНО включать: ремонт других помещений, замену окон/дверей вне ванной, проводку по всей квартире.\n"
        "Разрешённые разделы: демонтаж, гидроизоляция, плитка (пол + стены), трубы и сантехника, "
        "вентилятор/освещение, чистовой монтаж.\n"
        "Обязательные материалы: плитка напольная, плитка настенная, клей, гидроизоляция, затирка, "
        "трубы и фитинги, унитаз, раковина, смеситель для ванной/душа, ванна или душевая кабина.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "kitchen": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для ремонта кухни.\n"
        "ЗАПРЕЩЕНО включать: ремонт других комнат, сантехнику вне кухни, электрощиток всей квартиры.\n"
        "Разрешённые разделы: подготовка стен, фартук (плитка или панели), пол, потолок, "
        "розетки для техники на кухне, мойка и смеситель.\n"
        "Обязательные материалы: фартук (плитка или панели), напольное покрытие, клей/грунтовка/затирка, "
        "краска для потолка, кабель+розетки для техники, мойка кухонная, смеситель для кухни.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "doors_windows": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для замены дверей и/или окон.\n"
        "ЗАПРЕЩЕНО включать: сантехнику, электрику, напольные покрытия, отделку стен/потолков.\n"
        "Разрешённые разделы: демонтаж старых конструкций, монтаж новых дверей/окон, "
        "откосы (внутренние и наружные), добор/наличники, подоконник, фурнитура.\n"
        "Если упоминаются и двери и окна — считай оба раздела. Используй стандартные размеры если не указаны.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "plumbing": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для сантехнических работ.\n"
        "ЗАПРЕЩЕНО включать: электрощиток, отделку стен/полов/потолков, напольные покрытия, обои.\n"
        "Разрешённые разделы: разводка труб ХВС/ГВС, канализация, установка сантехприборов, счётчики.\n"
        "Обязательные материалы раздельными строками: трубы ХВС (м), трубы ГВС (м), фитинги/коллектор, "
        "счётчики воды, сантехприборы (по описанию пользователя).\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "painting": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для покраски стен и/или потолков.\n"
        "ЗАПРЕЩЕНО включать: сантехнику, электрику, напольные покрытия, двери, окна, обои.\n"
        "Разрешённые разделы: подготовка поверхности, грунтовка (1–2 слоя), шпаклёвка (если нужна), покраска (2 слоя).\n"
        "Материалы с нормами расхода: грунтовка (0.1–0.15 л/м²), шпаклёвка (1–1.5 кг/м²), краска (0.12–0.18 л/м² × 2 слоя).\n"
        "Эконом: 250–600 ₽/л. Оптимальный: Dulux/Tikkurila 700–1200 ₽/л. Премиум: 1200–3000 ₽/л.\n"
        "Потолок и стены считай раздельно. Штукатурка потолка на 20–40% дороже стен.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "balcony": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для ремонта балкона/лоджии.\n"
        "ЗАПРЕЩЕНО включать: ремонт других помещений, замену сантехники, капитальную проводку квартиры.\n"
        "Разрешённые разделы: остекление (если нужно), утепление (стены+пол+потолок), "
        "отделка стен (вагонка/панели ПВХ/ГКЛ), пол (ламинат/кварцвинил/плитка), "
        "электрика балкона (розетка + освещение).\n"
        "Перила и ограждение — только если упомянуты пользователем.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "full_renovation": (
        "Ты — опытный прораб-сметчик в России. Составляй смету для ПОЛНОГО РЕМОНТА ПОД КЛЮЧ.\n"
        "ОБЯЗАТЕЛЬНЫ все разделы в порядке этапов:\n"
        "1) Демонтаж и вывоз мусора\n"
        "2) Черновые работы стен (штукатурка, выравнивание)\n"
        "3) Черновые работы полов (стяжка)\n"
        "4) Черновые работы потолков (штукатурка)\n"
        "5) Электрика: штробление, кабели (ВВГнг-LS 3×2.5 + 3×1.5), щиток с автоматами (6–8 шт), УЗО (2 шт), розетки, выключатели — всё раздельными строками\n"
        "6) Сантехника: разводка труб ХВС/ГВС/канализации, установка приборов, трубы/фитинги, унитаз, раковина, смеситель ванной, смеситель кухни, ванна/душевая\n"
        "7) Чистовая отделка стен (обои или покраска)\n"
        "8) Чистовые полы (финишное покрытие + плинтусы)\n"
        "9) Потолки чистовые (покраска или натяжной)\n"
        "10) Двери, финальная уборка\n"
        "АРИФМЕТИКА: qty × unit_price = total. total_works и total_materials = суммы строк. "
        "Электрощиток: бокс, вводной автомат, групповые автоматы, УЗО — раздельными строками, не 'комплект'.\n"
    ),
    "cosmetic": (
        "Ты — опытный прораб-сметчик в России. Составляй смету СТРОГО для косметического ремонта.\n"
        "ЗАПРЕЩЕНО включать: замену труб, электрощиток, стяжку, снос стен, замену сантехприборов.\n"
        "Разрешённые разделы: подготовка поверхностей (шпаклёвка/грунтовка), отделка стен (покраска или обои), "
        "покраска/плёнка потолка, замена напольного покрытия (без стяжки, поверх существующего), "
        "замена розеток/выключателей (только лицевые панели, если упомянуто), плинтусы.\n"
        "АРИФМЕТИКА: qty × unit_price = total. Пересчитай суммы перед выводом.\n"
    ),
    "other": (
        "Ты — опытный прораб-сметчик в России. Составляй детальную смету строго под описание пользователя.\n"
        "Определи масштаб задачи из текста. Включай ТОЛЬКО разделы, относящиеся к описанной задаче.\n"
        "Не добавляй разделы, которые пользователь не упоминал.\n"
        "АРИФМЕТИКА: qty × unit_price = total. total_works и total_materials = суммы строк. "
        "Удаляй строки с qty=0 или unit_price=0.\n"
    ),
}

# JSON-шаблон для ответа (общий для всех категорий)
_JSON_SCHEMA = (
    'Верни ONLY raw JSON:\n'
    '{"summary":"","cost_min":0,"cost_max":0,"currency":"₽","variants":['
    '{"name":"Эконом","style":"Бюджетный","total_works":0,"total_materials":0,"total":0,"budget":"",'
    '"works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"pros":"","cons":""},'
    '{"name":"Оптимальный","style":"Средний","total_works":0,"total_materials":0,"total":0,"budget":"",'
    '"works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"pros":"","cons":""},'
    '{"name":"Премиум","style":"Дизайнерский","total_works":0,"total_materials":0,"total":0,"budget":"",'
    '"works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],'
    '"pros":"","cons":""}],'
    '"risks":""}'
)

_COMMON_RULES = (
    "\nОБЩИЕ ПРАВИЛА:\n"
    "- Эконом, Оптимальный и Премиум различаются качеством, брендами и объёмом решений.\n"
    "- Работы ≥ 30% от итоговой суммы варианта.\n"
    "- Оптимальный на 20–30% дороже Эконома, Премиум на 25–50% дороже Оптимального.\n"
    "- cost_min/cost_max = min/max total среди вариантов.\n"
    "- Никогда не включай фразы 'требует уточнения', 'неуверен в цифрах', 'рекомендуется уточнить'.\n"
    "- В поле risks обязательно добавь: 'Расчёт без учёта маржи подрядчика (+15–30%). "
    "Цены компаний под ключ включают накладные расходы.'\n"
    "- Не оставляй пустые pros/cons. Не отдавай вариант с 0 материалов.\n"
)


def _build_category_system_prompt(repair_type: str, system_hint: str = "") -> str:
    base = _CATEGORY_SYSTEM_PROMPTS.get(repair_type, _CATEGORY_SYSTEM_PROMPTS["other"])
    prompt = base + _COMMON_RULES + "\n" + _JSON_SCHEMA
    if system_hint:
        prompt += "\n\nСПЕЦИАЛЬНЫЕ ИНСТРУКЦИИ:\n" + system_hint
    return prompt


# Компактная версия для Groq/local
def _build_category_system_prompt_compact(repair_type: str, system_hint: str = "") -> str:
    base = _CATEGORY_SYSTEM_PROMPTS.get(repair_type, _CATEGORY_SYSTEM_PROMPTS["other"])
    # Берём первые 3 абзаца базового промпта (до 600 символов)
    short_base = base[:600].rsplit("\n", 1)[0] if len(base) > 600 else base
    prompt = (
        short_base
        + "\nРаботы ≥ 30% итога. Оптимальный > Эконом на 20%+, Премиум > Оптимальный на 25%+. "
        "В risks: 'Расчёт без учёта маржи подрядчика (+15–30%).' "
        "Отвечай ONLY чистым JSON: "
        + _JSON_SCHEMA.replace("Верни ONLY raw JSON:\n", "")
    )
    if system_hint:
        prompt += "\n" + system_hint
    return prompt


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LLAMACPP_DEFAULT_URL = "http://localhost:11434"

GROQ_DEFAULT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

HTTPX_TIMEOUT_LOCAL = httpx.Timeout(connect=5.0, read=600.0, write=15.0, pool=5.0)
HTTPX_TIMEOUT_CLOUD = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0)

RETRY_DELAYS = [3, 10]
MAX_RATE_LIMIT_WAIT = 30
JSON_MAX_RETRIES = 2

_BLOCKLIST_KEYWORDS = ["content-safety", "moderation", "guard", "embedding", "rerank", "classify", "whisper", "tts"]
_free_models_cache: list[str] = []


def _is_chat_model(model_id: str) -> bool:
    return not any(kw in model_id.lower() for kw in _BLOCKLIST_KEYWORDS)


def _is_local(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


def _is_groq(base_url: str) -> bool:
    return "groq.com" in base_url


async def _check_llamacpp() -> tuple[str, str] | None:
    base_url = os.getenv("LLAMACPP_URL", LLAMACPP_DEFAULT_URL).rstrip("/")
    model_name = os.getenv("LLAMACPP_MODEL", "local-model")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/health")
            if resp.status_code == 200:
                logger.info("llama.cpp server is up: %s", model_name)
                return model_name, f"{base_url}/v1"
    except Exception:
        pass
    logger.info("llama.cpp not available at %s", base_url)
    return None


def _get_groq_models() -> list[tuple[str, str]]:
    if not os.getenv("GROQ_API_KEY", "").strip():
        return []
    custom = os.getenv("GROQ_MODEL", "").strip()
    models = [custom] if custom else GROQ_DEFAULT_MODELS
    return [(m, GROQ_BASE_URL) for m in models]


async def fetch_free_models(api_key: str) -> list[str]:
    global _free_models_cache
    if _free_models_cache:
        return _free_models_cache
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        free = [
            m["id"] for m in data.get("data", [])
            if (m["id"].endswith(":free") or str(m.get("pricing", {}).get("prompt", "1")) == "0")
            and _is_chat_model(m["id"])
        ]
        priority = ["llama", "gemma", "qwen", "nemotron", "hermes", "mistral"]
        free.sort(key=lambda mid: next((i for i, kw in enumerate(priority) if kw in mid), len(priority)))
        _free_models_cache = free[:10]
        logger.info("Loaded %d free chat models from OpenRouter", len(_free_models_cache))
        return _free_models_cache
    except Exception:
        logger.warning("OpenRouter unavailable, skipping cloud models")
        return []


def _make_client(base_url: str, api_key: str) -> AsyncOpenAI:
    local = _is_local(base_url)
    groq = _is_groq(base_url)
    if local:
        effective_key = "local"
    elif groq:
        effective_key = os.getenv("GROQ_API_KEY", "")
    else:
        effective_key = api_key
    return AsyncOpenAI(
        api_key=effective_key,
        base_url=base_url,
        timeout=HTTPX_TIMEOUT_LOCAL if local else HTTPX_TIMEOUT_CLOUD,
        max_retries=0,
        default_headers={} if (local or groq) else {
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        },
    )


async def _get_model_chain(api_key: str) -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    for groq_entry in _get_groq_models():
        chain.append(groq_entry)
    local = await _check_llamacpp()
    if local:
        chain.append(local)
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    if primary:
        chain.append((primary, OPENROUTER_BASE_URL))
    for m in await fetch_free_models(api_key):
        if not any(m == c[0] for c in chain):
            chain.append((m, OPENROUTER_BASE_URL))
    if not chain:
        logger.error("No models available")
    return chain


def _build_rates_context(user_rates: list[dict]) -> str:
    if not user_rates:
        return ""
    lines = ["Расценки мастера по работам (используй их в первую очередь):"]
    for item in user_rates:
        lines.append(f"- {item.get('name','')}: {item.get('unit_price',0)} ₽/{item.get('unit','')} ({item.get('note','')})")
    return "\n".join(lines)


def _build_user_message(situation: str, project: dict | None, materials_context: str, rates_context: str, repair_type: str) -> str:
    parts = [f"Задача: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}, тип: {project.get('project_type', '')}, {project.get('area_m2', '')} м²")
        if project.get("notes"):
            parts.append(f"Заметки: {project['notes']}")
    if repair_type:
        parts.append(f"Категория работ: {repair_type} — составляй смету ТОЛЬКО по этой категории, не добавляй другие разделы.")
    if rates_context:
        parts.append(rates_context)
    if materials_context:
        parts.append(materials_context)
    return "\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "").strip()
    start = raw.find("{")
    if start == -1:
        return raw
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(raw[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return raw[start:]


def _norm_int(val) -> int:
    try:
        return int(float(str(val).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _ceil_int(val: float) -> int:
    try:
        return int(math.ceil(float(val)))
    except (TypeError, ValueError):
        return 0


def _extract_consumption(text: str) -> float | None:
    if not text:
        return None
    s = str(text).lower().replace(",", ".")
    patterns = [
        r"расход\s*(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*кг/м[2²]",
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*кг/м[2²]",
        r"расход\s*(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*л/м[2²]",
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*л/м[2²]",
    ]
    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            a = float(m.group(1))
            b = float(m.group(2)) if m.group(2) else None
            return (a + b) / 2 if b else a
    return None


def _extract_pack_weight_kg(text: str) -> float | None:
    if not text:
        return None
    s = str(text).lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*кг", s)
    return float(m.group(1)) if m else None


def _find_related_work_qty(works: list[dict], keywords: list[str]) -> int:
    max_qty = 0
    for w in works:
        name = (w.get("name") or "").lower()
        if any(k in name for k in keywords):
            max_qty = max(max_qty, _norm_int(w.get("qty") or 0))
    return max_qty


def _filter_zero_rows(rows: list[dict]) -> list[dict]:
    filtered = []
    for row in rows:
        qty = _norm_int(row.get("qty") or 0)
        unit_price = _norm_int(row.get("unit_price") or 0)
        total = _norm_int(row.get("total") or 0)
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if qty <= 0 or unit_price <= 0 or total <= 0:
            logger.info("Dropping zero/empty row '%s'", name)
            continue
        filtered.append(row)
    return filtered


def _detect_floor_type_from_works(works: list[dict]) -> str | None:
    joined = " ".join((w.get("name") or "").lower() for w in works)
    if "ламинат" in joined or "laminate" in joined:
        return "ламинат"
    if "кварцвинил" in joined or "vinyl" in joined or "lvt" in joined:
        return "кварцвинил"
    if "паркет" in joined:
        return "паркет"
    if "линолеум" in joined:
        return "линолеум"
    if "плитк" in joined or "керам" in joined or "tile" in joined:
        return "плитка"
    return None


def _fix_floor_name_sync(works: list[dict], materials: list[dict]) -> list[dict]:
    floor_type = _detect_floor_type_from_works(works)
    if not floor_type:
        return materials
    cleaned = []
    for m in materials:
        name = (m.get("name") or "").lower()
        if any(kw in name for kw in _FLOOR_COVERING_KEYWORDS):
            if floor_type == "ламинат" and ("кварцвинил" in name or "vinyl" in name or "lvt" in name):
                m["name"] = re.sub(r"(?i)кварцвинил|vinyl|lvt", "Ламинат", m.get("name") or "Ламинат")
            elif floor_type == "кварцвинил" and ("ламинат" in name or "laminate" in name):
                m["name"] = re.sub(r"(?i)ламинат|laminate", "Кварцвинил", m.get("name") or "Кварцвинил")
        cleaned.append(m)
    return cleaned


def _fix_line_arithmetic(rows: list[dict]) -> list[dict]:
    for row in rows:
        qty = _norm_int(row.get("qty") or 0)
        unit_price = _norm_int(row.get("unit_price") or 0)
        expected = qty * unit_price
        actual = _norm_int(row.get("total") or 0)
        if expected > 0 and actual != expected:
            logger.info(
                "Arithmetic fix '%s': total %d -> %d (qty=%d × price=%d)",
                row.get("name"), actual, expected, qty, unit_price
            )
            row["total"] = expected
    return rows


def _fix_floor_area_sync(
    works: list[dict],
    materials: list[dict],
    project_area: float | None,
    repair_type: str,
) -> tuple[list[dict], list[dict]]:
    # Синхронизацию площадей делаем только для категорий с напольными работами
    if repair_type not in ("floor", "full_renovation", "cosmetic", "kitchen", "bathroom", "balcony", "tiles"):
        return works, materials

    floor_mats = [
        m for m in materials
        if any(kw in (m.get("name") or "").lower() for kw in _FLOOR_COVERING_KEYWORDS)
        and ("м²" in (m.get("unit") or "") or "м2" in (m.get("unit") or "") or (m.get("unit") or "") in ("", "м"))
    ]
    if not floor_mats:
        return works, materials

    if project_area and len(floor_mats) > 1:
        total_floor_qty = sum(_norm_int(m.get("qty")) for m in floor_mats)
        if total_floor_qty != _ceil_int(project_area):
            scale = project_area / max(total_floor_qty, 1)
            remaining = _ceil_int(project_area)
            for i, m in enumerate(floor_mats):
                if i < len(floor_mats) - 1:
                    new_qty = max(1, round(_norm_int(m.get("qty")) * scale))
                    m["qty"] = new_qty
                    remaining -= new_qty
                else:
                    m["qty"] = max(1, remaining)
                m["total"] = m["qty"] * _norm_int(m.get("unit_price") or 0)

    for m in floor_mats:
        mat_name = (m.get("name") or "").lower()
        mat_qty = _norm_int(m.get("qty"))
        has_install_work = any(
            ("укладк" in (w.get("name") or "").lower() or "монтаж" in (w.get("name") or "").lower())
            and any(kw in (w.get("name") or "").lower() for kw in _FLOOR_COVERING_KEYWORDS)
            and _norm_int(w.get("qty")) == mat_qty
            for w in works
        )
        if not has_install_work and mat_qty > 0:
            if "плитк" in mat_name or "tile" in mat_name or "керам" in mat_name:
                work_name, unit_price = "Укладка плитки", 900
            elif "кварцвинил" in mat_name or "vinyl" in mat_name or "lvt" in mat_name:
                work_name, unit_price = "Укладка кварцвинила", 400
            elif "ламинат" in mat_name or "laminate" in mat_name:
                work_name, unit_price = "Укладка ламината", 350
            elif "паркет" in mat_name or "parquet" in mat_name:
                work_name, unit_price = "Укладка паркетной доски", 600
            else:
                work_name, unit_price = "Укладка напольного покрытия", 350
            works.append({"name": work_name, "unit": "м²", "qty": mat_qty, "unit_price": unit_price, "total": mat_qty * unit_price})
    return works, materials


def _ensure_skirting_boards(
    works: list[dict],
    materials: list[dict],
    project_area: float | None,
    repair_type: str,
) -> tuple[list[dict], list[dict]]:
    # Плинтусы добавляем ТОЛЬКО для категорий, где это уместно
    if repair_type not in _CATEGORY_ALLOWS_SKIRTING:
        return works, materials
    has_floor_work = any(any(kw in (w.get("name") or "").lower() for kw in _FLOOR_COVERING_KEYWORDS) for w in works)
    has_skirting = (
        any("плинтус" in (w.get("name") or "").lower() for w in works)
        or any("плинтус" in (m.get("name") or "").lower() for m in materials)
    )
    if not has_floor_work or has_skirting:
        return works, materials
    length = max(20, _ceil_int((project_area or 40) * 0.9))
    works.append({"name": "Установка плинтусов", "unit": "м.п.", "qty": length, "unit_price": 180, "total": length * 180})
    materials.append({"name": "Плинтус напольный", "brand": "ПВХ/МДФ", "unit": "м.п.", "qty": length, "unit_price": 220, "total": length * 220})
    return works, materials


def _get_tier_key(variant_name: str) -> str:
    name = (variant_name or "").lower()
    if "эконом" in name or "бюджет" in name:
        return "эконом"
    if "премиум" in name or "дизайн" in name or "люкс" in name:
        return "премиум"
    return "оптимальный"


def _ensure_electrical_section(
    works: list[dict],
    materials: list[dict],
    repair_type: str,
    project_area: float | None,
    variant_name: str = "",
) -> tuple[list[dict], list[dict]]:
    # Электрику добавляем ТОЛЬКО для разрешённых категорий
    if repair_type not in _CATEGORY_ALLOWS_ELECTRICAL:
        return works, materials

    elec_work_count = sum(1 for w in works if any(k in (w.get("name") or "").lower() for k in ["элект", "кабел", "штроб", "щит", "автомат", "узо", "розет", "выключ"]))
    elec_mat_count = sum(1 for m in materials if any(k in (m.get("name") or "").lower() for k in ["кабел", "щит", "автомат", "узо", "розет", "выключ", "вводной"]))
    cable_len = max(20, _ceil_int((project_area or 20) * 2.2))

    if elec_work_count < 2:
        works.append({"name": "Штробление и прокладка кабеля", "unit": "м", "qty": cable_len, "unit_price": 250, "total": cable_len * 250})
        works.append({"name": "Установка розеток и выключателей", "unit": "шт", "qty": max(6, _ceil_int((project_area or 20) / 3)), "unit_price": 450, "total": max(6, _ceil_int((project_area or 20) / 3)) * 450})
        if repair_type in ("full_renovation", "wiring"):
            works.append({"name": "Сборка и монтаж щитка", "unit": "шт", "qty": 1, "unit_price": 6500, "total": 6500})

    has_main_breaker = any("вводной" in (m.get("name") or "").lower() for m in materials)
    has_group_breakers = any("групповые" in (m.get("name") or "").lower() or "автомат" in (m.get("name") or "").lower() for m in materials)
    has_rcd = any("узо" in (m.get("name") or "").lower() or "дифавтомат" in (m.get("name") or "").lower() for m in materials)
    has_panel_box = any(("щит" in (m.get("name") or "").lower()) or ("бокс" in (m.get("name") or "").lower()) for m in materials)

    tier = _get_tier_key(variant_name)
    panel_items = _ELECTRICAL_PANEL_ITEMS.get(tier, _ELECTRICAL_PANEL_ITEMS["оптимальный"])

    if repair_type in ("full_renovation", "wiring"):
        if not has_panel_box:
            materials.append(dict(panel_items[0]))
        if not has_main_breaker:
            materials.append(dict(panel_items[1]))
        if not has_group_breakers:
            materials.append(dict(panel_items[2]))
        if not has_rcd:
            materials.append(dict(panel_items[3]))

    if not any("кабел" in (m.get("name") or "").lower() for m in materials):
        materials.append({"name": "Кабель ВВГнг-LS", "brand": "3x2.5 / 3x1.5", "unit": "м", "qty": cable_len, "unit_price": 95, "total": cable_len * 95})
    if not any("розет" in (m.get("name") or "").lower() for m in materials):
        socket_qty = max(6, _ceil_int((project_area or 20) / 3))
        materials.append({"name": "Розетки", "brand": "Белые, скрытый монтаж", "unit": "шт", "qty": socket_qty, "unit_price": 250, "total": socket_qty * 250})
    if not any("выключ" in (m.get("name") or "").lower() for m in materials):
        switch_qty = max(2, _ceil_int((project_area or 20) / 10))
        materials.append({"name": "Выключатели", "brand": "Одноклавишные/двухклавишные", "unit": "шт", "qty": switch_qty, "unit_price": 280, "total": switch_qty * 280})

    return works, materials


def _ensure_plumbing_section(
    works: list[dict],
    materials: list[dict],
    repair_type: str,
    variant_name: str = "",
) -> tuple[list[dict], list[dict]]:
    # Сантехнику добавляем ТОЛЬКО для разрешённых категорий
    if repair_type not in _CATEGORY_ALLOWS_PLUMBING:
        return works, materials

    has_plumbing_work = any(any(k in (w.get("name") or "").lower() for k in ["сантех", "труб", "вод", "канализ", "установк", "подключ"]) for w in works)
    has_pipe_mat = any(any(k in (m.get("name") or "").lower() for k in ["труб", "фитинг", "коллектор"]) for m in materials)

    has_toilet = any("унитаз" in (m.get("name") or "").lower() for m in materials)
    has_sink = any("раковин" in (m.get("name") or "").lower() or "мойка" in (m.get("name") or "").lower() for m in materials)
    has_faucet_bath = any("смеситель" in (m.get("name") or "").lower() and ("ванн" in (m.get("name") or "").lower() or "душ" in (m.get("name") or "").lower()) for m in materials)
    has_faucet_kitchen = any("смеситель" in (m.get("name") or "").lower() and "кухн" in (m.get("name") or "").lower() for m in materials)
    has_bath_shower = any("ванн" in (m.get("name") or "").lower() or "душев" in (m.get("name") or "").lower() for m in materials)

    tier = _get_tier_key(variant_name)
    fixtures = _PLUMBING_FIXTURES.get(tier, _PLUMBING_FIXTURES["оптимальный"])

    points = 5
    if not has_plumbing_work:
        works.append({"name": "Разводка труб водоснабжения и канализации", "unit": "точка", "qty": points, "unit_price": 4500, "total": points * 4500})
    has_install_work = any(any(k in (w.get("name") or "").lower() for k in ["установк", "подключ", "монтаж сантех"]) for w in works)
    if not has_install_work:
        works.append({"name": "Установка и подключение сантехприборов", "unit": "шт", "qty": points, "unit_price": 2000, "total": points * 2000})

    if not has_pipe_mat:
        materials.append({"name": "Трубы и фитинги для сантехники", "brand": "На 4-6 точек", "unit": "компл", "qty": 1, "unit_price": 18000, "total": 18000})

    if repair_type in ("full_renovation", "bathroom", "plumbing"):
        if not has_toilet:
            materials.append(dict(fixtures[0]))
        if not has_sink:
            materials.append(dict(fixtures[1]))
        if not has_faucet_bath:
            materials.append(dict(fixtures[2]))
        if not has_bath_shower:
            materials.append(dict(fixtures[4]))
    if repair_type in ("full_renovation", "kitchen") and not has_sink:
        materials.append({"name": "Мойка кухонная", "brand": "Нержавеющая сталь / композит", "unit": "шт", "qty": 1, "unit_price": 6000 if tier != "эконом" else 3500, "total": 6000 if tier != "эконом" else 3500})
    if repair_type in ("full_renovation", "kitchen") and not has_faucet_kitchen:
        materials.append(dict(fixtures[3]))

    return works, materials


def _ensure_contractor_margin_note(out: dict) -> dict:
    risks = out.get("risks") or ""
    if "маржи" not in risks.lower() and "накладн" not in risks.lower() and "+15" not in risks:
        if risks:
            out["risks"] = risks.rstrip() + " " + _CONTRACTOR_MARGIN_NOTE
        else:
            out["risks"] = _CONTRACTOR_MARGIN_NOTE
    return out


def _fix_self_doubt_phrases(variant: dict) -> dict:
    fields_to_clean = ["pros", "cons", "budget", "summary"]
    for field in fields_to_clean:
        val = variant.get(field) or ""
        if not val:
            continue
        val_lower = val.lower()
        if any(phrase in val_lower for phrase in _SELF_DOUBT_PHRASES):
            cleaned = val
            for phrase in _SELF_DOUBT_PHRASES:
                sentences = re.split(r'(?<=[.!?])\s+', cleaned)
                sentences = [s for s in sentences if phrase not in s.lower()]
                cleaned = " ".join(sentences).strip()
            variant[field] = cleaned if cleaned else variant.get(field, "")
    for row in (variant.get("works") or []) + (variant.get("materials") or []):
        name = row.get("name") or ""
        if any(phrase in name.lower() for phrase in _SELF_DOUBT_PHRASES):
            row["name"] = re.sub(
                r"\s*[\(\[]?(?:" + "|".join(re.escape(p) for p in _SELF_DOUBT_PHRASES) + r")[^\)\]]*[\)\]]?\s*",
                "", name, flags=re.IGNORECASE
            ).strip()
    return variant


def _fix_econom_floor_cap(variant: dict) -> dict:
    if (variant.get("name") or "").lower() not in ("эконом", "econom", "economy", "бюджетный"):
        return variant
    for m in (variant.get("materials") or []):
        name = (m.get("name") or "").lower()
        unit = (m.get("unit") or "").lower()
        is_floor = any(kw in name for kw in _FLOOR_COVERING_KEYWORDS)
        is_per_sqm = "м²" in unit or "м2" in unit or unit in ("", "м")
        if not (is_floor and is_per_sqm):
            continue
        unit_price = _norm_int(m.get("unit_price") or 0)
        if unit_price > _ECONOM_FLOOR_MAX_PRICE:
            m["unit_price"] = _ECONOM_FLOOR_MAX_PRICE
            qty = max(_norm_int(m.get("qty")), 1)
            m["total"] = qty * _ECONOM_FLOOR_MAX_PRICE
    return variant


def _fix_import_prices(materials: list[dict]) -> list[dict]:
    for m in materials:
        name = (m.get("name") or "").lower()
        brand = (m.get("brand") or "").lower()
        text = f"{name} {brand}"
        unit = (m.get("unit") or "").lower()
        unit_price = _norm_int(m.get("unit_price") or 0)
        if unit_price <= 0:
            continue
        for rule in _IMPORT_PRICE_RULES:
            country_match = any(c in text for c in rule["countries"])
            keyword_match = any(k in text for k in rule["keywords"])
            if not (country_match and keyword_match):
                continue
            rule_unit = rule["unit"]
            unit_ok = (rule_unit == "м²" and ("м²" in unit or "м2" in unit or unit in ("", "м")))
            unit_ok = unit_ok or (rule_unit == "л" and "л" in unit)
            unit_ok = unit_ok or (rule_unit not in ("м²", "л"))
            if not unit_ok:
                continue
            if unit_price < rule["min_price"]:
                m["unit_price"] = rule["min_price"]
                qty = max(_norm_int(m.get("qty")), 1)
                m["total"] = qty * rule["min_price"]
            break
    return materials


def _ensure_primer_before_plaster(
    works: list[dict],
    materials: list[dict],
    currency: str,
    repair_type: str,
) -> tuple[list[dict], list[dict]]:
    if repair_type not in _CATEGORY_ALLOWS_PRIMER_PLASTER:
        return works, materials
    has_plaster_work = any("штукатур" in (w.get("name") or "").lower() for w in works)
    has_plaster_mat = any("штукатур" in (m.get("name") or "").lower() for m in materials)
    if not (has_plaster_work or has_plaster_mat):
        return works, materials
    plaster_area = _find_related_work_qty(works, ["штукатур"])
    if plaster_area <= 0:
        return works, materials
    if not any("грунт" in (w.get("name") or "").lower() for w in works):
        works.append({"name": "Грунтовка основания перед штукатуркой", "unit": "м²", "qty": plaster_area, "unit_price": 80, "total": plaster_area * 80})
    if not any("грунт" in (m.get("name") or "").lower() for m in materials):
        consumption, pack_l, unit_price = 0.15, 10.0, 900
        qty = _ceil_int((plaster_area * consumption) / pack_l)
        materials.append({"name": f"Грунтовка глубокого проникновения, расход {consumption} л/м²", "brand": "Канистра 10 л", "unit": "шт", "qty": qty, "unit_price": unit_price, "total": qty * unit_price})
    return works, materials


def _fix_ceiling_plaster_prices(works: list[dict]) -> list[dict]:
    wall_prices = []
    for w in works:
        name = (w.get("name") or "").lower()
        if "штукатур" in name and "стен" in name and _norm_int(w.get("unit_price")) > 0:
            wall_prices.append(_norm_int(w.get("unit_price")))
    if not wall_prices:
        return works
    ceiling_min = _ceil_int(max(wall_prices) * 1.2)
    for w in works:
        name = (w.get("name") or "").lower()
        if "штукатур" in name and "потол" in name:
            qty = _norm_int(w.get("qty"))
            if _norm_int(w.get("unit_price")) < ceiling_min:
                w["unit_price"] = ceiling_min
                w["total"] = qty * ceiling_min
    return works


def _fix_consumable_materials(works: list[dict], materials: list[dict]) -> list[dict]:
    plaster_area = _find_related_work_qty(works, ["штукатур"])
    if plaster_area <= 0:
        return materials
    for m in materials:
        name = (m.get("name") or "").lower()
        brand = (m.get("brand") or "").lower()
        text = f"{name} {brand}"
        if "штукатур" not in text:
            continue
        consumption = _extract_consumption(text)
        if consumption is None:
            consumption = 8.5
            m["brand"] = (m.get("brand") or "") + f" · Расход {consumption} кг/м²"
        pack_weight = _extract_pack_weight_kg(text)
        if pack_weight is None:
            pack_weight = 30.0
            m["brand"] = (m.get("brand") or "") + f" · Мешок {int(pack_weight)} кг"
        needed_qty = _ceil_int((plaster_area * consumption) / pack_weight)
        if needed_qty > _norm_int(m.get("qty")):
            m["qty"] = needed_qty
        m["total"] = m["qty"] * _norm_int(m.get("unit_price"))
    return materials


def _ensure_nonempty_variant_fields(variant: dict) -> dict:
    if not variant.get("pros"):
        variant["pros"] = "Сбалансирован по задачам и бюджету."
    if not variant.get("cons"):
        variant["cons"] = "Стоимость уточняется по финальному проекту."
    if not (variant.get("materials") or []):
        variant["materials"] = [{"name": "Материалы уточняются по проекту", "brand": "Предварительный расчёт", "unit": "компл", "qty": 1, "unit_price": 1, "total": 1}]
    return variant


def _fix_works_ratio(works: list[dict], materials: list[dict]) -> list[dict]:
    total_works = sum(_norm_int(w.get("total")) for w in works)
    total_materials = sum(_norm_int(m.get("total")) for m in materials)
    total = total_works + total_materials
    if total <= 0 or total_works <= 0:
        return works
    ratio = total_works / total
    if ratio >= _MIN_WORKS_RATIO:
        return works
    target_works = _ceil_int(_MIN_WORKS_RATIO * total_materials / (1 - _MIN_WORKS_RATIO))
    scale = target_works / total_works
    for w in works:
        old = _norm_int(w.get("total"))
        if old <= 0:
            continue
        new_total = _ceil_int(old * scale)
        w["total"] = new_total
        qty = max(_norm_int(w.get("qty")), 1)
        w["unit_price"] = _ceil_int(new_total / qty)
    return works


def _fix_variant_completeness(variants: list[dict]) -> list[dict]:
    if len(variants) < 2:
        return variants
    ref_works_count = max(len(v.get("works") or []) for v in variants[:2])
    ref_mats_count = max(len(v.get("materials") or []) for v in variants[:2])
    min_works_required = ref_works_count
    min_mats_required = _ceil_int(ref_mats_count * 0.8)
    for i, v in enumerate(variants):
        if i < 2:
            continue
        works_count = len(v.get("works") or [])
        mats_count = len(v.get("materials") or [])
        if works_count < min_works_required or mats_count < min_mats_required:
            v["_incomplete"] = True
    return variants


def _enforce_variant_order(variants: list[dict]) -> list[dict]:
    prev_total = 0
    for i, v in enumerate(variants):
        total_works = sum(_norm_int(w.get("total")) for w in (v.get("works") or []))
        total_materials = sum(_norm_int(m.get("total")) for m in (v.get("materials") or []))
        total = total_works + total_materials

        if i > 0 and prev_total > 0:
            min_required = _ceil_int(prev_total * (1 + _MIN_TIER_GAP_PCT))
            if total < min_required:
                diff = min_required - total
                if v.get("works"):
                    works_total = sum(_norm_int(w.get("total")) for w in v["works"])
                    if works_total > 0:
                        for w in v["works"]:
                            share = _norm_int(w.get("total")) / works_total
                            addition = _ceil_int(diff * share)
                            w["total"] = _norm_int(w.get("total")) + addition
                            qty = max(_norm_int(w.get("qty")), 1)
                            w["unit_price"] = _ceil_int(w["total"] / qty)
                        new_works_total = sum(_norm_int(w.get("total")) for w in v["works"])
                        remainder = min_required - (new_works_total + total_materials)
                        if remainder > 0:
                            last_w = v["works"][-1]
                            last_w["total"] = _norm_int(last_w.get("total")) + remainder
                            qty = max(_norm_int(last_w.get("qty")), 1)
                            last_w["unit_price"] = _ceil_int(last_w["total"] / qty)
                    else:
                        v["works"].append({"name": "Дополнительные работы сегмента", "unit": "компл", "qty": 1, "unit_price": diff, "total": diff})
                elif v.get("materials"):
                    last_m = v["materials"][-1]
                    last_m["total"] = _norm_int(last_m.get("total")) + diff
                    qty = max(_norm_int(last_m.get("qty")), 1)
                    last_m["unit_price"] = _ceil_int(last_m["total"] / qty)
                else:
                    v.setdefault("works", []).append({"name": "Дополнительные работы сегмента", "unit": "компл", "qty": 1, "unit_price": diff, "total": diff})
                total_works = sum(_norm_int(w.get("total")) for w in (v.get("works") or []))
                total_materials = sum(_norm_int(m.get("total")) for m in (v.get("materials") or []))
                total = total_works + total_materials

        v["total_works"] = total_works
        v["total_materials"] = total_materials
        v["total"] = total
        v["budget"] = f"{total:,} ₽".replace(",", " ")
        prev_total = total
    return variants


def _normalize_result(data: dict, project: dict | None = None, repair_type: str = "other") -> dict:
    out = {
        "summary": data.get("summary") or data.get("description") or "",
        "cost_min": 0, "cost_max": 0,
        "currency": data.get("currency") or "₽",
        "risks": data.get("risks") or data.get("notes") or "",
        "variants": [],
    }

    project_area: float | None = None
    if project:
        try:
            project_area = float(project.get("area_m2") or 0) or None
        except (TypeError, ValueError):
            project_area = None

    for v in (data.get("variants") or data.get("options") or [])[:3]:
        variant_name = v.get("name") or ""
        works = []
        for w in (v.get("works") or []):
            qty = _norm_int(w.get("qty") or 0)
            unit_price = _norm_int(w.get("unit_price") or 0)
            total = _norm_int(w.get("total") or 0)
            if total <= 0 and qty > 0 and unit_price > 0:
                total = qty * unit_price
            works.append({"name": w.get("name") or "", "unit": w.get("unit") or "", "qty": qty, "unit_price": unit_price, "total": total})

        works = _fix_ceiling_plaster_prices(works)

        materials = []
        for m in (v.get("materials") or []):
            qty = _norm_int(m.get("qty") or 0)
            unit_price = _norm_int(m.get("unit_price") or 0)
            total = _norm_int(m.get("total") or 0)
            if total <= 0 and qty > 0 and unit_price > 0:
                total = qty * unit_price
            materials.append({"name": m.get("name") or "", "brand": m.get("brand") or "", "unit": m.get("unit") or "", "qty": qty, "unit_price": unit_price, "total": total})

        # Арифметика
        works = _fix_line_arithmetic(works)
        materials = _fix_line_arithmetic(materials)
        materials = _fix_import_prices(materials)
        materials = _fix_consumable_materials(works, materials)

        # Категорийно-зависимые постобработки
        works, materials = _ensure_primer_before_plaster(works, materials, out["currency"], repair_type)
        works, materials = _fix_floor_area_sync(works, materials, project_area, repair_type)
        materials = _fix_floor_name_sync(works, materials)
        works, materials = _ensure_skirting_boards(works, materials, project_area, repair_type)
        works, materials = _ensure_electrical_section(works, materials, repair_type, project_area, variant_name)
        works, materials = _ensure_plumbing_section(works, materials, repair_type, variant_name)
        works = _fix_works_ratio(works, materials)
        works = _filter_zero_rows(works)
        materials = _filter_zero_rows(materials)

        total_works = sum(w["total"] for w in works)
        total_materials = sum(m["total"] for m in materials)
        total = total_works + total_materials

        variant = {
            "name": variant_name,
            "style": v.get("style") or "",
            "total_works": total_works, "total_materials": total_materials, "total": total,
            "budget": v.get("budget") or f"{total:,} ₽".replace(",", " "),
            "works": works, "materials": materials,
            "pros": v.get("pros") or "", "cons": v.get("cons") or "",
        }
        variant = _fix_econom_floor_cap(variant)
        variant = _fix_self_doubt_phrases(variant)
        out["variants"].append(_ensure_nonempty_variant_fields(variant))

    out["variants"] = _fix_variant_completeness(out["variants"])
    out["variants"] = _enforce_variant_order(out["variants"])
    out = _ensure_contractor_margin_note(out)

    totals = [v["total"] for v in out["variants"] if v["total"] > 0]
    if totals:
        out["cost_min"] = min(totals)
        out["cost_max"] = max(totals)
    else:
        out["cost_min"] = _norm_int(data.get("cost_min") or data.get("min_cost") or 0)
        out["cost_max"] = _norm_int(data.get("cost_max") or data.get("max_cost") or 0)

    return out


def _estimate_looks_incomplete(result: dict, repair_type: str) -> bool:
    variants = result.get("variants") or []
    if not variants:
        return True

    first = variants[0]
    works_count = len(first.get("works") or [])
    mats_count = len(first.get("materials") or [])

    if any(v.get("_incomplete") for v in variants):
        return True

    # Минимальные пороги по категориям
    thresholds = {
        "full_renovation": (8, 7, 280000),
        "bathroom": (5, 5, 60000),
        "wiring": (3, 4, 30000),
        "plumbing": (2, 4, 20000),
        "floor": (3, 2, 15000),
        "kitchen": (4, 5, 40000),
        "tiles": (3, 3, 15000),
        "ceiling": (2, 2, 10000),
        "painting": (2, 2, 8000),
        "wallpaper": (2, 2, 10000),
        "cosmetic": (3, 3, 20000),
        "balcony": (3, 3, 20000),
        "doors_windows": (2, 2, 10000),
        "other": (2, 2, 5000),
    }
    min_w, min_m, min_total = thresholds.get(repair_type, (2, 2, 5000))
    if works_count < min_w or mats_count < min_m or first.get("total", 0) < min_total:
        return True

    # Доп. проверки для полного ремонта
    if repair_type == "full_renovation":
        elec_present = any(any(k in (w.get("name") or "").lower() for k in ["элект", "кабел", "щит", "автомат", "узо", "штроб"]) for w in first.get("works") or [])
        plumb_present = any(any(k in (w.get("name") or "").lower() for k in ["сантех", "труб", "вод", "канализ"]) for w in first.get("works") or [])
        toilet_present = any("унитаз" in (m.get("name") or "").lower() for m in first.get("materials") or [])
        if not elec_present or not plumb_present or not toilet_present:
            return True

    return False


def _parse_retry_after(exc: RateLimitError) -> float:
    try:
        return float(exc.response.json()["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return 15.0


async def _try_model(
    client: AsyncOpenAI,
    model: str,
    messages: list,
    max_tokens: int,
    use_json_mode: bool,
    project: dict | None = None,
    repair_type: str = "other",
) -> dict:
    kwargs: dict = dict(model=model, messages=messages, temperature=0.3, max_tokens=max_tokens)
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content
    parsed = json.loads(_clean_json(raw))
    return _normalize_result(parsed, project=project, repair_type=repair_type)


async def get_estimate(
    situation: str,
    project: dict | None = None,
    user_id: int | None = None,
    system_hint: str = "",
    repair_type: str = "other",
) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model_chain = await _get_model_chain(api_key)
    if not model_chain:
        raise RuntimeError("Нет доступных моделей")

    materials_context_full = await get_materials_context(situation, limit=12)
    materials_context_short = await get_materials_context(situation, limit=3)
    user_rates = get_user_rates(user_id) if user_id else []
    rates_context = _build_rates_context(user_rates)

    user_msg_full = _build_user_message(situation, project, materials_context_full, rates_context, repair_type)
    user_msg_short = _build_user_message(situation, project, materials_context_short, rates_context, repair_type)

    for model, base_url in model_chain:
        local = _is_local(base_url)
        groq = _is_groq(base_url)

        if local:
            system_prompt = _build_category_system_prompt_compact(repair_type, system_hint)
            max_tokens = 2200
        elif groq:
            system_prompt = _build_category_system_prompt_compact(repair_type, system_hint)
            max_tokens = 1800
        else:
            system_prompt = _build_category_system_prompt(repair_type, system_hint)
            max_tokens = 5200

        use_json_mode = local or groq
        user_msg = user_msg_short if groq else user_msg_full
        client = _make_client(base_url, api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        json_attempts = 0
        provider_tag = "local" if local else ("groq" if groq else "openrouter")

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages, max_tokens, use_json_mode, project=project, repair_type=repair_type)
                if _estimate_looks_incomplete(result, repair_type):
                    logger.warning("Estimate incomplete for repair_type=%s via %s, retrying", repair_type, model)
                    for v in result.get("variants", []):
                        v.pop("_incomplete", None)
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Предыдущая смета неполная для категории '{repair_type}'. Исправь:\n"
                            "1) Удали строки с qty=0, unit_price=0 или total=0.\n"
                            "2) Арифметика: qty×unit_price=total; пересчитай total_works и total как суммы строк.\n"
                            "3) Добавь недостающие позиции ТОЛЬКО для выбранной категории — не добавляй лишних разделов.\n"
                            "4) Разрыв: Оптимальный на 20-30% дороже Эконома, Премиум на 25-50% дороже Оптимального.\n"
                            "5) В поле risks: 'Расчёт без учёта маржи подрядчика (+15–30%).'"
                        ),
                    })
                    result = await _try_model(client, model, messages, max_tokens, use_json_mode, project=project, repair_type=repair_type)
                logger.info("Estimate OK via %s (%s), repair_type=%s", model, provider_tag, repair_type)
                return result
            except NotFoundError:
                logger.warning("Model not found: %s", model)
                _free_models_cache.clear()
                break
            except RateLimitError as exc:
                wait = _parse_retry_after(exc)
                if wait <= MAX_RATE_LIMIT_WAIT and attempt < len(RETRY_DELAYS):
                    logger.warning("Rate limited on %s, waiting %.0fs", model, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.warning("Rate limit too long (%.0fs) on %s, skipping", wait, model)
                    break
            except APIStatusError as exc:
                if exc.status_code == 413:
                    logger.warning("Payload too large (413) for %s (%s), skipping", model, provider_tag)
                    break
                raise
            except (APITimeoutError, APIConnectionError):
                if attempt < len(RETRY_DELAYS):
                    logger.warning("Timeout on %s, retrying in %ds", model, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.warning("All retries failed for %s", model)
                    break
            except json.JSONDecodeError:
                json_attempts += 1
                if json_attempts < JSON_MAX_RETRIES:
                    logger.warning("Bad JSON from %s (attempt %d), retrying", model, json_attempts)
                    await asyncio.sleep(2)
                else:
                    logger.warning("Bad JSON from %s, skipping", model)
                    break

    raise RuntimeError("Ни одна модель не ответила")
