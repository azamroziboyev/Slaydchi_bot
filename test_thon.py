import os
from aiogram import Bot, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


class DocGenerator(StatesGroup):
    collecting = State()

# ================== WORD MENU TEXTS ==================
WORD_TEXTS = {
    "📝 Create Word File",
    "📝 Word fayl yaratish",
    "📝 Создать Word файл"
}

# ================== SAVE / BACK TEXTS ==================
SAVE_TEXTS = {"💾 Saqlash", "💾 Save", "💾 Сохранить", "/save"}
BACK_TEXTS = {"⬅️ Orqaga", "⬅️ Back", "⬅️ Назад"}

# ================== KEYBOARD ==================
async def get_text2word_menu(state: FSMContext):
    data = await state.get_data()
    lang = data.get("til", "uz")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["uz"])

    # BU YERDAN state.clear() VA state.update_data() LARNI OLIB TASHLANG!
    # Faqat menyuni qaytaring
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["menu_word_save"])],
            [KeyboardButton(text=t["menu_back"])]
        ],
        resize_keyboard=True
    )

# ================== START WORD PROCESS ==================
@dp.message(lambda m: m.text in WORD_TEXTS)
async def start_word_process(message: Message, state: FSMContext):
    current_data = await state.get_data()
    lang = current_data.get("til", "uz")

    await state.clear()
    await state.set_state(DocGenerator.collecting)
    # Tilni qayta tiklaymiz, aks holda t["menu_word_save"] xato beradi
    await state.update_data(til=lang, buffer=[])

    menu = await get_text2word_menu(state)

    await message.answer(
        "📝 Yozish boshlandi!\n\nMatn yoki rasm yuboring.",
        reply_markup=menu
    )

# ================== COLLECT TEXT & IMAGE ==================
@dp.message(DocGenerator.collecting, F.text | F.photo)
async def handle_collection(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    buffer = data.get("buffer", [])

    # TEXT
    if message.text and message.text.strip() not in SAVE_TEXTS and message.text.strip() not in BACK_TEXTS:
        buffer.append({"type": "text", "content": message.text.strip()})

    # PHOTO
    elif message.photo:
        os.makedirs("temp_word", exist_ok=True)
        photo = message.photo[-1]
        path = f"temp_word/{photo.file_id}.jpg"
        await bot.download(photo, destination=path)
        buffer.append({"type": "image", "content": path})

    await state.update_data(buffer=buffer)

# ================== SAVE WORD FILE ==================
@dp.message(DocGenerator.collecting, lambda m: m.text in SAVE_TEXTS)
async def cmd_save_doc(message: Message, state: FSMContext):
    data = await state.get_data()
    buffer = data.get("buffer", [])

    if not buffer:
        return await message.answer("❗ Hali hech narsa yubormadingiz.")

    # Word fayl yaratish
    file_path = create_word_report(message.from_user.id, buffer)
    doc_file = FSInputFile(file_path)

    try:
        await message.answer_document(
            doc_file,
            caption="✅ Word faylingiz tayyor!"
        )
    finally:
        # Rasmlarni o‘chirish
        for item in buffer:
            if item["type"] == "image" and os.path.exists(item["content"]):
                os.remove(item["content"])

        # Word faylni o‘chirish
        if os.path.exists(file_path):
            os.remove(file_path)

        await state.clear()

# ================== BACK BUTTON ==================
@dp.message(DocGenerator.collecting, lambda m: (m.text or "").strip() in BACK_TEXTS)
async def back_from_word(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    main_keyboard = await get_main_menu(state, message, user_id)
    await message.answer(
        "🏠 Asosiy menyu",
        reply_markup=main_keyboard
    )