import config
import logging
import asyncio
import random
from aiogram import Bot, Dispatcher
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from base import SQL

db = SQL('db.db')

bot = Bot(token=config.TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# ─── Состояния игр в памяти ───────────────────────────────────────────────────
ttt_games = {}
guess_games = {}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Крестики нолики", callback_data="kr-nol")],
    [InlineKeyboardButton(text="🔢 Угадай число", callback_data="number")],
    [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
])

def get_score(user_id):
    return db.get_field("users", user_id, "score") or 0

def add_score(user_id, amount):
    vip = db.get_field("users", user_id, "vip") or 0
    double = db.get_field("users", user_id, "double_score") or 0
    if double:
        amount *= 2
        db.update_field("users", user_id, "double_score", 0)
    if vip:
        amount = int(amount * 1.5)
    current = get_score(user_id)
    db.update_field("users", user_id, "score", current + amount)

# ─── Магазин ──────────────────────────────────────────────────────────────────
def shop_keyboard(user_id):
    double = db.get_field("users", user_id, "double_score") or 0
    hint = db.get_field("users", user_id, "hint") or 0
    shield = db.get_field("users", user_id, "shield") or 0
    vip = db.get_field("users", user_id, "vip") or 0
    score = get_score(user_id)

    rows = []
    if not double:
        rows.append([InlineKeyboardButton(text="⚡ Двойные очки — 200", callback_data="buy_double")])
    else:
        rows.append([InlineKeyboardButton(text="⚡ Двойные очки (куплено)", callback_data="already")])

    if not hint:
        rows.append([InlineKeyboardButton(text="💡 Подсказка — 150", callback_data="buy_hint")])
    else:
        rows.append([InlineKeyboardButton(text="💡 Подсказка (куплено)", callback_data="already")])

    if not shield:
        rows.append([InlineKeyboardButton(text="🛡 Щит — 300", callback_data="buy_shield")])
    else:
        rows.append([InlineKeyboardButton(text="🛡 Щит (куплено)", callback_data="already")])

    if not vip:
        rows.append([InlineKeyboardButton(text="👑 VIP статус — 1500", callback_data="buy_vip")])
    else:
        rows.append([InlineKeyboardButton(text="👑 VIP статус (активен)", callback_data="already")])

    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def shop_text(user_id):
    score = get_score(user_id)
    vip = db.get_field("users", user_id, "vip") or 0
    double = db.get_field("users", user_id, "double_score") or 0
    hint = db.get_field("users", user_id, "hint") or 0
    shield = db.get_field("users", user_id, "shield") or 0
    inv = []
    if double: inv.append("⚡ Двойные очки")
    if hint: inv.append("💡 Подсказка")
    if shield: inv.append("🛡 Щит")
    if vip: inv.append("👑 VIP")
    inv_text = ", ".join(inv) if inv else "пусто"
    return (
        f"🛒 Магазин\n\n"
        f"💰 Твои очки: {score}\n"
        f"🎒 Инвентарь: {inv_text}\n\n"
        f"⚡ Двойные очки — 200 (следующая победа x2)\n"
        f"💡 Подсказка — 150 (диапазон ±10 в угадай число)\n"
        f"🛡 Щит — 300 (при поражении в крестики +25 очков)\n"
        f"👑 VIP статус — 1500 (постоянный x1.5 к очкам)"
    )

# ─── Утилиты крестиков-ноликов ────────────────────────────────────────────────
def ttt_keyboard(board):
    symbols = {"X": "❌", "O": "⭕", " ": "⬜"}
    rows = []
    for row in range(3):
        buttons = []
        for col in range(3):
            idx = row * 3 + col
            buttons.append(InlineKeyboardButton(
                text=symbols[board[idx]],
                callback_data=f"ttt_{idx}"
            ))
        rows.append(buttons)
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ttt_check_winner(board):
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6)
    ]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] != " ":
            return board[a]
    if " " not in board:
        return "draw"
    return None

def ttt_bot_move(board):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        line = [board[a], board[b], board[c]]
        if line.count("O") == 2 and line.count(" ") == 1:
            return [a,b,c][line.index(" ")]
    for a,b,c in wins:
        line = [board[a], board[b], board[c]]
        if line.count("X") == 2 and line.count(" ") == 1:
            return [a,b,c][line.index(" ")]
    if board[4] == " ":
        return 4
    free = [i for i, v in enumerate(board) if v == " "]
    return random.choice(free) if free else None

def ttt_board_text(board, status=""):
    symbols = {"X": "❌", "O": "⭕", " ": "⬜"}
    rows = []
    for r in range(3):
        rows.append(" ".join(symbols[board[r*3+c]] for c in range(3)))
    text = "\n".join(rows)
    if status:
        text += f"\n\n{status}"
    return text

end_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Играть снова", callback_data="kr-nol")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")],
])

# ─── Клавиатура угадай число ──────────────────────────────────────────────────
def guess_keyboard(user_id):
    hint = db.get_field("users", user_id, "hint") or 0
    rows = []
    if hint:
        rows.append([InlineKeyboardButton(text="💡 Использовать подсказку", callback_data="use_hint")])
    rows.append([InlineKeyboardButton(text="🏳 Сдаться", callback_data="guess_surrender")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

guess_win_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Играть снова", callback_data="number")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")],
])

# ─── Обработчик сообщений ─────────────────────────────────────────────────────
@dp.message()
async def handle_message(message):
    user_id = message.from_user.id
    if not db.user_exist(user_id):
        db.add_user(user_id)

    if user_id in guess_games:
        text = message.text.strip() if message.text else ""
        if text.lstrip("-").isdigit():
            number = guess_games[user_id]["number"]
            guess_games[user_id]["attempts"] += 1
            attempts = guess_games[user_id]["attempts"]
            guess = int(text)

            if guess < number:
                await message.answer(f"📈 Больше! Попытка {attempts}", reply_markup=guess_keyboard(user_id))
            elif guess > number:
                await message.answer(f"📉 Меньше! Попытка {attempts}", reply_markup=guess_keyboard(user_id))
            else:
                del guess_games[user_id]
                add_score(user_id, 20)
                score = get_score(user_id)
                await message.answer(
                    f"🎉 Правильно! Число было {number}. Угадал за {attempts} попыток.\n"
                    f"💰 +20 очков! Всего: {score}",
                    reply_markup=guess_win_keyboard
                )
        else:
            await message.answer("Введи целое число от 1 до 100", reply_markup=guess_keyboard(user_id))
        return

    await message.answer("Главное меню:", reply_markup=main_menu)

# ─── Обработчик inline кнопок ─────────────────────────────────────────────────
@dp.callback_query()
async def handle_callback(call):
    user_id = call.from_user.id
    data = call.data

    if not db.user_exist(user_id):
        db.add_user(user_id)

    await bot.answer_callback_query(call.id)

    # Главное меню
    if data == "menu":
        ttt_games.pop(user_id, None)
        guess_games.pop(user_id, None)
        await call.message.edit_text("Главное меню:", reply_markup=main_menu)
        return

    # Заглушка для уже купленных предметов
    if data == "already":
        await call.answer("У тебя уже есть этот предмет!", show_alert=True)
        return

    # ── Магазин ──────────────────────────────────────────────────────────────
    if data == "shop":
        await call.message.edit_text(shop_text(user_id), reply_markup=shop_keyboard(user_id))
        return

    if data.startswith("buy_"):
        item = data.split("_")[1]
        score = get_score(user_id)
        prices = {"double": 200, "hint": 150, "shield": 300, "vip": 1500}
        fields = {"double": "double_score", "hint": "hint", "shield": "shield", "vip": "vip"}
        names = {"double": "⚡ Двойные очки", "hint": "💡 Подсказка", "shield": "🛡 Щит", "vip": "👑 VIP статус"}

        price = prices[item]
        if score < price:
            await call.answer(f"Недостаточно очков! Нужно {price}, у тебя {score}.", show_alert=True)
            return

        db.update_field("users", user_id, "score", score - price)
        db.update_field("users", user_id, fields[item], 1)
        await call.answer(f"{names[item]} куплено!", show_alert=True)
        await call.message.edit_text(shop_text(user_id), reply_markup=shop_keyboard(user_id))
        return

    # ── Крестики-нолики ──────────────────────────────────────────────────────
    if data == "kr-nol":
        board = [" "] * 9
        ttt_games[user_id] = {"board": board}
        await call.message.edit_text(
            "❌ Крестики-нолики\nТы играешь за ❌. Твой ход:",
            reply_markup=ttt_keyboard(board)
        )
        return

    if data.startswith("ttt_"):
        if user_id not in ttt_games:
            await call.message.edit_text("Игра не найдена. Начни заново.", reply_markup=main_menu)
            return

        board = ttt_games[user_id]["board"]
        idx = int(data.split("_")[1])

        if board[idx] != " ":
            await call.answer("Эта клетка уже занята!", show_alert=True)
            return

        board[idx] = "X"
        result = ttt_check_winner(board)

        if result == "X":
            del ttt_games[user_id]
            add_score(user_id, 50)
            score = get_score(user_id)
            await call.message.edit_text(
                ttt_board_text(board, f"🎉 Ты победил! +50 очков! Всего: {score}"),
                reply_markup=end_keyboard
            )
            return
        elif result == "draw":
            del ttt_games[user_id]
            add_score(user_id, 15)
            score = get_score(user_id)
            await call.message.edit_text(
                ttt_board_text(board, f"🤝 Ничья! +15 очков! Всего: {score}"),
                reply_markup=end_keyboard
            )
            return

        bot_idx = ttt_bot_move(board)
        if bot_idx is not None:
            board[bot_idx] = "O"

        result = ttt_check_winner(board)

        if result == "O":
            del ttt_games[user_id]
            shield = db.get_field("users", user_id, "shield") or 0
            if shield:
                db.update_field("users", user_id, "shield", 0)
                add_score(user_id, 25)
                score = get_score(user_id)
                status = f"🤖 Бот победил! Но щит сработал — +25 очков! Всего: {score}"
            else:
                status = "🤖 Бот победил! +0 очков"
            await call.message.edit_text(
                ttt_board_text(board, status),
                reply_markup=end_keyboard
            )
            return
        elif result == "draw":
            del ttt_games[user_id]
            add_score(user_id, 15)
            score = get_score(user_id)
            await call.message.edit_text(
                ttt_board_text(board, f"🤝 Ничья! +15 очков! Всего: {score}"),
                reply_markup=end_keyboard
            )
            return

        await call.message.edit_text(
            ttt_board_text(board, "Твой ход:"),
            reply_markup=ttt_keyboard(board)
        )
        return

    # ── Угадай число ─────────────────────────────────────────────────────────
    if data == "number":
        number = random.randint(1, 100)
        guess_games[user_id] = {"number": number, "attempts": 0}
        await call.message.edit_text(
            "🔢 Угадай число от 1 до 100!\nПросто напиши число в чат.",
            reply_markup=guess_keyboard(user_id)
        )
        return

    if data == "guess_surrender":
        if user_id in guess_games:
            number = guess_games[user_id]["number"]
            del guess_games[user_id]
            await call.message.edit_text(
                f"🏳 Ты сдался. Загаданное число было {number}.",
                reply_markup=main_menu
            )
        return

    if data == "use_hint":
        if user_id not in guess_games:
            return
        hint = db.get_field("users", user_id, "hint") or 0
        if not hint:
            await call.answer("У тебя нет подсказки!", show_alert=True)
            return
        number = guess_games[user_id]["number"]
        db.update_field("users", user_id, "hint", 0)
        low = max(1, number - 10)
        high = min(100, number + 10)
        await call.answer(f"💡 Число находится между {low} и {high}", show_alert=True)
        return

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
