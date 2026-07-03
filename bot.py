import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from config import BOT_TOKEN
from database import Database

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

NAME, COST, DATE = range(3)
db = Database()


# ============================================================
# 1️⃣ REPLY-КЛАВИАТУРА (внизу экрана)
# ============================================================
async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все подписки (Reply)"""
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)
    
    if not subs:
        await update.message.reply_text("📭 У вас пока нет подписок.", reply_markup=get_reply_keyboard())
        return
    
    text = "📋 **Ваши подписки:**\n\n"
    for sub_id, name, cost, renewal in subs:
        text += f"🆔 {sub_id} • **{name}**\n"
        text += f"   💰 {cost:.2f} ₽   📅 {renewal}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_reply_keyboard())


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику (Reply)"""
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)
    
    if not subs:
        await update.message.reply_text("📭 У вас пока нет подписок.", reply_markup=get_reply_keyboard())
        return
    
    total_cost = db.get_total_cost(user_id)
    
    text = "📊 **Статистика подписок**\n\n"
    text += f"📝 Всего подписок: {len(subs)}\n"
    text += f"💰 Общая стоимость в месяц: {total_cost:.2f} ₽\n"
    text += f"💰 В год: {total_cost * 12:.2f} ₽\n\n"
    
    text += "📋 **Детали:**\n"
    for sub in subs:
        sub_id, name, cost, renewal = sub
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        status = "🔴" if days_left < 0 else "🟢" if days_left > 30 else "🟡"
        text += f"{status} {name}: {cost:.2f} ₽ (осталось {days_left} дн.)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_reply_keyboard())


async def due_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подписки, которые скоро истекают (Reply)"""
    user_id = update.effective_user.id
    due_subs = db.get_due_soon(user_id, 7)
    
    if not due_subs:
        await update.message.reply_text("🔔 Нет подписок, истекающих в ближайшие 7 дней.", reply_markup=get_reply_keyboard())
        return
    
    text = "🔔 **Подписки, истекающие в ближайшие 7 дней:**\n\n"
    for sub in due_subs:
        sub_id, name, cost, renewal = sub
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        text += f"🆔 {sub_id} • **{name}**\n"
        text += f"   💰 {cost:.2f} ₽   📅 {renewal} (осталось {days_left} дн.)\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_reply_keyboard())
def get_reply_keyboard():
    """Клавиатура внизу экрана (ReplyKeyboard)"""
    keyboard = [
        [KeyboardButton("📝 Добавить подписку")],
        [KeyboardButton("📋 Мои подписки"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🔔 Скоро истекают"), KeyboardButton("🔄 Продлить")],
        [KeyboardButton("🗑️ Удалить"), KeyboardButton("🔙 Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ============================================================
# 2️⃣ ОБРАБОТЧИК REPLY-КНОПОК (текстовые кнопки внизу)
# ============================================================

async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на ReplyKeyboard"""
    text = update.message.text

    # Если бот ждёт ввод — отправляем в диалог
    if context.user_data.get('expecting'):
        await handle_message(update, context)
        return

    if text == "📝 Добавить подписку":
        await add_start(update, context)
    elif text == "📋 Мои подписки":
        await list_subscriptions(update, context)
    elif text == "📊 Статистика":
        await stats(update, context)
    elif text == "🔔 Скоро истекают":
        await due_soon(update, context)
    elif text == "🔄 Продлить":
        await renew_reply(update, context)
    elif text == "🗑️ Удалить":
        await delete_reply(update, context)
    elif text == "🔙 Назад":  # ← КНОПКА НАЗАД В ГЛАВНОМ МЕНЮ
        await update.message.reply_text(
            "👋 **Главное меню**\n\n"
            "Выбери действие 👇",
            parse_mode='Markdown',
            reply_markup=get_reply_keyboard()
        )
    else:
        await update.message.reply_text("❌ Неизвестная команда.", reply_markup=get_reply_keyboard())
# ============================================================
# 3️⃣ REPLY-ФУНКЦИИ (для кнопок внизу)
# ============================================================

async def renew_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продление подписки через Reply (ввод ID)"""
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("📭 У вас нет подписок.", reply_markup=get_reply_keyboard())
        return

    text = "🔄 **Введите ID подписки для продления:**\n\n"
    for sub_id, name, cost, renewal in subs:
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        status = "🔴" if days_left < 0 else "🟢" if days_left > 30 else "🟡"
        text += f"{status} 🆔 {sub_id} • **{name}** — {cost:.2f} ₽ (до {renewal}, {days_left} дн.)\n"

    context.user_data['expecting'] = 'renew_id'
    await update.message.reply_text(text, parse_mode='Markdown')


async def delete_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление подписки через Reply (ввод ID)"""
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("📭 У вас нет подписок.", reply_markup=get_reply_keyboard())
        return

    text = "🗑️ **Введите ID подписки для удаления:**\n\n"
    for sub_id, name, cost, renewal in subs:
        text += f"🆔 {sub_id} • **{name}** — {cost:.2f} ₽ (до {renewal})\n"

    context.user_data['expecting'] = 'delete_id'
    await update.message.reply_text(text, parse_mode='Markdown')


# ============================================================
# 4️⃣ ОБРАБОТЧИК ВВОДА (диалог)
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений в диалоге"""
    text = update.message.text
    user_id = update.effective_user.id

    # ===== КНОПКА "НАЗАД" =====
    if text == "🔙 Назад":
        context.user_data['expecting'] = None
        await update.message.reply_text("❌ Отменено.", reply_markup=get_reply_keyboard())
        return

    # ===== ДОБАВЛЕНИЕ: НАЗВАНИЕ =====
    if context.user_data.get('expecting') == 'name':
        context.user_data['sub_name'] = text
        context.user_data['expecting'] = 'cost'
        keyboard = [[KeyboardButton("🔙 Назад")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "💰 Введите **стоимость** (рубли):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    # ===== ДОБАВЛЕНИЕ: СТОИМОСТЬ =====
    elif context.user_data.get('expecting') == 'cost':
        try:
            cost = float(text.replace(',', '.'))
            context.user_data['sub_cost'] = cost
            context.user_data['expecting'] = 'date'
            keyboard = [[KeyboardButton("🔙 Назад")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "📅 Введите **дату** (ГГГГ-ММ-ДД):",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text("❌ Введите корректную стоимость.")

    # ===== ДОБАВЛЕНИЕ: ДАТА =====
    elif context.user_data.get('expecting') == 'date':
        try:
            date_str = text
            datetime.strptime(date_str, '%Y-%m-%d')
            name = context.user_data['sub_name']
            cost = context.user_data['sub_cost']
            sub_id = db.add_subscription(user_id, name, cost, date_str)
            context.user_data['expecting'] = None
            await update.message.reply_text(
                f"✅ **Подписка добавлена!**\n📝 {name}\n💰 {cost:.2f} ₽\n📅 {date_str}\n🆔 ID: {sub_id}",
                parse_mode='Markdown',
                reply_markup=get_reply_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используйте: ГГГГ-ММ-ДД")

    # ===== УДАЛЕНИЕ: ВВОД ID =====
    elif context.user_data.get('expecting') == 'delete_id':
        try:
            sub_id = int(text)
            sub = db.get_subscription(sub_id)
            if not sub or sub[1] != user_id:
                await update.message.reply_text("❌ Подписка не найдена или не ваша.")
                return
            if db.delete_subscription(sub_id):
                context.user_data['expecting'] = None
                await update.message.reply_text(
                    f"✅ **Подписка удалена!**\n📝 {sub[2]} ({sub[3]:.2f} ₽)",
                    parse_mode='Markdown',
                    reply_markup=get_reply_keyboard()
                )
            else:
                await update.message.reply_text("❌ Ошибка при удалении.")
        except ValueError:
            await update.message.reply_text("❌ Введите корректный ID (число).")

    # ===== ПРОДЛЕНИЕ: ВВОД ID =====
    elif context.user_data.get('expecting') == 'renew_id':
        try:
            sub_id = int(text)
            sub = db.get_subscription(sub_id)
            if not sub or sub[1] != user_id:
                await update.message.reply_text("❌ Подписка не найдена или не ваша.")
                return
            old_date = datetime.strptime(sub[4], '%Y-%m-%d')
            new_date = old_date + timedelta(days=30)
            db.update_subscription(sub_id, sub[2], sub[3], new_date.strftime('%Y-%m-%d'))
            context.user_data['expecting'] = None
            await update.message.reply_text(
                f"✅ **Продлено!**\n📝 {sub[2]}\n📅 {old_date.strftime('%d.%m.%Y')} → {new_date.strftime('%d.%m.%Y')}",
                parse_mode='Markdown',
                reply_markup=get_reply_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ Введите корректный ID (число).")

    else:
        await update.message.reply_text(
            "👋 **Главное меню**\n\nВыбери действие 👇",
            parse_mode='Markdown',
            reply_markup=get_reply_keyboard()
        )
# ============================================================
# INLINE-КНОПКИ (внутри сообщения)
# ============================================================

async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка Inline-кнопок (в сообщении)"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add":
        await query.edit_message_text("📝 Используйте кнопку внизу ➡️", reply_markup=get_reply_keyboard())
    elif data == "list":
        await list_subscriptions_inline(query, context)
    elif data == "stats":
        await stats_inline(query, context)
    elif data == "due":
        await due_inline(query, context)
    elif data == "renew":
        await renew_menu_inline(query, context)
    elif data == "delete":
        await delete_menu_inline(query, context)
    else:
        await query.edit_message_text("❌ Неизвестная команда.")


# ============================================================
# INLINE-ФУНКЦИИ (для Inline-кнопок)
# ============================================================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню (Inline)"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Добавить подписку", callback_data="add")],
        [InlineKeyboardButton("📋 Мои подписки", callback_data="list")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🔔 Скоро истекают", callback_data="due")],
        [InlineKeyboardButton("🔄 Продлить подписку", callback_data="renew")],
        [InlineKeyboardButton("🗑️ Удалить подписку", callback_data="delete")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 **Главное меню**\n\n"
        "Выбери действие 👇",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора подписки для продления (Inline)"""
    query = update.callback_query
    await query.answer()
    
    sub_id = int(query.data.split('_')[1])
    sub = db.get_subscription(sub_id)
    
    if not sub:
        await query.edit_message_text("❌ Подписка не найдена.")
        return
    
    user_id = query.from_user.id
    if sub[1] != user_id:
        await query.edit_message_text("❌ Это не ваша подписка.")
        return
    
    old_date = datetime.strptime(sub[4], '%Y-%m-%d')
    new_date = old_date + timedelta(days=30)
    db.update_subscription(sub_id, sub[2], sub[3], new_date.strftime('%Y-%m-%d'))
    
    await query.edit_message_text(
        f"✅ **Подписка продлена!**\n\n"
        f"📝 {sub[2]}\n"
        f"📅 {old_date.strftime('%d.%m.%Y')} → {new_date.strftime('%d.%m.%Y')}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В меню", callback_data="main_menu")]
        ])
    )


async def delete_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление подписки (Inline)"""
    query = update.callback_query
    await query.answer()
    
    sub_id = int(query.data.split('_')[2])
    sub = db.get_subscription(sub_id)
    
    if not sub:
        await query.edit_message_text("❌ Подписка не найдена.")
        return
    
    if db.delete_subscription(sub_id):
        await query.edit_message_text(
            f"✅ **Подписка удалена!**\n\n"
            f"📝 {sub[2]} ({sub[3]:.2f} ₽)",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Ошибка при удалении.")

async def list_subscriptions_inline(query, context):
    user_id = query.from_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await query.edit_message_text("📭 Нет подписок.")
        return
    text = "📋 **Ваши подписки:**\n\n"
    for sub_id, name, cost, renewal in subs:
        text += f"🆔 {sub_id} • **{name}** — {cost:.2f} ₽ (до {renewal})\n"
    await query.edit_message_text(text, parse_mode='Markdown')

async def stats_inline(query, context):
    user_id = query.from_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await query.edit_message_text("📭 Нет подписок.")
        return
    total = db.get_total_cost(user_id)
    text = f"📊 **Статистика**\n\n📝 Всего: {len(subs)}\n💰 В месяц: {total:.2f} ₽\n💰 В год: {total * 12:.2f} ₽"
    await query.edit_message_text(text, parse_mode='Markdown')

async def due_inline(query, context):
    user_id = query.from_user.id
    due = db.get_due_soon(user_id, 7)
    if not due:
        await query.edit_message_text("🔔 Нет подписок, истекающих в ближайшие 7 дней.")
        return
    text = "🔔 **Истекают скоро:**\n\n"
    for sub_id, name, cost, renewal in due:
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        text += f"🆔 {sub_id} • **{name}** — {days_left} дн.\n"
    await query.edit_message_text(text, parse_mode='Markdown')

async def renew_menu_inline(query, context):
    user_id = query.from_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await query.edit_message_text("📭 Нет подписок.")
        return
    keyboard = []
    for sub_id, name, cost, renewal in subs:
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        status = "🔴" if days_left < 0 else "🟢" if days_left > 30 else "🟡"
        keyboard.append([InlineKeyboardButton(f"{status} {name} ({cost:.2f} ₽)", callback_data=f"renew_{sub_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    await query.edit_message_text("🔄 **Выберите:**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_menu_inline(query, context):
    user_id = query.from_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await query.edit_message_text("📭 Нет подписок.")
        return
    keyboard = []
    for sub_id, name, cost, renewal in subs:
        keyboard.append([InlineKeyboardButton(f"🗑️ {name} ({cost:.2f} ₽)", callback_data=f"delete_sub_{sub_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    await query.edit_message_text("🗑️ **Выберите:**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


# ============================================================
# ОСНОВНЫЕ КОМАНДЫ (start, help, check)
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет!\nВыбери действие 👇", reply_markup=get_reply_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 /add — добавить\n/list — список\n/stats — статистика\n/due — скоро истекают\n/renew — продлить\n/delete — удалить", parse_mode='Markdown', reply_markup=get_reply_keyboard())

async def check_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    due = db.get_due_soon(user_id, 3)
    if not due:
        await update.message.reply_text("🔔 Нет подписок, истекающих в ближайшие 3 дня.", reply_markup=get_reply_keyboard())
        return
    text = "🔔 **Истекают через 3 дня:**\n\n"
    for sub_id, name, cost, renewal in due:
        days_left = (datetime.strptime(renewal, '%Y-%m-%d') - datetime.now()).days
        text += f"🆔 {sub_id} • **{name}** — {days_left} дн.\n"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_reply_keyboard())


# ============================================================
# 8ConversationHandler (для команды /add)
# ============================================================

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['expecting'] = 'name'
    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📝 **Добавление новой подписки**\n\n"
        "Введите **название** подписки:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sub_name'] = update.message.text
    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "💰 Введите **стоимость** подписки в рублях:\n"
        "Например: 299.00",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return COST

async def add_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['sub_cost'] = float(update.message.text.replace(',', '.'))
        
        keyboard = [[KeyboardButton("🔙 Назад")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "📅 Введите **дату продления** в формате:\n"
            "`ГГГГ-ММ-ДД`\n\n"
            "Например: 2026-12-31",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return DATE
    except ValueError:
        await update.message.reply_text("❌ Введите корректную стоимость (число).")
        return COST

async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_str = update.message.text
        datetime.strptime(date_str, '%Y-%m-%d')
        user_id = update.effective_user.id
        name = context.user_data['sub_name']
        cost = context.user_data['sub_cost']
        sub_id = db.add_subscription(user_id, name, cost, date_str)
        await update.message.reply_text(
            f"✅ **Добавлено!**\n📝 {name}\n💰 {cost:.2f} ₽\n📅 {date_str}\n🆔 ID: {sub_id}",
            parse_mode='Markdown',
            reply_markup=get_reply_keyboard()
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: ГГГГ-ММ-ДД")
        return DATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.", reply_markup=get_reply_keyboard())
    return ConversationHandler.END


# ============================================================
# MAIN
# ============================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("check", check_reminders))

    # Reply-кнопки (внизу)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_buttons))

    # Inline-кнопки (в сообщении)
    app.add_handler(CallbackQueryHandler(handle_inline_buttons, pattern="^(add|list|stats|due|renew|delete)$"))
    app.add_handler(CallbackQueryHandler(renew_menu_inline, pattern="^renew$"))
    app.add_handler(CallbackQueryHandler(handle_renew, pattern="^renew_"))
    app.add_handler(CallbackQueryHandler(delete_menu_inline, pattern="^delete_menu$"))
    app.add_handler(CallbackQueryHandler(delete_subscription, pattern="^delete_sub_"))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(list_subscriptions_inline, pattern="^list_page_"))

    # ConversationHandler
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cost)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)

    print("🤖 Бот запущен!")
    app.run_polling()


if __name__ == '__main__':
    main()