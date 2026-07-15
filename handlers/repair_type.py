from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

REPAIR_TYPES = [
    ("🪵 Замена пола", "floor"),
    ("⚡ Замена проводки", "wiring"),
    ("🪟 Ремонт потолка", "ceiling"),
    ("🖼 Поклейка обоев", "wallpaper"),
    ("🔲 Укладка плитки", "tiles"),
    ("🚿 Ремонт ванной", "bathroom"),
    ("🍳 Ремонт кухни", "kitchen"),
    ("🚪 Замена дверей/окон", "doors_windows"),
    ("🔧 Сантехника", "plumbing"),
    ("🎨 Покраска стен", "painting"),
    ("🏠 Ремонт балкона", "balcony"),
    ("🏗 Полный ремонт", "full_renovation"),
    ("✨ Косметический ремонт", "cosmetic"),
    ("🔨 Другое", "other"),
]

REPAIR_LABELS = {key: label for label, key in REPAIR_TYPES}

SYSTEM_HINTS = {
    "floor": "Расчёт замены напольного покрытия. Учитывай: демонтаж старого покрытия, стяжку (если нужна), грунтовку, финишное покрытие (ламинат/кварцвинил/паркет/плитка/линолеум), плинтусы, порожки.",
    "wiring": "Расчёт замены электропроводки. Учитывай: демонтаж старой проводки, прокладку новых кабелей, установку розеток/выключателей, щиток с автоматами, штробление стен и заделку.",
    "ceiling": "Расчёт ремонта/замены потолка. Учитывай: демонтаж старого покрытия, выравнивание (шпаклёвка/штукатурка или натяжной потолок), грунтовку, финишную отделку, покраску или натяжную конструкцию.",
    "wallpaper": "Расчёт поклейки обоев. Учитывай: снятие старых обоев, выравнивание стен (шпаклёвка), грунтовку, клей, сами обои (разные классы), работу по поклейке.",
    "tiles": "Расчёт укладки плитки. Учитывай: подготовку основания, клей, затирку, саму плитку (кафель/керамогранит/мозаика), декор, резку, профили и уголки.",
    "bathroom": "Расчёт ремонта ванной комнаты. Учитывай: демонтаж, гидроизоляцию, плитку на пол и стены, сантехнику (унитаз/ванна/душевая/раковина), смесители, освещение, вентиляцию.",
    "kitchen": "Расчёт ремонта кухни. Учитывай: пол, стены (плитка/панели/обои), потолок, электрику для техники, вентиляцию, возможно замену сантехники.",
    "doors_windows": "Расчёт замены дверей и/или окон. Учитывай: демонтаж старых конструкций, установку новых (размеры, материал — ПВХ/дерево/алюминий), откосы, подоконники, уплотнители, отделку проёмов.",
    "plumbing": "Расчёт сантехнических работ. Учитывай: замену труб (ХВС/ГВС/канализация), установку сантехники, разводку, утепление труб, счётчики воды.",
    "painting": "Расчёт покраски стен/потолков. Учитывай: грунтовку, шпаклёвку (если нужна), малярную ленту, саму краску (классы качества), количество слоёв, работу.",
    "balcony": "Расчёт ремонта балкона/лоджии. Учитывай: остекление (если нужно), утепление (пол/стены/потолок), электрику, отделку стен и пола, перила.",
    "full_renovation": "Расчёт полного ремонта квартиры/помещения под ключ. Учитывай все этапы: демонтаж, черновые работы, электрику, сантехнику, стяжку, выравнивание стен и потолков, чистовую отделку пола/стен/потолка, установку дверей, финальную уборку. Раздели по зонам если это квартира.",
    "cosmetic": "Расчёт косметического ремонта. Учитывай: покраску или поклейку обоев, замену напольного покрытия без стяжки, покраску потолка, мелкий ремонт без сноса стен и замены коммуникаций.",
    "other": "Расчёт ремонтных работ. Внимательно прочитай описание пользователя и составь детальную смету именно под его запрос.",
}


def repair_type_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(REPAIR_TYPES) - 1, 2):
        row = [
            InlineKeyboardButton(text=REPAIR_TYPES[i][0], callback_data=f"repair_type:{REPAIR_TYPES[i][1]}"),
            InlineKeyboardButton(text=REPAIR_TYPES[i + 1][0], callback_data=f"repair_type:{REPAIR_TYPES[i + 1][1]}"),
        ]
        rows.append(row)
    if len(REPAIR_TYPES) % 2 != 0:
        last = REPAIR_TYPES[-1]
        rows.append([InlineKeyboardButton(text=last[0], callback_data=f"repair_type:{last[1]}")])
    rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "nav:estimate")
async def cb_nav_estimate(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    await call.message.answer(
        "🔨 <b>Выбери тип ремонта</b>\n\n"
        "Выбери категорию — нейросеть получит точное задание и рассчитает смету корректно:",
        reply_markup=repair_type_kb(),
    )


@router.callback_query(F.data.startswith("repair_type:"))
async def cb_repair_type_selected(call: CallbackQuery, state: FSMContext) -> None:
    from aiogram.types import ReplyKeyboardRemove
    from handlers.estimate import EstimateForm
    await call.answer()
    repair_key = call.data.split(":", 1)[1]
    label = REPAIR_LABELS.get(repair_key, repair_key)
    hint = SYSTEM_HINTS.get(repair_key, "")
    await state.update_data(repair_type=repair_key, repair_label=label, repair_hint=hint)
    await state.set_state(EstimateForm.situation)
    await call.message.answer(
        f"✅ Тип ремонта: <b>{label}</b>\n\n"
        f"📝 <b>Опиши детали</b>: площадь, пожелания по стилю, материалам, бюджету.\n"
        f"<i>Пример: 28 м², хочу кварцвинил под дерево, со стяжкой, бюджет ~80 000 ₽</i>",
        reply_markup=ReplyKeyboardRemove(),
    )
