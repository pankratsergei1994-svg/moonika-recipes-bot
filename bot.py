import os
import logging
import sqlite3
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

def init_db():
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, ingredients TEXT, steps TEXT, photo_file_id TEXT, category TEXT, added_by TEXT, is_favorite INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

init_db()

CATEGORIES = ["Завтрак", "Обед", "Ужин", "Десерт", "Закуска", "Напиток", "Другое"]

class AddRecipe(StatesGroup):
    name = State()
    category = State()
    ingredients = State()
    steps = State()
    photo = State()

class EditRecipe(StatesGroup):
    choose = State()
    field = State()
    new_value = State()

class Search(StatesGroup):
    query = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить рецепт"), KeyboardButton(text="📋 Все рецепты")],
        [KeyboardButton(text="🎲 Случайный"), KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="🛒 Список покупок")],
    ], resize_keyboard=True)

@router.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! 💕\nОбщий бот рецептов Мооники.\nДобавляйте, ищите и готовьте вместе.", reply_markup=main_menu())

# ===== ДОБАВЛЕНИЕ =====
@router.message(F.text == "➕ Добавить рецепт")
async def add_start(message: types.Message, state: FSMContext):
    await state.set_state(AddRecipe.name)
    await message.answer("Название рецепта:")

@router.message(AddRecipe.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        builder.button(text=cat, callback_data=f"cat:{cat}")
    builder.adjust(2)
    await state.set_state(AddRecipe.category)
    await message.answer("Выбери категорию:", reply_markup=builder.as_markup())

@router.callback_query(AddRecipe.category, F.data.startswith("cat:"))
async def add_category(callback: types.CallbackQuery, state: FSMContext):
    cat = callback.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(AddRecipe.ingredients)
    await callback.message.answer("Ингредиенты:")
    await callback.answer()

@router.message(AddRecipe.ingredients)
async def add_ing(message: types.Message, state: FSMContext):
    await state.update_data(ingredients=message.text)
    await state.set_state(AddRecipe.steps)
    await message.answer("Шаги приготовления:")

@router.message(AddRecipe.steps)
async def add_steps(message: types.Message, state: FSMContext):
    await state.update_data(steps=message.text)
    await state.set_state(AddRecipe.photo)
    await message.answer("Отправь фото блюда или напиши «пропустить»:")

@router.message(AddRecipe.photo, F.photo)
async def add_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_recipe(message, state, photo_id)

@router.message(AddRecipe.photo, F.text)
async def add_photo_skip(message: types.Message, state: FSMContext):
    await save_recipe(message, state, None)

async def save_recipe(message, state, photo_id):
    data = await state.get_data()
    added_by = message.from_user.first_name or "Кто-то"
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("INSERT INTO recipes (name, ingredients, steps, photo_file_id, category, added_by) VALUES (?, ?, ?, ?, ?, ?)",
              (data["name"], data["ingredients"], data["steps"], photo_id, data.get("category"), added_by))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ Рецепт сохранён!", reply_markup=main_menu())

# ===== СПИСОК И ПРОСМОТР =====
@router.message(F.text == "📋 Все рецепты")
async def list_recipes(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id, name, category FROM recipes ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Пока нет рецептов.")
        return
    builder = InlineKeyboardBuilder()
    for rid, name, cat in rows:
        label = f"{name} ({cat})" if cat else name
        builder.button(text=label, callback_data=f"view:{rid}")
    builder.adjust(1)
    await message.answer("Все рецепты:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("view:"))
async def view_recipe(callback: types.CallbackQuery):
    rid = int(callback.data.split(":")[1])
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT name, ingredients, steps, photo_file_id, category, added_by, is_favorite FROM recipes WHERE id = ?", (rid,))
    row = c.fetchone()
    conn.close()
    if not row:
        await callback.answer("Не найдено")
        return
    name, ingredients, steps, photo, cat, added_by, fav = row
    text = f"🍽 <b>{name}</b>\nКатегория: {cat or '—'}\n<i>Добавил(а): {added_by}</i>\n\n<b>Ингредиенты:</b>\n{ingredients}\n\n<b>Приготовление:</b>\n{steps}"
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ В избранное" if not fav else "💔 Убрать", callback_data=f"fav:{rid}")
    builder.button(text="🗑 Удалить", callback_data=f"del:{rid}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{rid}")
    builder.adjust(2)
    if photo:
        await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("fav:"))
async def toggle_fav(callback: types.CallbackQuery):
    rid = int(callback.data.split(":")[1])
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT is_favorite FROM recipes WHERE id = ?", (rid,))
    current = c.fetchone()[0]
    c.execute("UPDATE recipes SET is_favorite = ? WHERE id = ?", (0 if current else 1, rid))
    conn.commit()
    conn.close()
    await callback.answer("Готово!")

@router.callback_query(F.data.startswith("del:"))
async def delete_recipe(callback: types.CallbackQuery):
    rid = int(callback.data.split(":")[1])
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("DELETE FROM recipes WHERE id = ?", (rid,))
    conn.commit()
    conn.close()
    await callback.message.answer("Рецепт удалён.")
    await callback.answer()

# ===== СЛУЧАЙНЫЙ И ИЗБРАННОЕ =====
@router.message(F.text == "🎲 Случайный")
async def random_recipe(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id FROM recipes ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        await view_recipe_by_id(message, row[0])
    else:
        await message.answer("Нет рецептов.")

async def view_recipe_by_id(message, rid):
    # упрощённый вызов просмотра
    fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="", message=message, data=f"view:{rid}")
    await view_recipe(fake_callback)

@router.message(F.text == "⭐ Избранное")
async def favorites(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes WHERE is_favorite = 1")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Избранное пусто.")
        return
    builder = InlineKeyboardBuilder()
    for rid, name in rows:
        builder.button(text=name, callback_data=f"view:{rid}")
    builder.adjust(1)
    await message.answer("⭐ Избранное:", reply_markup=builder.as_markup())

# ===== ПОИСК =====
@router.message(F.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(Search.query)
    await message.answer("Введи название или часть названия:")

@router.message(Search.query)
async def search_do(message: types.Message, state: FSMContext):
    q = f"%{message.text}%"
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes WHERE name LIKE ? OR ingredients LIKE ?", (q, q))
    rows = c.fetchall()
    conn.close()
    await state.clear()
    if not rows:
        await message.answer("Ничего не найдено.", reply_markup=main_menu())
        return
    builder = InlineKeyboardBuilder()
    for rid, name in rows:
        builder.button(text=name, callback_data=f"view:{rid}")
    builder.adjust(1)
    await message.answer("Результаты поиска:", reply_markup=builder.as_markup())

# ===== СПИСОК ПОКУПОК =====
@router.message(F.text == "🛒 Список покупок")
async def shopping(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT name, ingredients FROM recipes")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Нет рецептов.")
        return
    text = "🛒 <b>Список покупок</b>\n\n"
    for name, ing in rows:
        text += f"<b>{name}:</b>\n{ing}\n\n"
    await message.answer(text, parse_mode="HTML")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
