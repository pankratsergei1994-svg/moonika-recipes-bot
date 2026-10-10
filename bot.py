print("=== BOT STARTED ===")
import os
print("TOKEN EXISTS:", bool(os.getenv("BOT_TOKEN")))

import logging
import sqlite3
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
print("Creating bot...")
bot = Bot(token=BOT_TOKEN)
print("Bot created")

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

def init_db():
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, ingredients TEXT, steps TEXT, added_by TEXT, is_favorite INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

init_db()

class AddRecipe(StatesGroup):
    name = State()
    ingredients = State()
    steps = State()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить рецепт"), KeyboardButton(text="📋 Все рецепты")],
            [KeyboardButton(text="🎲 Случайный рецепт"), KeyboardButton(text="⭐ Избранное")],
        ],
        resize_keyboard=True
    )

@router.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Привет! 💕\n\nЭто общий бот с рецептами Мооники.\nВы оба можете добавлять блюда и смотреть их.", reply_markup=main_menu())

@router.message(F.text == "➕ Добавить рецепт")
async def add_start(message: types.Message, state: FSMContext):
    await state.set_state(AddRecipe.name)
    await message.answer("Введи название рецепта:")

@router.message(AddRecipe.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddRecipe.ingredients)
    await message.answer("Теперь напиши ингредиенты:")

@router.message(AddRecipe.ingredients)
async def add_ing(message: types.Message, state: FSMContext):
    await state.update_data(ingredients=message.text)
    await state.set_state(AddRecipe.steps)
    await message.answer("Опиши шаги приготовления:")

@router.message(AddRecipe.steps)
async def add_steps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    added_by = message.from_user.first_name or "Кто-то"
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("INSERT INTO recipes (name, ingredients, steps, added_by) VALUES (?, ?, ?, ?)", (data["name"], data["ingredients"], message.text, added_by))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ Рецепт сохранён!", reply_markup=main_menu())

@router.message(F.text == "📋 Все рецепты")
async def list_recipes(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Пока нет рецептов. Добавь первый!")
        return
    builder = InlineKeyboardBuilder()
    for rid, name in rows:
        builder.button(text=name, callback_data=f"view:{rid}")
    builder.adjust(1)
    await message.answer("Все рецепты:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("view:"))
async def view_recipe(callback: types.CallbackQuery):
    rid = int(callback.data.split(":")[1])
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT name, ingredients, steps, added_by, is_favorite FROM recipes WHERE id = ?", (rid,))
    row = c.fetchone()
    conn.close()
    if row:
        fav = "⭐" if row[4] else ""
        text = f"🍽 <b>{row[0]}</b> {fav}\n<i>Добавил(а): {row[3]}</i>\n\n<b>Ингредиенты:</b>\n{row[1]}\n\n<b>Приготовление:</b>\n{row[2]}"
        builder = InlineKeyboardBuilder()
        btn_text = "💔 Убрать из избранного" if row[4] else "⭐ В избранное"
        builder.button(text=btn_text, callback_data=f"fav:{rid}")
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("fav:"))
async def toggle_fav(callback: types.CallbackQuery):
    rid = int(callback.data.split(":")[1])
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT is_favorite FROM recipes WHERE id = ?", (rid,))
    current = c.fetchone()[0]
    new_val = 0 if current else 1
    c.execute("UPDATE recipes SET is_favorite = ? WHERE id = ?", (new_val, rid))
    conn.commit()
    conn.close()
    await callback.answer("Готово!")
    await callback.message.edit_reply_markup(reply_markup=None)

@router.message(F.text == "🎲 Случайный рецепт")
async def random_recipe(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT name, ingredients, steps FROM recipes ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        text = f"🎲 <b>{row[0]}</b>\n\n<b>Ингредиенты:</b>\n{row[1]}\n\n<b>Приготовление:</b>\n{row[2]}"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("Пока нет рецептов.")

@router.message(F.text == "⭐ Избранное")
async def favorites(message: types.Message):
    conn = sqlite3.connect("recipes.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes WHERE is_favorite = 1 ORDER BY name")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("В избранном пока пусто.")
        return
    builder = InlineKeyboardBuilder()
    for rid, name in rows:
        builder.button(text=name, callback_data=f"view:{rid}")
    builder.adjust(1)
    await message.answer("⭐ Избранные рецепты:", reply_markup=builder.as_markup())

async def main():
    print("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
