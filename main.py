from telegram import Update, User
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import random
import json
import os

# === НАСТРОЙКИ ===
BOT_TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН_ЗДЕСЬ"  # ← замени на свой!
BALANCE_FILE = "balances.json"

# Загружаем балансы
def load_balances():
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_balances(balances):
    with open(BALANCE_FILE, "w") as f:
        json.dump(balances, f)

# Получаем ID пользователя из упоминания или объекта
def get_user_id(user_input: str, update: Update) -> str:
    if user_input.startswith("@"):
        # Пока не можем разрешить username → используем ID из ответа
        # В MVP будем просить отвечать на сообщение
        return None
    return user_input

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    balances = load_balances()
    user_id = str(user.id)
    if user_id not in balances:
        balances[user_id] = 500
        save_balances(balances)
    await update.message.reply_text(
        f"Привет, {user.first_name}! 💰 Твой баланс: {balances[user_id]} монет.\n\n"
        "Чтобы вызвать на дуэль, ответь на сообщение друга и напиши:\n/duel 100"
    )

# Команда /balance
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    balances = load_balances()
    bal = balances.get(str(user.id), 500)
    await update.message.reply_text(f"💰 Баланс: {bal} монет")

# Команда /duel — вызов
async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответь на сообщение игрока и напиши: /duel [ставка]")
        return

    if not context.args:
        await update.message.reply_text("❌ Укажи ставку: /duel 100")
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом!")
        return

    if bet < 10:
        await update.message.reply_text("❌ Минимальная ставка: 10 монет")
        return

    challenger = update.effective_user
    opponent = update.message.reply_to_message.from_user

    if challenger.id == opponent.id:
        await update.message.reply_text("❌ Нельзя играть сам с собой!")
        return

    balances = load_balances()
    ch_id = str(challenger.id)
    op_id = str(opponent.id)

    # Инициализация балансов
    if ch_id not in balances:
        balances[ch_id] = 500
    if op_id not in balances:
        balances[op_id] = 500

    if balances[ch_id] < bet:
        await update.message.reply_text("❌ Недостаточно монет!")
        return

    save_balances(balances)

    # Сохраняем состояние дуэли в контексте (временно — для MVP)
    context.bot_data[f"duel_{op_id}"] = {
        "challenger_id": ch_id,
        "opponent_id": op_id,
        "bet": bet,
        "challenger_name": challenger.first_name,
        "opponent_name": opponent.first_name,
    }

    await update.message.reply_text(
        f"{challenger.first_name} вызывает {opponent.first_name} на дуэль!\n"
        f"Ставка: {bet} монет 🎲\n\n"
        f"{opponent.first_name}, напиши «Принимаю», чтобы начать!"
    )

# Обработка сообщения "Принимаю"
async def handle_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)

    duel_key = f"duel_{user_id}"
    if duel_key not in context.bot_data:
        return  # не относится к дуэли

    duel_data = context.bot_data[duel_key]
    if duel_data["opponent_id"] != user_id:
        return

    # Начинаем дуэль
    ch_name = duel_data["challenger_name"]
    op_name = duel_data["opponent_name"]
    bet = duel_data["bet"]

    await update.message.reply_text(f"🎲 Дуэль началась! Ставка: {bet} монет")

    ch_score = 0
    op_score = 0

    for round_num in range(1, 4):
        await update.message.reply_text(f"Раунд {round_num}...")
        await update.message.reply_text("🎲 🎲", disable_notification=True)
        await update.message.reply_text("...", disable_notification=True)

        ch_roll = random.randint(1, 6)
        op_roll = random.randint(1, 6)

        if ch_roll > op_roll:
            ch_score += 1
        elif op_roll > ch_roll:
            op_score += 1

        await update.message.reply_text(f"{ch_name}: {ch_roll} — {op_name}: {op_roll}")

    # Итог
    balances = load_balances()
    ch_id = duel_data["challenger_id"]
    op_id = duel_data["opponent_id"]

    if ch_score > op_score:
        winner, winner_id = ch_name, ch_id
        balances[ch_id] += bet
        balances[op_id] -= bet
    elif op_score > ch_score:
        winner, winner_id = op_name, op_id
        balances[op_id] += bet
        balances[ch_id] -= bet
    else:
        winner = "Ничья!"
        # Ставка возвращается — ничего не меняем

    save_balances(balances)

    if ch_score != op_score:
        await update.message.reply_text(f"🏆 Победил(а) {winner}! Выигрыш: {bet} монет")
    else:
        await update.message.reply_text("🤝 Ничья! Ставки возвращены.")

    # Удаляем дуэль
    del context.bot_data[duel_key]

# Основной запуск
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("duel", duel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_accept))

    application.run_polling()
