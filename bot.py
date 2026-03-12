import asyncio
import logging
import sys
import os
import json
from dotenv import load_dotenv
from datetime import datetime
import io

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
                           InlineKeyboardButton, CallbackQuery, ContentType)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import StorageKey
from referat_2gpt import run_code
from tezis import make_thesis
from mustaqil.mustaqil_ish import run_snip
from services.models import APIKeyManager, DB_path, ModelManager, add_key, add_model, show_models, count_model, init_models_db
from services.models import show_keys, count_key
from text import TRANSLATIONS
from services.limits import (init_db, ensure_user, get_limits, check_rate_limit, is_already_referred, mark_as_referred,
                             is_first_time_user, user_exists, mark_user_as_onboarded, parse_pages)
from services.balance import get_balance, deduct_balance, add_balance
from services.access_control import can_generate, PRICES
# from slide.slayd_bot import run_engine
from text2word.text2word import create_word_report
import time
from services.statistics import get_statistics, increment_user_usage, export_monthly_income_to_excel
# IMPORT SECTION ENDS

ADMINS = [1477944238,]
CHANNEL_ID = -1002031432971


model_manager = ModelManager(DB_path)
key_manager = APIKeyManager(DB_path)


def get_message_id(topic: str):
    data = load_db()
    return data.get(topic, [])


def load_db():
    try:
        return json.load(open("db.json"))
    except:
        return {}


async def get_texts(state: FSMContext):
    data = await state.get_data()
    lang = data.get("til", "uz")  # default to Uzbek
    return TRANSLATIONS[lang]


async def get_main_menu(state: FSMContext, message: Message, user_id):
    data = await state.get_data()
    lang = data.get("til", "uz")
    t = TRANSLATIONS[lang]
    await state.update_data(topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None,
                            student_name=None)
    await state.clear()
    await state.update_data(til=lang)
    t = TRANSLATIONS[lang]
    # user_id = message.from_user.id
    # Temporary debug logging (remove after testing)
    # print(f"Debug: user_id={user_id}, in ADMINS={user_id in ADMINS}")
    if user_id in ADMINS:
        return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["menu_referat"])],
            [KeyboardButton(text=t["menu_presentation"]), KeyboardButton(text=t["menu_mustaqil"])],
            [KeyboardButton(text=t["menu_help"]), KeyboardButton(text=t["menu_tezis"])],
            [KeyboardButton(text=t["menu_word"]), KeyboardButton(text=t["menu_balance"])],
            [KeyboardButton(text=t["menu_referal"]), KeyboardButton(text=t["menu_prices"])],
            [KeyboardButton(text="Foydalanuvchiga Xabar"), KeyboardButton(text="Statistika")],
            [KeyboardButton(text="Add model"), KeyboardButton(text="Add API KEY")],
        ],
        resize_keyboard=True
    )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=t["menu_referat"])],
                [KeyboardButton(text=t["menu_presentation"]), KeyboardButton(text=t["menu_mustaqil"])],
                [KeyboardButton(text=t["menu_help"]), KeyboardButton(text=t["menu_tezis"])],
                [KeyboardButton(text=t["menu_word"]), KeyboardButton(text=t["menu_balance"])],
                [KeyboardButton(text=t["menu_referal"]), KeyboardButton(text=t["menu_prices"])]
            ],
            resize_keyboard=True
        )


load_dotenv()
# Bot token can be obtained via https://t.me/BotFather
TOKEN = os.getenv("BOT_TOKEN")

# All handlers should be attached to the Router (or Dispatcher)

dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    args = message.text.split()
    texts = await get_texts(state)

    # Ensure user exists
    ensure_user(user_id)

    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}!",
        parse_mode="HTML"
    )

    # Referral logic
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].replace("ref_", ""))

        if referrer_id != user_id and user_exists(referrer_id):
            if not is_already_referred(user_id):
                add_balance(referrer_id, 1000)
                mark_as_referred(user_id)

                await message.bot.send_message(
                    referrer_id, texts["referal_payment"]
                )

    # Language selection keyboard
    language_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="O'zbek", callback_data="lang:uz"),
            InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="English", callback_data="lang:eng")
        ]]
    )

    await message.answer(
        "Tilni tanlang / Выберите язык / Select language:",
        reply_markup=language_keyboard
    )


@dp.callback_query(lambda c: c.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = callback.data.split(":")[1]  # "uz", "ru", "eng"

    # Save language only in FSM
    await state.update_data(til=lang)
    
    texts = TRANSLATIONS[lang]
    menu = await get_main_menu(state, callback.message, user_id)

    # Acknowledge language selection (only once!)
    await callback.answer(f"Language set to {lang.upper()} ✅")

    # Remove the keyboard after selection
    await callback.message.edit_reply_markup(reply_markup=None)

    # Onboarding logic for first-time users
    if is_first_time_user(user_id):  # check is_onboarded flag
        await callback.message.answer(texts["welcome"])
        await callback.message.answer(texts["policy_confirmation"])
        mark_user_as_onboarded(user_id)  # mark as onboarded in DB

    # Send main menu
    await callback.message.answer(texts["start"], reply_markup=menu)

# --------------------------------------------------------------------
# model qo'shish
# --------------------------------------------------------------------
class ModelStates(StatesGroup):
    yangi_model = State()



@dp.message(lambda m: m.text == "Add model")
async def ask_model(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("❌ Sizda bu funksiyaga ruxsat yo'q.")
        return
    await message.answer("Modelni yuboring:")
    await state.set_state(ModelStates.yangi_model)
    

@dp.message(ModelStates.yangi_model)
async def get_yangi_model(message: Message, state: FSMContext):
    await state.update_data(yangi_model=message.text)
    data = await state.get_data()

    add_model(data["yangi_model"])           # avval qo‘shamiz
    modellar_soni = count_model()             # keyin sanaymiz

    await message.answer(
        f"Model ro'yxatga qo'shildi\n"
        f"Mavjud modellar soni: {modellar_soni}"
    )

    modellar = show_models()
    royxat = "\n".join(modellar)

    await message.answer(royxat)
    await state.clear()


#----------------------------------------------------------------------
# Add key menyusini 
#----------------------------------------------------------------------


class KeyStates(StatesGroup):
    yangi_key = State()



@dp.message(lambda m: m.text == "Add API KEY")
async def ask_key(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("❌ Sizda bu funksiyaga ruxsat yo'q.")
        return
    await message.answer("Keyni yuboring:")
    await state.set_state(KeyStates.yangi_key)
    

@dp.message(KeyStates.yangi_key)
async def get_yangi_key(message: Message, state: FSMContext):
    await state.update_data(yangi_key=message.text)
    data = await state.get_data()

    add_key(data["yangi_key"])           # avval qo‘shamiz
    keylar_soni = count_key()             # keyin sanaymiz

    await message.answer(
        f"Key ro'yxatga qo'shildi\n"
        f"Mavjud keylar soni: {keylar_soni}"
    )

    keylar = show_keys()
    if keylar:
        royxat = "\n".join(f"{i}. {key}" for i, key in enumerate(keylar, start=1))

        await message.answer(royxat)
    await state.clear()




##################
# Foydalanuvchilarga payment haqida xabar yuborish
##################


class XabarStates(StatesGroup):
    foydalanuvchi_id = State()
    xabar = State()


@dp.message(lambda m: m.text == "Foydalanuvchiga Xabar")
async def send_message_user(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("❌ Sizda bu funksiyaga ruxsat yo'q.")
        return
    await message.answer("Foydalanuvchi Id raqamini kiriting")
    await state.set_state(XabarStates.foydalanuvchi_id)


@dp.message(XabarStates.foydalanuvchi_id)
async def get_id(message: Message, state: FSMContext):
    await state.update_data(user_id=message.text)
    await message.answer("Yubormoqchi bo'lgan xabarni kiriting")
    await state.set_state(XabarStates.xabar)
    


@dp.message(XabarStates.xabar)
async def get_xabar(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id_str = data.get("user_id")
    user_message = message.text

    try:
        user_id = int(user_id_str)
        await bot.send_message(chat_id=user_id, text=user_message)
        await message.answer(f"✅ Xabar foydalanuvchiga yuborildi: {user_id}")
    except Exception as e:
        await message.answer(f"❌ Xabar yuborilmadi: {e}")

    await state.clear()
###############
# Yodram menu
##############

HELP_TEXTS = {
    "ℹ️ Yordam",
    "ℹ️ Помощь",
    "ℹ️ Help"
}


@dp.message(lambda m: m.text in HELP_TEXTS)
async def show_prices(message: Message, state: FSMContext):
    await state.clear()
    texts = await get_texts(state)
    await message.answer(texts["help_menu_text"])




#################################################
# Word fayl yaratish menyusi

##################################################

# ================== FSM ==================
class DocGenerator(StatesGroup):
    collecting = State()

# ================== TEXTS ==================
WORD_TEXTS = {"📝 Create Word File", "📝 Word fayl yaratish", "📝 Создать Word файл"}
SAVE_TEXTS = {"💾 Saqlash", "💾 Save", "💾 Сохранить", "/save"}
BACK_TEXTS = {"⬅️ Orqaga", "⬅️ Back", "⬅️ Назад"}

# ================== KEYBOARD ==================
async def get_text2word_menu(state: FSMContext):
    data = await state.get_data()
    lang = data.get("til", "uz")
    t = TRANSLATIONS.get(lang)
    await state.update_data(til=lang)
    t = TRANSLATIONS[lang]
    # BU YERDAN state.clear() VA state.update_data() LARNI OLIB TASHLANG!
    # Faqat menyuni qaytaring
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["menu_word_save"])],
            [KeyboardButton(text=t["menu_back"])]
        ],
        resize_keyboard=True
    )
# ================== CREATE WORD FUNCTION ==================


# ================== START WORD PROCESS ==================
@dp.message(lambda m: (m.text or "").strip() in WORD_TEXTS)
async def start_word_process(message: Message, state: FSMContext):
    print(f"[DEBUG] Starting Word process for user {message.from_user.id}")
    data = await state.get_data()
    lang = data.get("til", "uz")
    # await state.clear()
    await state.update_data(til=lang)
    t = TRANSLATIONS[lang]
    # BU YERDAN state.clear() VA state.update_data() LARNI OLIB TASHLANG!
    # Faqat menyuni qaytaring
    menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["menu_word_save"])],
            [KeyboardButton(text=t["menu_back"])]
        ],
        resize_keyboard=True
    )
    await state.set_state(DocGenerator.collecting)
    await state.update_data(buffer=[])
    # menu = await get_text2word_menu(state)
    await message.answer(
        "📝 Yozish boshlandi!\nMatn yoki rasm yuboring.\nTugatgach /save yoki tugmani bosing.",
        reply_markup=menu
    )

# ================== COLLECT TEXT & IMAGE ==================
@dp.message(DocGenerator.collecting, F.text | F.photo, lambda m: (m.text or "").strip() not in SAVE_TEXTS and (m.text or "").strip() not in BACK_TEXTS)
async def handle_collection(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    buffer = data.get("buffer", [])
    text = (message.text or "").strip()


    # TEXT
    if text and text not in SAVE_TEXTS and text not in BACK_TEXTS:
        buffer.append({"type": "text", "content": text})

    # PHOTO
    if message.photo:
        os.makedirs("temp", exist_ok=True)
        photo = message.photo[-1]
        path = f"temp/{photo.file_id}.jpg"
        await bot.download(photo, destination=path)
        buffer.append({"type": "image", "content": path})

    await state.update_data(buffer=buffer)

# ================== SAVE DOCUMENT ==================
@dp.message(DocGenerator.collecting, lambda m: (m.text or "").strip() in SAVE_TEXTS)
async def cmd_save_doc(message: Message, state: FSMContext):
    # Telegram invisible charlarni olib tashlaymi
    # FSM dan bufferni olamiz
    
    data = await state.get_data()
    buffer = data.get("buffer", [])

    if not buffer:
        return await message.answer("❗ Hali hech narsa yubormadingiz.")

    # Word fayl yaratish
    file_path = await asyncio.to_thread(create_word_report, message.from_user.id, buffer)
    

    doc_file = FSInputFile(file_path)
    await message.answer_document(doc_file, caption="✅ Word faylingiz tayyor!")

    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"[DEBUG] Removed Word file: {file_path}")

    # FSM tozalanadi
    await state.clear()
    



# ================== BACK BUTTON ==================
@dp.message(DocGenerator.collecting, lambda m: m.text in BACK_TEXTS)
async def back_from_word(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    main_menu = await get_main_menu(state, message, user_id)
    await message.answer("🏠 Asosiy menyu", reply_markup=main_menu)

# ================== CREATE WORD FUNCTION ==================


#########################################################
# Narxlar tugmasi

##########################################################

class PaymentStates(StatesGroup):
    amount = State()
    receipt = State()


PRICES_TEXTS = {
    "🏷️ Narxlar",
    "🏷️ Цены",
    "🏷️ Prices"
}


@dp.message(lambda m: m.text in PRICES_TEXTS)
async def show_prices(message: Message, state: FSMContext):
    # user_id = message.from_user.id
    texts = await get_texts(state)
    payment = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
    ])
    await message.answer(texts["text_prices"], reply_markup=payment)


@dp.callback_query(F.data == "pay_start")
async def start_payment(callback: CallbackQuery, state: FSMContext):
    texts = await get_texts(state)

    amount_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="2 000 so'm", callback_data="amount:2000"),
                InlineKeyboardButton(text="6 000 so'm", callback_data="amount:6000")
            ],
            [
                InlineKeyboardButton(text="8 000 so'm", callback_data="amount:8000"),
                InlineKeyboardButton(text="13 000 so'm", callback_data="amount:13000")
            ]
        ]
    )
    
    await callback.message.answer(texts["choose_amount"], reply_markup=amount_keyboard)
    await callback.message.answer(texts["payment_manual"])
    await callback.answer()


async def generate_receipt(holat, summa):
    width = 27
    now = datetime.now().strftime('%Y-%m-%d')
    nowmin = datetime.now().strftime('%H:%M')

    # Sarlavhani markazga olish
    title = "SLAYDCHI".center(width)

    receipt = f"""
    {"─" * width}
    {title}
    {"─" * width}
    {"To'lov holati:":<18} {holat:>10} 
    {"To'lov sanasi:":<18} {now:>10}
    {"To'lov vaqti:":<18} {nowmin:>10} 
    {"Summa:":<18} {summa:>10} 
    {"─" * width}
    {"RAHMAT!".center(width)}
    {"─" * width}
    """
    return receipt

@dp.callback_query(lambda c: c.data.startswith("amount:"))
async def get_amount(callback: CallbackQuery, state: FSMContext):
    amount = callback.data.split(":")[1]

    await state.update_data(amount=amount)
    await state.set_state(PaymentStates.receipt)

    texts = await get_texts(state)

    receipt_text = await generate_receipt("kutilmoqda", str(amount))
    await callback.message.answer(f"<code>{receipt_text}</code>", parse_mode="HTML")
    await callback.message.answer(texts["send_receipt"])
    await callback.answer()


pending_payments = {}


# @dp.message(PaymentStates.receipt, F.photo)
# async def get_receipt(message: Message, state: FSMContext, bot: Bot):
#     data = await state.get_data()
#     amount = data["amount"] 

#     user = message.from_user
#     username = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}"

#     caption = (
#         f"💰 Payment request\n"
#         f"👤 User ID: {user.id}\n"
#         f"👤 Username: {username}\n"
#         f"💵 Amount: {amount} so'm"
#     )

#     photo_id = message.photo[-1].file_id

#     # Save pending payment
#     pending_payments[user.id] = {"amount": amount, "timestamp": datetime.now(), "status": "pending"}

#     # Inline keyboard for confirmation
#     keyboard_confirm = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm:{user.id}"),
#                 InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{user.id}")
#             ]
#         ]
#     )

#     # Send to all admins
#     for admin_id in ADMINS:
#         try:
#             logging.info(f"Sending photo with keyboard to admin {admin_id}")
#             await bot.send_photo(
#                 chat_id=admin_id,
#                 photo=photo_id,
#                 caption=caption + "\n\nDo you confirm this payment?",
#                 reply_markup=keyboard_confirm
#             )
#         except Exception as e:
#             logging.error(f"Failed to send photo to admin {admin_id}: {e}")

#     texts = await get_texts(state)
#     await message.answer(texts["payment_sent"])
#     asyncio.create_task(auto_rollback(user.id, message.bot))
#     await state.clear()

#
# ----this function that gets photo and pdf file is generated by Chatgpt so above is the real function that works
#
@dp.message(PaymentStates.receipt, F.content_type.in_([ContentType.PHOTO, ContentType.DOCUMENT]))
async def get_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data["amount"]

    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}"

    # Reject non-PDF documents
    if message.content_type == ContentType.DOCUMENT and message.document.mime_type != "application/pdf":
        await message.answer("Iltimos, faqat PDF fayl yuboring!")
        return

    caption = (
        f"💰 Payment request\n"
        f"👤 User ID: {user.id}\n"
        f"👤 Username: {username}\n"
        f"💵 Amount: {amount} so'm"
    )

    # Determine file type and ID
    if message.content_type == ContentType.PHOTO:
        file_id = message.photo[-1].file_id
        send_func = bot.send_photo
        file_kwargs = {"photo": file_id}  # caption removed
    elif message.content_type == ContentType.DOCUMENT:
        file_id = message.document.file_id
        send_func = bot.send_document
        file_kwargs = {"document": file_id}  # caption removed

    # Save pending payment
    pending_payments[user.id] = {
        "amount": amount,
        "timestamp": datetime.now(),
        "status": "pending",
        "file_type": message.content_type
    }

    # Inline keyboard for admin confirmation
    keyboard_confirm = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm:{user.id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{user.id}")
            ]
        ]
    )

    # Send to all admins
    for admin_id in ADMINS:
        try:
            logging.info(f"Sending receipt to admin {admin_id}")
            await send_func(
                chat_id=admin_id,
                reply_markup=keyboard_confirm,
                caption=caption + "\n\nDo you confirm this payment?",
                **file_kwargs
            )
        except Exception as e:
            logging.error(f"Failed to send receipt to admin {admin_id}: {e}")

    texts = await get_texts(state)
    await message.answer(texts["payment_sent"])
    asyncio.create_task(auto_rollback(user.id))
    await state.clear()


@dp.callback_query(lambda c: c.data.startswith(("confirm:", "reject:")))
async def handle_admin_confirmation(callback: CallbackQuery, bot: Bot, state: FSMContext, ):
    action, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)
    texts = await get_texts(state)

    if user_id not in pending_payments:
        await callback.answer("To'lov allaqachon tasdiqlangan")
        return

    payment = pending_payments[user_id]

    if action == "confirm":
        add_balance(user_id, payment["amount"])
        payment["status"] = "confirmed"
        await bot.send_message(user_id, f"{texts["payment_confirmed"]} {payment["amount"]}")
        await callback.answer("Payment confirmed")
    elif action == "reject":
        payment["status"] = "rejected"
        await bot.send_message(user_id, texts["payment_rejected"])
        await callback.answer("Payment rejected")

    # Remove inline keyboard from admin message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        print(f"Failed to remove inline keyboard: {e}")

    # Remove pending payment
    del pending_payments[user_id]


async def auto_rollback(user_id: int):
    await asyncio.sleep(5 * 60)  # 5 minutes
    payment = pending_payments.get(user_id)
    if payment and payment["status"] == "pending":
        add_balance(user_id, payment["amount"])
        #await bot.send_message(user_id, f"⏰ Your payment of {payment['amount']} UZS has been automatically refunded due to no confirmation.")
        del pending_payments[user_id]





BALANCE_TEXTS = {
    "💰Balans",
    "💰Баланс",
    "💰Balance"
}

@dp.message(lambda m: m.text in BALANCE_TEXTS)
async def show_balance(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check rate limit for balance checks (e.g., 10 checks per hour)
    if not check_rate_limit(user_id, "balance_check", 35, 1800):
        await message.answer("❌ Too many balance checks. Please wait before checking again.")
        return
    
    balance = get_balance(user_id)
    texts = await get_texts(state)
    payment = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
    ])
    await message.answer(f"{texts['balance_info']} {balance} so'm", reply_markup=payment)


CREATION_TEXTS = {
    "🆓 Bepul yaratish",
    "🆓 Бесплатное создание",
    "🆓 Free creation"
}

@dp.message(lambda m: m.text in CREATION_TEXTS)
async def show_referal_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    bot_username = "slayd_chibot"  # without @

    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    await message.answer(
        f"👥 Do‘stlaringizni taklif qiling!\n\n"
        f"Har bir do‘st uchun +1000 so‘m 💰\n\n"
        f"🔗 Sizning referal havolangiz:\n{referral_link}"
    )
    

####################
# prezentatsiya tayyorlash
####################
class TaqdimotStates(StatesGroup):
    student_name = State()
    language = State()
    topic = State()


PRESENTATION_TEXTS = {
    "📊 Presentation",
    "📊 Prezentatsiya",
    "📊 Презентация"
}

@dp.message(lambda m: m.text in PRESENTATION_TEXTS)
async def presentation_start(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("til", "uz")
    texts = TRANSLATIONS[lang]
    await message.answer(texts["alert_upcoming"])
    await state.clear()

#     contents_type = "presentation"
#     user_id = message.from_user.id
#     allowed, reason = can_generate(user_id, contents_type)
    
#     if not allowed:
#         if reason == "rate_limited":
#             await message.answer(
#                 "❌ Too many requests. Please wait a moment before trying again."
#             )
#         elif reason == "blocked":
#             payment = InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
#             ])
#             await message.answer(
#                 texts["alerta_payment"], reply_markup=payment
#             )
#         return
    
#     mode = reason  # "free" or "paid"
#     await state.update_data(til=lang, topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None, student_name=None)
#     await message.answer(texts["topic_referat"])
#     await state.set_state(TaqdimotStates.topic)

# # Step 3: Collect university
# @dp.message(TaqdimotStates.topic, lambda m: m.text not in MENU_TEXTS)
# async def get_topic_taqdimot(message: Message, state: FSMContext):
#     texts = await get_texts(state)
#     await state.update_data(topic=message.text.upper())

#     keyboard_referat = InlineKeyboardMarkup(inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="O'zbek", callback_data="ref_lang:uz"),
#                 InlineKeyboardButton(text="Русский", callback_data="ref_lang:ru"),
#                 InlineKeyboardButton(text="English", callback_data="ref_lang:en")
#             ]
#         ])
#     await message.answer(texts["language_referat"], reply_markup=keyboard_referat)
#     await state.set_state(TaqdimotStates.language)


# @dp.callback_query(TaqdimotStates.language, F.data.startswith("ref_lang:"))
# async def set_language_taqdimot(callback: CallbackQuery, state: FSMContext):
#     texts = await get_texts(state)
#     referat_lang = callback.data.split(":")[1]  # uz / ru / en

#     await state.update_data(language=referat_lang)  # ✅ saved
#     await callback.answer()
#     await callback.message.answer(texts["student_referat"])
#     await state.set_state(TaqdimotStates.student_name)

# # Step 4: Collect student name
# @dp.message(TaqdimotStates.student_name, lambda m: m.text not in MENU_TEXTS)
# async def get_student_taqdimot(message: Message, state: FSMContext):
#     texts = await get_texts(state)
#     await state.update_data(student_name=message.text.title())

#     await message.answer(texts["referat_generating"])
#     data = await state.get_data()
#     file_path = f"taqdimot_{message.from_user.id}_{int(time.time())}.pptx"
#     # Generate the document
#     #check if API wokring

#     test = await asyncio.to_thread(
#         run_engine,
#         topic=data["topic"],
#         student=data['student_name'],
#         language=data['language'],
#         file_path=file_path
#     )
#     if test == "API":
#         await message.answer("Please try again later")
#         for admin in ADMINS:
#             await message.answer("Diqqat Prezentatsiya API da xatolik yoki API key eskirgan")
#         return

#     # Send the document
#     file = FSInputFile(file_path)
#     await message.answer_document(document=file, caption="Bu sizning taqdimotingiz. Iltimos o'zingiz ham bir ko'z tashlab o'ting.")
#     #contents_type = "presentation"
#     price = PRICES["presentation"]
#     user_id = message.from_user.id
#     #deduct the balance of the user
#     deduct_balance(user_id, price)
#     increment_user_usage(user_id)

#     os.remove(file_path)

#     # Finish the state
#     await state.clear()




####################
# Tezis yozish
####################

class TezisStates(StatesGroup):
    language = State()
    topic = State()
    university = State()
    student_name = State()

TEZIS_TEXTS = {
    "✍️ Tezis yozish",
    "✍️ Написать тезис",
    "✍️ Write thesis"
}

# Step 2: Start command
@dp.message(lambda m: m.text in TEZIS_TEXTS)
async def tezis_start(message: Message, state: FSMContext):
    
    data = await state.get_data()
    lang = data.get("til", "uz")
    texts = TRANSLATIONS[lang]
    # await message.answer(texts["alert_upcoming"])
    # ----pastdagi funksiya qatorlari to'liq ishlaydi faqat bosh qotirmaganim uchun shunchaki keyin ishga tushurish maqsadida comment qilib bu funksiya keyin ishga tushadi deb qoydim.
    await state.clear()
    texts = await get_texts(state)
    user_id = message.from_user.id
   
    allowed, reason = can_generate(user_id, "tezis")
    
    if not allowed:
        if reason == "rate_limited":
            await message.answer(
                "❌ Too many requests. Please wait a moment before trying again."
            )
        elif reason == "blocked":
            payment = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
            ])
            await message.answer(
                texts["alerta_payment"], reply_markup=payment
            )
        return
    await state.update_data(til=lang, topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None, student_name=None)
    await message.answer(texts["topic_mustaqil"])
    await state.set_state(TezisStates.topic)

# Step 3: Collect university
@dp.message(TezisStates.topic, lambda m: m.text not in MENU_TEXTS)
async def get_topic(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(topic=message.text.upper())
    await message.answer(texts["university_mustaqil"])
    await state.set_state(TezisStates.university)

@dp.message(TezisStates.university, lambda m: m.text not in MENU_TEXTS)
async def get_university(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(university=message.text)
    await message.answer(texts["student_tezis"])
    await state.set_state(TezisStates.student_name)

@dp.message(TezisStates.student_name, lambda m: m.text not in MENU_TEXTS)
async def get_student_name(message: Message, state: FSMContext):
    
    texts = await get_texts(state)
    await state.update_data(student_name=message.text)
    keyboard_tezis = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="O'zbek", callback_data="tez_lang:uz"),
            InlineKeyboardButton(text="Русский", callback_data="tez_lang:ru"),
            InlineKeyboardButton(text="English", callback_data="tez_lang:en")
        ]
    ])
    await message.answer(texts["language_tezis"], reply_markup=keyboard_tezis)
    await state.set_state(TezisStates.language)

@dp.callback_query(TezisStates.language, F.data.startswith("tez_lang:"))
async def get_language_tezis(callback: CallbackQuery,  state: FSMContext):
    texts = await get_texts(state)
    message = callback.message
    texts = await get_texts(state)
    await state.update_data(language=callback.data.split(":")[1])
    await callback.answer()
    data = await state.get_data()
    user_id = message.from_user.id

    await callback.message.answer("Tezisingiz tayyorlanmoqa iltimos biroz kuting...")
    file_path = f"tezis_{user_id}_{int(time.time())}.docx"
    
    file_tezis = await asyncio.to_thread(
        make_thesis,
        language=data["language"],
        topic=data["topic"],
        file_path=file_path,
        university=data['university'],
        student_name=data['student_name']
    )
    if file_tezis == "error":
        await message.answer("Please try again later")
        for admin in ADMINS:
            await message.answer(f"Diqqat Referat API da xatolik yoki API key eskirgan\nTezis yaratish menyusida muammo!\nXato yuz bergan foydalanuvchi: {user_id}")
        return
    file = FSInputFile(file_tezis)
    await message.answer_document(document=file, caption=texts["caption_file"])
    

    contents_type = "tezis"
    price = PRICES[contents_type]
    user_id = message.from_user.id
    #deduct the balance of the user
    deduct_balance(user_id, price)
    increment_user_usage(user_id)

    os.remove(file_path)

    # Finish the state
    await state.clear()

####################
# referat  yozish
####################


class ReferatStates(StatesGroup):
    university = State()
    student_name = State()
    qabul_qiluvchi = State()
    language = State()
    topic = State()
    pages = State()


REFERAT_TEXTS = {
    "📄 Referat yaratish",
    "📄 Создать реферат",
    "📄 Create Referat"
}    


# Step 2: Start command
@dp.message(lambda m: m.text in REFERAT_TEXTS)
async def referat_start(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("til", "uz")
    texts = TRANSLATIONS[lang]
    
    await state.clear()

    contents_type = "referat"
    user_id = message.from_user.id
    allowed, reason = can_generate(user_id, contents_type)
    
    if not allowed:
        if reason == "rate_limited":
            await message.answer(
                "❌ Too many requests. Please wait a moment before trying again."
            )
        elif reason == "blocked":
            payment = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
            ])
            await message.answer(
                texts["alerta_payment"], reply_markup=payment
            )
        return
    
    mode = reason  # "free" or "paid"
    await state.update_data(til=lang, topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None, student_name=None)
    await message.answer(texts["university_referat"])
    await state.set_state(ReferatStates.university)

# Step 3: Collect university
@dp.message(ReferatStates.university, lambda m: m.text not in MENU_TEXTS)
async def get_university(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(university=message.text.upper())
    await message.answer(texts["student_referat"])
    await state.set_state(ReferatStates.student_name)

# Step 4: Collect student name
@dp.message(ReferatStates.student_name, lambda m: m.text not in MENU_TEXTS)
async def get_student_name(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(student_name=message.text.title())

    keyboard_referat = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="O'zbek", callback_data="ref_lang:uz"),
            InlineKeyboardButton(text="Русский", callback_data="ref_lang:ru"),
            InlineKeyboardButton(text="English", callback_data="ref_lang:en")
        ]
    ])
    await message.answer(texts["language_referat"], reply_markup=keyboard_referat)
    await state.set_state(ReferatStates.language)

# @dp.message(ReferatStates.language, lambda m: m.text not in MENU_TEXTS)
# async def get_language(message: Message, state: FSMContext):
#     texts = await get_texts(state)
#     await state.update_data(language=message.text.title())
#     await message.answer(texts["teacher_referat"])
#     await state.set_state(ReferatStates.qabul_qiluvchi)

@dp.callback_query(ReferatStates.language, F.data.startswith("ref_lang:"))
async def set_language_referat(callback: CallbackQuery, state: FSMContext):
    texts = await get_texts(state)
    referat_lang = callback.data.split(":")[1]  # uz / ru / en

    await state.update_data(language=referat_lang)  # ✅ saved
    await callback.answer()

    # ✅ ask next question
    await callback.message.answer(texts["teacher_referat"])

    # ✅ move FSM forward
    await state.set_state(ReferatStates.qabul_qiluvchi)

@dp.message(ReferatStates.qabul_qiluvchi, lambda m: m.text not in MENU_TEXTS)
async def get_qabul_qiluvchi(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(qabul_qiluvchi=message.text.title())
    await message.answer(texts["topic_referat"])
    await state.set_state(ReferatStates.topic)

@dp.message(ReferatStates.topic, lambda m: m.text not in MENU_TEXTS)
async def get_topic(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(topic=message.text.title())
    await message.answer(texts["pages_referat"])
    await state.set_state(ReferatStates.pages)

# Step 5: Collect qabul qiluvchi and generate file
@dp.message(ReferatStates.pages, lambda m: m.text not in MENU_TEXTS)
async def get_pages(message: Message, state: FSMContext):
    texts = await get_texts(state)
    try:
        pages = parse_pages(message.text)
    except ValueError:
        await message.answer("❌ Faqat butun son kiriting (2–20 oralig‘ida).")
        return
    
    await state.update_data(pages=message.text.title())
    data = await state.get_data()
    user_id = message.from_user.id
    
    await message.answer(texts["referat_generating"])
    file_path = f"referat_{user_id}_{int(time.time())}.docx"
    # Generate the document
    #check if API wokring

    test = await asyncio.to_thread(
        run_code,
        university=data['university'],
        student=data['student_name'],
        teacher=data['qabul_qiluvchi'],
        language=data['language'],
        topic=data["topic"],
        pages=data["pages"],
        file_path=file_path
    )
    if test == "later":
        await message.answer("Please try again later")
        for admin in ADMINS:
            await message.answer(f"Diqqat Referat API da xatolik yoki API key eskirgan\nReferat yaratish bo'limida xato yuz berdi.\nXato yuz bergan foydalanuvchi: {user_id}")
        return

    # Send the document
    file = FSInputFile(file_path)
    await message.answer_document(document=file, caption="Bu sizning referatingiz. Iltimos o'zingiz ham bir ko'z tashlab o'ting.")
    contents_type = "referat"
    price = PRICES[contents_type]
    user_id = message.from_user.id
    #deduct the balance of the user
    deduct_balance(user_id, price)
    increment_user_usage(user_id)

    os.remove(file_path)

    # Finish the state
    await state.clear()


####################
# mustaqil ish yozish
####################
class MustaqilStates(StatesGroup):
    university = State()
    student_name = State()
    qabul_qiluvchi = State()
    mustaqil_language = State()
    topic = State()
    pages = State()
    
MUSTAQIL_TEXTS ={
    "📜 Mustaqil ish yozish",
    "📜 Написать самостоятельную работу",
    "📜 Write Independent Work"
}

MENU_TEXTS = REFERAT_TEXTS | TEZIS_TEXTS | MUSTAQIL_TEXTS | PRESENTATION_TEXTS | BALANCE_TEXTS
    

# Step 2: Start command
@dp.message(lambda m: m.text in MUSTAQIL_TEXTS)
async def mustaqil_start(message: Message, state: FSMContext):
    #calls the language getter funtion and equals to texts var
    data = await state.get_data()
    lang = data.get("til", "uz")
    texts = TRANSLATIONS[lang]
    #cleares the states except the user interface language
    await state.clear()

    user_id = message.from_user.id
    allowed, reason = can_generate(user_id, "mustaqil")
    
    if not allowed:
        if reason == "rate_limited":
            await message.answer(
                "❌ Too many requests. Please wait a moment before trying again."
            )
        elif reason == "blocked":
            payment = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts["make_payment"], callback_data="pay_start")]
            ])
            await message.answer(
                texts["alerta_payment"], reply_markup=payment
            )
        return
    
    mode = reason  # "free" or "paid"
    await state.update_data(til=lang, topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None, student_name=None)
 
    await message.answer(texts["university_mustaqil"])
    await state.set_state(MustaqilStates.university)

# Step 3: Collect university
@dp.message(MustaqilStates.university, lambda m: m.text not in MENU_TEXTS)
async def get_university(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(university=message.text.upper())
    await message.answer(texts["student_mustaqil"])
    await state.set_state(MustaqilStates.student_name)

# Step 4: Collect student name
@dp.message(MustaqilStates.student_name, lambda m: m.text not in MENU_TEXTS)
async def get_student_name(message: Message, state: FSMContext):
    texts = await get_texts(state)

    await state.update_data(student_name=message.text.title())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="O'zbek", callback_data="ref_lang:uz"),
            InlineKeyboardButton(text="Русский", callback_data="ref_lang:ru"),
            InlineKeyboardButton(text="English", callback_data="ref_lang:en")
        ]
    ])

    await message.answer(texts["language_mustaqil"], reply_markup=keyboard)
    await state.set_state(MustaqilStates.mustaqil_language)

@dp.callback_query(MustaqilStates.mustaqil_language, F.data.startswith("ref_lang:"))
async def set_referat_language(callback: CallbackQuery, state: FSMContext):
    texts = await get_texts(state)
    referat_lang = callback.data.split(":")[1]  # uz / ru / en

    await state.update_data(mustaqil_language=referat_lang)  # ✅ saved
    await callback.answer()

    # ✅ ask next question
    await callback.message.answer(texts["teacher_mustaqil"])

    # ✅ move FSM forward
    await state.set_state(MustaqilStates.qabul_qiluvchi)


# @dp.message(MustaqilStates.mustaqil_language, lambda m: m.text not in MENU_TEXTS)
# async def get_mustaqil_language(message: Message, state: FSMContext):
#     texts = await get_texts(state)
#     await state.update_data(language=message.text.title())
#     await message.answer(texts["teacher_mustaqil"])
#     await state.set_state(MustaqilStates.qabul_qiluvchi)

@dp.message(MustaqilStates.qabul_qiluvchi, lambda m: m.text not in MENU_TEXTS)
async def get_qabul_qiluvchi(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(qabul_qiluvchi=message.text.title())
    await message.answer(texts["topic_mustaqil"])
    await state.set_state(MustaqilStates.topic)

@dp.message(MustaqilStates.topic, lambda m: m.text not in MENU_TEXTS)
async def get_topic(message: Message, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(topic=message.text.title())
    await message.answer(texts["pages_mustaqil"])
    await state.set_state(MustaqilStates.pages)



# Step 5: Collect qabul qiluvchi and generate file  asl nusxa
@dp.message(MustaqilStates.pages, lambda m: m.text not in MENU_TEXTS)
async def get_pages(message: Message, bot: Bot, state: FSMContext):
    texts = await get_texts(state)
    await state.update_data(pages=message.text.title())
    data = await state.get_data()
    
    # # tayyor fayllarni topish funksiyasi
    topic = data["topic"].lower()

    # msg_id = get_message_id(topic)
    

    # if msg_id:
    #     # Ask the user what to do
    #     keyboard = InlineKeyboardMarkup(inline_keyboard=[
    #         [
    #             InlineKeyboardButton(text="📎 Ready presentation", callback_data=f"ready:{topic}"),
    #             InlineKeyboardButton(text="🆕 New one", callback_data=f"new:{topic}")
    #         ]
    #     ])

    #     await message.answer(
    #         f"A presentation already exists for '{topic}'.\n"
    #         "Do you want the ready one or create a new one?",
    #         reply_markup=keyboard
    #     )
    # else:
    user_id = message.from_user.id
    await message.answer(texts["mustaqil_generating"])
    file_path = f"referat_{user_id}_{int(time.time())}.docx"
    #check if API wokring
    

        # Generate the document
    test = await asyncio.to_thread(
        run_snip,
        university=data['university'],
        student=data['student_name'],
        teacher=data['qabul_qiluvchi'],
        language=data['mustaqil_language'],
        topic=data["topic"],
        pages=data["pages"],
        file_path=file_path
    )
    if test == "later":
        await message.answer("Please try again later")
        for admin in ADMINS:
            await message.answer(f"Diqqat Mustaqil ish API da xatolik yoki API key eskirgan\nMustaqil ish yaratish bilan muammo.\n Xatolik yuz bergan foydalanuvchi: {user_id}")
        return


    doc = FSInputFile(file_path)

    # ---- 1. SEND TO USER ----
    await message.answer_document(
        document=FSInputFile(file_path),
        caption=texts["caption_file"]
    )

    # 2. SEND TO CHANNEL WITH NEW NAME
    doc_renamed = FSInputFile(
        path=file_path,
        filename=f"{topic}.docx"
    )

    sent = await bot.send_document(
        chat_id=CHANNEL_ID,
        document=doc_renamed
    )
    
    contents_type = "mustaqil"
    price = PRICES[contents_type]
    user_id = message.from_user.id
    # deduct the balance of the user
    deduct_balance(user_id, price)
    increment_user_usage(user_id)
    # ---- 4. DELETE LOCAL FILE ----
    os.remove(file_path)
    await state.clear()

# @dp.callback_query(F.data.startswith("ready"))
# async def send_ready(callback: CallbackQuery, bot: Bot, state: FSMContext ):
#     topic = callback.data.split(":")[1]
#     file_ids = get_message_id(topic)  # must return a list of file_ids

#     if not file_ids:
#         await callback.message.answer("Bu mavzuga oid fayl topilmadi ❌")
#         await callback.answer()
#         return

#     # Load user data from FSM
#     data = await state.get_data()

#     if len(file_ids) > 1:
#         await callback.message.answer("Bu mavzuga oid bir nechta fayllar mavjud:")

#     for idx, file_id in enumerate(file_ids, start=1):
#         # 1️⃣ Download file from Telegram
#         tg_file = await bot.get_file(file_id)
#         original_path = f"temp/original_{callback.from_user.id}_{idx}.docx"
#         await bot.download_file(tg_file.file_path, original_path)

#         # 2️⃣ Edit file
#         edited_path = f"temp/edited_{callback.from_user.id}_{idx}.docx"
#         edited_file = edit_mustaqil(
#             input_path=original_path,
#             output_path=edited_path,
#             universitet=data.get("university", ""),
#             student_name=data.get("student_name", ""),
#             qabul_qiluvchi=data.get("qabul_qiluvchi", ""),
#             year=str(time.strftime("%Y"))
#         )

#         # 3️⃣ Send edited file to user
#         await bot.send_document(
#             chat_id=callback.message.chat.id,
#             document=FSInputFile(edited_file),
#             caption=f"📘 Mavzu: {topic} (fayl {idx})"
#         )

#         # 4️⃣ Cleanup temp files
#         os.remove(original_path)
#         os.remove(edited_path)

#     await callback.answer("Fayllar yuborildi ✅")




# @dp.callback_query(F.data.startswith("new"))
# async def create_new(callback: CallbackQuery, bot: Bot, state: FSMContext):
#     topic = callback.data.split(":")[1]

#     # Load saved FSM data
#     data = await state.get_data()

#     await callback.message.answer("Yangi mustaqil ish tayyorlanmoqda....")

#     # Generate unique filename
#     file_path = f"referat_{callback.from_user.id}_{int(time.time())}.docx"

#     # Generate the document
#     run_snip(
#         university=data['university'],
#         student=data['student_name'],
#         teacher=data['qabul_qiluvchi'],
#         language=data['language'],
#         topic=data["topic"],
#         pages=data["pages"],
#         file_path=file_path
#     )

#     doc = FSInputFile(file_path)

#     # ---- 1. SEND TO USER ----
#     await callback.message.answer_document(
#         document=doc,
#         caption="Bu sizning Mustaqil ishingiz. Iltimos ko‘z tashlab chiqing."
#     )

#     # ---- 2. SEND TO CHANNEL WITH RENAMED FILENAME ----
#     # Re-create FSInputFile from BYTES (file is already closed now)
#     with open(file_path, "rb") as f:
#         file_bytes = f.read()

#     doc_renamed = FSInputFile(
#         path=None,
#         file=file_bytes,
#         filename=f"{topic}.docx"   # <-- renamed filename for channel
#     )

#     sent = await bot.send_document(
#         chat_id=CHANNEL_ID,
#         document=doc_renamed
#     )

#     # ---- 3. SAVE topic → message_id ----
#     save_topic(topic, sent.message_id)

#     # ---- 4. DELETE LOCAL FILE ----
#     os.remove(file_path)

@dp.message(lambda m: m.text == "Statistika")
async def statistika_handler(message: Message, state: FSMContext):
    total_users, total_files, active_today, total_payments, payments_today, payments_30days = get_statistics()
    await state.clear()
    excel = export_monthly_income_to_excel()
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: {total_users}\n"
        f"📄 Umumiy fayllar yaratilgan: {total_files}\n"
        f"🟢 Bugungi faollik: {active_today} foydalanuvchi\n\n"
        f"💰 Umumiy to‘lovlar: {total_payments}\n"
        f"📅 Bugungi to‘lovlar: {payments_today}\n"
        f"📅 Bu oydagi  to‘lovlar: {payments_30days}\n"
    )
    await message.answer_document(
        document=FSInputFile(excel)
    )
    await message.answer(text, parse_mode="HTML")
    

@dp.message()
async def echo_handler(message: Message, state: FSMContext) -> None:
    texts = await get_texts(state)

    # Clear only specific FSM data, keep language
    await state.update_data(topic=None, pages=None, qabul_qiluvchi=None, university=None, language=None, student_name=None)

    # Alert user
    await message.answer(texts["menu_alert"])
    user_id = message.from_user.id
    # Get main menu keyboard
    menu = await get_main_menu(state, message, user_id)

    # Send main menu with proper text
    await message.answer(text=texts["start"], reply_markup=menu)

    


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    init_db()
    init_models_db()
    asyncio.run(main())