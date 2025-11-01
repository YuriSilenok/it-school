import os
import logging
import json
from PIL import Image
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (замените на ваш)
BOT_TOKEN = "7714646750:AAE-4OPcjUKiG5-9d9uXBehIIKvbkKEkkmc"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Создаем папки для хранения файлов
os.makedirs("temp_images", exist_ok=True)
os.makedirs("stickers", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Файл для хранения данных о стикерпаках
STICKER_PACKS_FILE = "data/sticker_packs.json"

# Словарь для временного хранения file_id (решение проблемы длинного callback_data)
temp_sticker_data = {}

# Состояния FSM
class StickerCreation(StatesGroup):
    waiting_for_photo = State()
    waiting_for_problem = State()
    waiting_for_pack_name = State()
    waiting_for_sticker_to_add = State()

# Меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить стикер"), KeyboardButton(text="📦 Добавить в стикерпак")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="👀 Мои стикерпаки")]
    ],
    resize_keyboard=True
)

# Функции для работы с JSON
def load_sticker_packs():
    if os.path.exists(STICKER_PACKS_FILE):
        with open(STICKER_PACKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_sticker_packs(data):
    with open(STICKER_PACKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_sticker_packs(user_id):
    packs = load_sticker_packs()
    return packs.get(str(user_id), {})

def save_user_sticker_pack(user_id, pack_name, sticker_files):
    packs = load_sticker_packs()
    if str(user_id) not in packs:
        packs[str(user_id)] = {}
    
    packs[str(user_id)][pack_name] = sticker_files
    save_sticker_packs(packs)

# Функции для работы с временными данными стикеров
def save_temp_sticker_data(user_id, short_id, file_id, sticker_path):
    if str(user_id) not in temp_sticker_data:
        temp_sticker_data[str(user_id)] = {}
    temp_sticker_data[str(user_id)][short_id] = {
        'file_id': file_id,
        'sticker_path': sticker_path
    }

def get_temp_sticker_data(user_id, short_id):
    return temp_sticker_data.get(str(user_id), {}).get(short_id)

def generate_short_id():
    import uuid
    return str(uuid.uuid4())[:8]  # Берем только первые 8 символов

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для создания стикеров.",
        reply_markup=main_menu
    )

@dp.message(F.text == "➕ Добавить стикер")
async def add_sticker(message: Message, state: FSMContext):
    await message.answer(
        "Пришли фото для стикера",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StickerCreation.waiting_for_photo)

@dp.message(StickerCreation.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаем уникальное имя файла
        user_id = message.from_user.id
        temp_filename = f"temp_images/{user_id}_{file_id}.jpg"
        sticker_filename = f"stickers/{user_id}_{file_id}.webp"
        
        # Скачиваем файл
        await bot.download_file(file_path, temp_filename)
        
        # Конвертируем в стикер (WebP формат)
        with Image.open(temp_filename) as img:
            # Ресайзим изображение до размера стикера (512x512)
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            
            # Конвертируем в WebP
            img.save(sticker_filename, "WEBP", quality=80)
        
        # Генерируем короткий ID для callback_data
        short_id = generate_short_id()
        
        # Сохраняем информацию о стикере во временном хранилище
        save_temp_sticker_data(user_id, short_id, file_id, sticker_filename)
        
        # Сохраняем информацию о стикере в состоянии
        await state.update_data(
            last_sticker=sticker_filename,
            sticker_file_id=file_id,
            short_id=short_id
        )
        
        # Создаем инлайн клавиатуру для быстрого добавления в стикерпак
        quick_add_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Добавить в стикерпак", callback_data=f"qa_{short_id}")],  # Короткий callback_data
                [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")]
            ]
        )
        
        # Отправляем стикер пользователю
        with open(sticker_filename, "rb") as sticker_file:
            await message.answer_document(
                document=types.BufferedInputFile(
                    sticker_file.read(),
                    filename=f"sticker_{user_id}.webp"
                ),
                caption="✅ Ваш стикер готов!\n\nВы можете добавить его в стикерпак или создать новый стикерпак.",
                reply_markup=quick_add_keyboard
            )
        
        # Очищаем временные файлы
        os.remove(temp_filename)
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке фото. Попробуйте еще раз.",
            reply_markup=main_menu
        )
        await state.clear()

@dp.message(StickerCreation.waiting_for_photo)
async def wrong_photo_input(message: Message):
    await message.answer("📸 Пожалуйста, отправьте фото для создания стикера.")

@dp.message(F.text == "📦 Добавить в стикерпак")
async def add_to_stickerpack(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_packs = get_user_sticker_packs(user_id)
    
    if not user_packs:
        # Если стикерпаков нет, предлагаем создать первый
        await message.answer(
            "📦 У вас еще нет стикерпаков. Давайте создадим первый!\n\n"
            "Введите название для нового стикерпака:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(StickerCreation.waiting_for_pack_name)
    else:
        # Если стикерпаки есть, показываем список
        packs_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"📦 {pack_name}", callback_data=f"sp_{pack_name}")]  # Короткий callback_data
                for pack_name in list(user_packs.keys())[:10]  # Ограничиваем количество для безопасности
            ] + [
                [InlineKeyboardButton(text="➕ Создать новый стикерпак", callback_data="new_pack")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ]
        )
        
        await message.answer(
            "📦 Выберите стикерпак для добавления стикера:",
            reply_markup=packs_keyboard
        )

@dp.callback_query(F.data.startswith("qa_"))  # Quick Add
async def quick_add_to_pack(callback: types.CallbackQuery, state: FSMContext):
    short_id = callback.data.replace("qa_", "")
    user_id = callback.from_user.id
    
    # Получаем данные стикера из временного хранилища
    sticker_data = get_temp_sticker_data(user_id, short_id)
    
    if sticker_data:
        await state.update_data(
            selected_sticker=sticker_data['sticker_path'],
            sticker_file_id=sticker_data['file_id']
        )
        await add_to_stickerpack(callback.message, state)
    else:
        await callback.answer("❌ Стикер не найден. Создайте новый стикер.")
    
    await callback.answer()

@dp.callback_query(F.data == "new_pack")  # Create New Pack
async def create_new_pack(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📦 Введите название для нового стикерпака:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StickerCreation.waiting_for_pack_name)
    await callback.answer()

@dp.callback_query(F.data.startswith("sp_"))  # Select Pack
async def select_existing_pack(callback: types.CallbackQuery, state: FSMContext):
    pack_name = callback.data.replace("sp_", "")
    user_data = await state.get_data()
    selected_sticker = user_data.get('selected_sticker')
    
    if not selected_sticker:
        # Если стикер не выбран, просим отправить фото
        await callback.message.answer(
            "📸 Пришлите фото для добавления в стикерпак:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.update_data(selected_pack=pack_name)
        await state.set_state(StickerCreation.waiting_for_sticker_to_add)
    else:
        # Добавляем существующий стикер в пак
        await add_sticker_to_pack(callback.message, callback.from_user.id, pack_name, selected_sticker)
        await state.clear()
    
    await callback.answer()

@dp.message(StickerCreation.waiting_for_pack_name)
async def process_pack_name(message: Message, state: FSMContext):
    pack_name = message.text.strip()
    user_id = message.from_user.id
    
    if len(pack_name) < 2:
        await message.answer("❌ Название стикерпака должно содержать минимум 2 символа.")
        return
    
    # Ограничиваем длину названия пакета для callback_data
    if len(pack_name) > 30:
        await message.answer("❌ Название стикерпака слишком длинное. Используйте до 30 символов.")
        return
    
    user_packs = get_user_sticker_packs(user_id)
    
    if pack_name in user_packs:
        await message.answer("❌ Стикерпак с таким названием уже существует. Выберите другое название.")
        return
    
    # Создаем пустой стикерпак
    save_user_sticker_pack(user_id, pack_name, [])
    
    await state.update_data(selected_pack=pack_name)
    await message.answer(
        f"✅ Стикерпак '{pack_name}' создан!\n\n"
        f"📸 Теперь пришлите фото для добавления в стикерпак:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StickerCreation.waiting_for_sticker_to_add)

@dp.message(StickerCreation.waiting_for_sticker_to_add, F.photo)
async def process_sticker_for_pack(message: Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        pack_name = user_data.get('selected_pack')
        user_id = message.from_user.id
        
        if not pack_name:
            await message.answer("❌ Ошибка: стикерпак не выбран.")
            await state.clear()
            return
        
        # Скачиваем и обрабатываем фото
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        temp_filename = f"temp_images/{user_id}_{file_id}.jpg"
        sticker_filename = f"stickers/{user_id}_{file_id}_pack.webp"
        
        await bot.download_file(file_path, temp_filename)
        
        with Image.open(temp_filename) as img:
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            img.save(sticker_filename, "WEBP", quality=80)
        
        # Добавляем стикер в пак
        await add_sticker_to_pack(message, user_id, pack_name, sticker_filename)
        
        # Очищаем временные файлы
        os.remove(temp_filename)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing sticker for pack: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке фото. Попробуйте еще раз.",
            reply_markup=main_menu
        )
        await state.clear()

async def add_sticker_to_pack(message: Message, user_id: int, pack_name: str, sticker_filename: str):
    try:
        user_packs = get_user_sticker_packs(user_id)
        
        if pack_name not in user_packs:
            user_packs[pack_name] = []
        
        # Добавляем стикер в пак
        user_packs[pack_name].append(sticker_filename)
        save_user_sticker_pack(user_id, pack_name, user_packs[pack_name])
        
        sticker_count = len(user_packs[pack_name])
        
        # Создаем клавиатуру для дальнейших действий
        actions_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Добавить еще стикер", callback_data=f"sp_{pack_name}")],
                [InlineKeyboardButton(text="👀 Посмотреть стикерпак", callback_data=f"vp_{pack_name}")],  # Короткий callback_data
                [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")]
            ]
        )
        
        await message.answer(
            f"✅ Стикер успешно добавлен в стикерпак '{pack_name}'!\n\n"
            f"📊 Всего стикеров в паке: {sticker_count}",
            reply_markup=actions_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error adding sticker to pack: {e}")
        await message.answer("❌ Ошибка при добавлении стикера в стикерпак.")

@dp.message(F.text == "👀 Мои стикерпаки")
async def show_my_stickerpacks(message: Message):
    user_id = message.from_user.id
    user_packs = get_user_sticker_packs(user_id)
    
    if not user_packs:
        await message.answer("📦 У вас пока нет стикерпаков. Создайте первый с помощью кнопки '📦 Добавить в стикерпак'")
        return
    
    packs_list = "\n".join([f"📦 {pack_name} ({len(stickers)} стикеров)" for pack_name, stickers in user_packs.items()])
    
    packs_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"👀 {pack_name} ({len(stickers)} шт.)", callback_data=f"vp_{pack_name}")]  # Короткий callback_data
            for pack_name, stickers in list(user_packs.items())[:10]  # Ограничиваем количество
        ] + [
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await message.answer(
        f"📦 Ваши стикерпаки:\n\n{packs_list}",
        reply_markup=packs_keyboard
    )

@dp.callback_query(F.data.startswith("vp_"))  # View Pack
async def view_stickerpack(callback: types.CallbackQuery):
    pack_name = callback.data.replace("vp_", "")
    user_id = callback.from_user.id
    user_packs = get_user_sticker_packs(user_id)
    
    if pack_name not in user_packs:
        await callback.answer("❌ Стикерпак не найден")
        return
    
    stickers = user_packs[pack_name]
    
    if not stickers:
        await callback.message.answer(f"📦 Стикерпак '{pack_name}' пустой.")
        await callback.answer()
        return
    
    # Отправляем первый стикер из пака
    try:
        with open(stickers[0], "rb") as sticker_file:
            await callback.message.answer_document(
                document=types.BufferedInputFile(
                    sticker_file.read(),
                    filename=f"sticker_from_{pack_name}.webp"
                ),
                caption=f"📦 Стикерпак: {pack_name}\n🎯 Стикеров: {len(stickers)}\n\nИспользуйте кнопки ниже для управления:"
            )
        
        # Клавиатура для управления стикерпаком
        manage_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить стикер", callback_data=f"sp_{pack_name}")],
                [InlineKeyboardButton(text="🗑️ Удалить стикерпак", callback_data=f"dp_{pack_name}")],  # Короткий callback_data
                [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_packs_list")]
            ]
        )
        
        await callback.message.answer(
            f"Управление стикерпаком '{pack_name}':",
            reply_markup=manage_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error viewing stickerpack: {e}")
        await callback.message.answer("❌ Ошибка при загрузке стикерпака.")
    
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_packs_list")
async def back_to_packs_list(callback: types.CallbackQuery):
    await show_my_stickerpacks(callback.message)
    await callback.answer()

# Остальной код (помощь и другие функции) остается без изменений
@dp.message(F.text == "❓ Помощь")
async def help_command(message: Message, state: FSMContext):
    await message.answer(
        "Опишите вашу проблему, и я постараюсь помочь:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StickerCreation.waiting_for_problem)

@dp.message(StickerCreation.waiting_for_problem)
async def process_problem(message: Message, state: FSMContext):
    user_problem = message.text
    user_id = message.from_user.id
    
    # Логируем проблему
    logger.info(f"User {user_id} reported problem: {user_problem}")
    
    # Простые решения для распространенных проблем
    solutions = {
        "стикер": "Для создания стикера отправьте четкое фото с хорошим освещением. "
                  "Изображение будет автоматически преобразовано в квадратный формат 512x512 пикселей.",
        "стикерпак": "Стикерпак - это коллекция стикеров. Вы можете создавать несколько стикерпаков "
                     "и добавлять в них созданные стикеры.",
        "фото": "Пожалуйста, убедитесь, что отправляете изображение в формате JPEG или PNG. "
                "Размер файла не должен превышать 20MB.",
        "ошибка": "Если возникла ошибка, попробуйте перезапустить бота командой /start "
                  "или отправьте фото заново.",
        "качество": "Для лучшего качества стикера используйте фото с высоким разрешением "
                    "и минимальным количеством деталей на фоне.",
        "формат": "Бот автоматически конвертирует фото в формат WebP, который используется для Telegram стикеров."
    }
    
    # Ищем ключевые слова в проблеме
    problem_lower = user_problem.lower()
    suggested_solutions = []
    
    for keyword, solution in solutions.items():
        if keyword in problem_lower:
            suggested_solutions.append(solution)
    
    if suggested_solutions:
        response = "Вот возможные решения вашей проблемы:\n\n" + "\n\n".join(suggested_solutions)
    else:
        response = (
            "Спасибо за обращение! Я записал вашу проблему. "
            "Вот общие рекомендации:\n\n"
            "1. Для создания стикера отправляйте четкие фото\n"
            "2. Убедитесь, что основной объект хорошо виден\n"
            "3. Используйте фото с простым фоном для лучшего результата\n"
            "4. Размер файла не должен превышать 20MB\n"
            "5. Вы можете создавать стикерпаки для организации своих стикеров"
        )
    
    await message.answer(response, reply_markup=main_menu)
    await state.clear()

@dp.message(Command("help"))
async def help_direct(message: Message):
    await message.answer(
        "Я бот для создания стикеров! Вот что я умею:\n\n"
        "➕ Добавить стикер - создайте стикер из фото\n"
        "📦 Добавить в стикерпак - добавьте стикер в коллекцию\n"
        "👀 Мои стикерпаки - просмотрите ваши стикерпаки\n"
        "❓ Помощь - получите помощь по использованию бота\n\n"
        "Просто нажмите на кнопку в меню ниже:",
        reply_markup=main_menu
    )

@dp.message()
async def handle_other_messages(message: Message):
    await message.answer(
        "Используйте кнопки меню для навигации:",
        reply_markup=main_menu
    )

async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())