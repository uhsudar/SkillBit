import logging
import os
import random
import asyncio
import signal
import sys
from typing import Any, Coroutine, List, Dict, Optional, Set
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Исправление для Windows - настройка политики цикла событий
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.chdir(os.path.dirname(os.path.abspath(__file__)))

API_KEY = ''

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.info('Starting Bot...')

games: Dict[int, Dict] = {}

# Описания игр
game_descriptions = {
    "Викторина": (
        "🎓 **Викторина**\n\n"
        "Интеллектуальная битва на общие знания. Отвечайте на вопросы быстрее других!\n\n"
        "**Правила:**\n"
        "- Вопросы с вариантами ответов (A/B/C/D)\n"
        "- **20 секунд** на обдумывание\n"
        "- **+2 очка** за правильный ответ\n"
        "- Итоговый рейтинг после 5 раундов"
    ),
    "Крокодил": (
        "🐊 **Крокодил**\n\n"
        "Объясняйте слова без прямых подсказок, а другие игроки должны угадать!\n\n"
        "**Правила:**\n"
        "- **Крокодил** выбирает слово из 3 вариантов\n"
        "- **15 секунд** на объяснение (жесты, ассоциации)\n"
        "- **60 секунд** на угадывание\n"
        "- Нельзя использовать однокоренные слова"
    ),
    "Города и страны": (
        "🏙️ **Города и страны**\n\n"
        "Назовите город или страну на последнюю букву предыдущего слова\n\n"
        "**Правила:**\n"
        "- Режимы: **города** или **страны**\n"
        "- На **20 секунд** дается на ответ\n"
        "- Буквы **Ь, Ы, Ъ, Й** пропускаются (берется предыдущая)\n"
        "- Буква **Я** обрабатывается специально: слова на 'Я' имеют приоритет\n"
        "- Когда слова на текущую букву заканчиваются, ищется следующая подходящая буква\n"
        "- Повторять слова нельзя\n"
        "- Проигрывает тот, кто не успел или ошибся"
    )
}

# Данные для викторины
QUIZ_QUESTIONS = [
    {"question": "Осман", "options": ["Алексус", "Наксус", "Поксус", "НЕГРУС"], "answer": "НЕГРУС"},
    {"question": "Какой элемент имеет символ 'O'?", "options": ["Золото", "Кислород", "Углерод", "Азот"],
     "answer": "Кислород"},
    {"question": "Сколько планет в Солнечной системе?", "options": ["7", "8", "9", "10"], "answer": "8"},
    {"question": "Какая планета ближе всего к Солнцу?", "options": ["Венера", "Марс", "Меркурий", "Земля"],
     "answer": "Меркурий"},
    {"question": "Сколько цветов в радуге?", "options": ["5", "6", "7", "8"], "answer": "7"},
]
ROUND_COUNT = 5
ANSWER_TIME = 20  # секунд на ответ

# Данные для крокодила
CROC_WORDS = ["слон", "велосипед", "кошка", "самолет", "дерево", "компьютер"]

# Данные для игры "Города/Страны"
BAD_ENDING_LETTERS = {'ь', 'ы', 'ъ', 'й'}
COUNTRIES = [
    "Россия", "Германия", "Франция", "Испания", "Италия", "Португалия", "Бельгия", "Нидерланды",
    "Польша", "Чехия", "Австрия", "Швейцария", "Норвегия", "Швеция", "Финляндия", "Дания",
    "Канада", "США", "Мексика", "Бразилия", "Аргентина", "Колумбия", "Чили", "Перу",
    "Китай", "Япония", "Южная Корея", "Индия", "Пакистан", "Индонезия", "Филиппины", "Таиланд",
    "Австралия", "Новая Зеландия", "Египет", "Марокко", "Алжир", "ЮАР", "Нигерия", "Кения",
    "Ямайка", "Япония"
]
CITIES = [
    "Анкара", "Амстердам", "Антверпен", "Абу-Даби", "Афины", "Берлин", "Будапешт", "Барселона",
    "Бухарест", "Бейрут", "Багдад", "Баку", "Бангкок", "Белград", "Брисбен", "Варшава", "Вена",
    "Вильнюс", "Ванкувер", "Валлетта", "Вашингтон", "Гамбург", "Глазго", "Гонолулу", "Гавана",
    "Дели", "Дамаск", "Джакарта", "Дублин", "Доха", "Ереван", "Екатеринбург", "Женева", "Загреб",
    "Исламабад", "Иерусалим", "Киев", "Каракас", "Каир", "Карачи", "Кейптаун", "Копенгаген",
    "Куала-Лумпур", "Кито", "Лондон", "Лос-Анджелес", "Лима", "Лагос", "Москва", "Мадрид", "Мехико",
    "Мельбурн", "Минск", "Манила", "Мумбаи", "Нью-Йорк", "Найроби", "Осло", "Оттава", "Париж",
    "Пекин", "Прага", "Рим", "Рио-де-Жанейро", "Рига", "Сеул", "Санкт-Петербург", "Сан-Франциско",
    "Сингапур", "София", "Стамбул", "Стокгольм", "Токио", "Торонто", "Тегеран", "Таллин", "Улан-Батор",
    "Флоренция", "Филадельфия", "Хельсинки", "Хартум", "Хьюстон", "Цюрих", "Чикаго", "Шанхай",
    "Шэньчжэнь", "Эдмонтон", "Южно-Сахалинск", "Ярославль", "Ялта", "Якутск"
]
CITIES_ANSWER_TIMEOUT = 20
JOIN_TIMEOUT = 20


def get_effective_letters(word: str) -> List[str]:
    letters = []
    for ch in reversed(word.lower()):
        if ch not in BAD_ENDING_LETTERS:
            letters.append(ch)
    return letters


def find_available_letter(used_words: List[str], word_pool: List[str], last_word: str) -> str:
    if not last_word:
        return random.choice(word_pool)[0].lower()

    effective_letters = get_effective_letters(last_word)

    if not effective_letters:
        return last_word[-1].lower()

    if 'я' in effective_letters:
        for word in word_pool:
            if word.lower().startswith('я') and word not in used_words:
                return 'я'

    for letter in effective_letters:
        for word in word_pool:
            if word.lower().startswith(letter) and word not in used_words:
                return letter

    for letter in last_word.lower()[::-1]:
        if letter in BAD_ENDING_LETTERS:
            continue
        for word in word_pool:
            if word.lower().startswith(letter) and word not in used_words:
                return letter

    return effective_letters[0] if effective_letters else last_word[-1].lower()


def find_next_word(required_letter: str, used_words: List[str], word_pool: List[str]) -> Optional[str]:
    for word in word_pool:
        if word.lower().startswith(required_letter) and word not in used_words:
            return word
    return None


async def mention_user(user_id: int, user_name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{user_name}</a>'


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            'Привет, я СкиллБит! Бот, который имеет коллекцию из логических и настольных игр.'
        )
        bot_username = context.bot.username
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить в группу", url=f"https://t.me/{bot_username}?startgroup=true")],
            [InlineKeyboardButton("Мини-игры", callback_data="games_list")]
        ])
        await update.message.reply_text(
            "Я предназначен для работы в групповых чатах. Добавьте меня в свою беседу!",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text('Привет! Используйте команды, чтобы начать игру.')


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_username = context.bot.username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить в группу", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("Мини-игры", callback_data="games_list")]
    ])
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=keyboard
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.effective_chat.type == 'private':
        if chat_id in games:
            game = games[chat_id]
            if game['type'] == 'cities' and 'join_message_id' in game:
                try:
                    await context.bot.delete_message(chat_id, game['join_message_id'])
                except BadRequest:
                    pass
            games.pop(chat_id, None)
            await update.message.reply_text('Игра остановлена.')
        else:
            await update.message.reply_text('Нет активной игры для остановки.')
        return

    try:
        admins = [a.user.id for a in await context.bot.get_chat_administrators(chat_id)]
    except BadRequest:
        admins = []

    if user_id not in admins:
        return await update.message.reply_text('Только админ может сбросить игры.')

    if chat_id in games:
        game = games[chat_id]
        if game['type'] == 'cities' and 'join_message_id' in game:
            try:
                await context.bot.delete_message(chat_id, game['join_message_id'])
            except BadRequest:
                pass
        games.pop(chat_id, None)
        await update.message.reply_text('Игра остановлена.')
    else:
        await update.message.reply_text('Нет активной игры для остановки.')


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Викторина доступна только в группах.")
        return

    if chat.id in games:
        await update.message.reply_text("В этом чате уже идет другая игра. Сначала завершите её (/stop).")
        return

    questions = random.sample(QUIZ_QUESTIONS, min(ROUND_COUNT, len(QUIZ_QUESTIONS)))

    games[chat.id] = {
        'type': 'quiz',
        'chat_id': chat.id,
        'questions': questions,
        'current_round': 0,
        'scores': {},
        'answers': {},
    }
    await send_next_question(chat.id, context)


async def send_next_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = games.get(chat_id)
    if not game or game['type'] != 'quiz':
        return

    if game['current_round'] >= len(game['questions']):
        await show_final_scores(chat_id, context)
        games.pop(chat_id, None)
        return

    question_info = game['questions'][game['current_round']]
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(opt, callback_data=f'quiz_answer:{chat_id}:{opt}')] for opt in question_info['options']])

    game['answers'] = {}
    message_text = (f"Вопрос {game['current_round'] + 1} из {len(game['questions'])}:\n\n"
                    f"{question_info['question']}\n\nУ вас есть {ANSWER_TIME} секунд на ответ!")

    await context.bot.send_message(chat_id, message_text, reply_markup=keyboard)
    asyncio.create_task(wait_answer_time(chat_id, context))


async def wait_answer_time(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(ANSWER_TIME)
    game = games.get(chat_id)
    if not game or game['type'] != 'quiz':
        return

    question_info = game['questions'][game['current_round']]
    correct_answer = question_info['answer']

    results = [f"Время истекло! Результаты вопроса:\n"]
    for user_id, answer in game['answers'].items():
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            user_name = await mention_user(user_id, user.user.full_name)
        except BadRequest:
            user_name = "Игрок"
        if answer == correct_answer:
            game['scores'][user_id] = game['scores'].get(user_id, 0) + 2
            results.append(f"✅ {user_name} выбрал «{answer}» — правильно! +2 очка")
        else:
            results.append(f"❌ {user_name} выбрал «{answer}» — неверно. +0 очков")

    if not game['answers']:
        results.append("Никто не ответил на этот вопрос.")

    await context.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML", reply_markup=ReplyKeyboardRemove())

    game['current_round'] += 1
    await asyncio.sleep(3)
    await send_next_question(chat_id, context)


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('quiz_answer:'):
        return
    parts = data.split(':', 2)
    if len(parts) < 3:
        return
    _, chat_id_str, answer = parts
    try:
        chat_id = int(chat_id_str)
    except ValueError:
        return

    game = games.get(chat_id)
    if not game or game['type'] != 'quiz':
        await query.answer("Нет активной викторины в этом чате.", show_alert=True)
        return
    if game['current_round'] >= len(game['questions']):
        await query.answer("Викторина уже завершена.", show_alert=True)
        return

    user_id = query.from_user.id
    game['answers'][user_id] = answer
    await query.answer(f"Ваш ответ «{answer}» принят.", show_alert=False)


async def show_final_scores(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = games.get(chat_id)
    if not game or game['type'] != 'quiz':
        return
    if not game['scores']:
        await context.bot.send_message(chat_id, "Игра завершена. Никто не набрал очков.")
        return

    sorted_scores = sorted(game['scores'].items(), key=lambda x: x[1], reverse=True)
    result_lines = ["🏆 Итоги викторины:\n"]
    places = ['🥇', '🥈', '🥉']
    for i, (user_id, score) in enumerate(sorted_scores):
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            user_name = await mention_user(user_id, user.user.full_name)
        except BadRequest:
            user_name = "Игрок"
        place_icon = places[i] if i < 3 else f"{i + 1}."
        result_lines.append(f"{place_icon} {user_name}: {score} очков")

    await context.bot.send_message(chat_id, "\n".join(result_lines), parse_mode="HTML",
                                   reply_markup=ReplyKeyboardRemove())


async def crocodile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Эта команда доступна только в группах.")
        return

    if chat.id in games:
        await update.message.reply_text("В этом чате уже идет другая игра. Сначала завершите её (/stop).")
        return

    chat_admins = await context.bot.get_chat_administrators(chat.id)
    bot_id = context.bot.id
    candidates = [a.user for a in chat_admins if a.user.id != bot_id]

    if not candidates:
        await update.message.reply_text("Не удалось найти подходящего игрока для роли Крокодила.")
        return

    crocodile_player = random.choice(candidates)
    words_for_choice = random.sample(CROC_WORDS, 3)

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(w, callback_data=f'croc_word:{w}')] for w in words_for_choice])

    try:
        await context.bot.send_message(
            crocodile_player.id,
            "Вы — Крокодил! Выберите слово для объяснения из списка ниже:",
            reply_markup=keyboard
        )
    except BadRequest:
        await update.message.reply_text(
            "Не удалось отправить сообщение выбранному игроку в личку. Пусть он начнет диалог с ботом.")
        return

    games[chat.id] = {
        'type': 'crocodile',
        'chat_id': chat.id,
        'crocodile_id': crocodile_player.id,
        'word': None,
        'stage': 'waiting_word',
    }

    try:
        user_name = await mention_user(crocodile_player.id, crocodile_player.full_name)
        await update.message.reply_text(f"Крокодил выбран: {user_name}. Ждем, пока он выберет слово.",
                                        parse_mode="HTML")
    except BadRequest:
        await update.message.reply_text(f"Крокодил выбран: {crocodile_player.full_name}. Ждем, пока он выберет слово.")


async def handle_crocodile_word_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith('croc_word:'):
        return
    parts = data.split(':', 1)
    if len(parts) < 2:
        return
    chosen_word = parts[1]
    user_id = query.from_user.id

    for game in list(games.values()):
        if game['type'] == 'crocodile' and game['crocodile_id'] == user_id and game['stage'] == 'waiting_word':
            game['word'] = chosen_word
            game['stage'] = 'explaining'

            await query.edit_message_text(f"Вы выбрали слово: {chosen_word}. Теперь объясняйте его в группе!")
            await context.bot.send_message(game['chat_id'], "Крокодил начал объяснение. У него есть 15 секунд!")

            async def explanation_time_up():
                await asyncio.sleep(15)
                current_game = games.get(game['chat_id'])
                if current_game and current_game['stage'] == 'explaining':
                    await context.bot.send_message(game['chat_id'],
                                                   "Время вышло! Попробуйте угадать слово, у вас есть 60 секунд.")
                    current_game['stage'] = 'guessing'
                    asyncio.create_task(guessing_time_up(game['chat_id'], context))

            async def guessing_time_up(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
                await asyncio.sleep(60)
                current_game = games.get(chat_id)
                if current_game and current_game['stage'] == 'guessing':
                    await ctx.bot.send_message(chat_id,
                                               f"Время на угадывание вышло! Слово было: {current_game['word']}\nИгра завершена.")
                    games.pop(chat_id, None)

            asyncio.create_task(explanation_time_up())
            return

    await query.edit_message_text("Ошибка: игра не найдена или слово уже выбрано.")


async def handle_crocodile_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    game = games.get(chat_id)
    if not game or game['type'] != 'crocodile':
        return

    if game['stage'] in ['explaining', 'guessing']:
        if user_id == game['crocodile_id'] and text.lower() == (game['word'] or '').lower():
            await update.message.reply_text(
                "❌ Крокодил подсказал слово! Игра завершена. Нарушение правила.\n"
                "Для новой игры напишите /crocodile"
            )
            games.pop(chat_id, None)
            return
        elif text.lower() == (game['word'] or '').lower():
            try:
                user_name = await mention_user(user_id, update.effective_user.full_name)
                await update.message.reply_text(
                    f"✅ {user_name} угадал слово! Игра завершена.\n"
                    "Для новой игры напишите /crocodile",
                    parse_mode="HTML"
                )
            except BadRequest:
                await update.message.reply_text(
                    f"✅ {update.effective_user.full_name} угадал слово! Игра завершена.\n"
                    "Для новой игры напишите /crocodile"
                )
            games.pop(chat_id, None)
            return


async def cities_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Эта команда доступна только в группах.")
        return

    if chat.id in games:
        await update.message.reply_text("В этом чате уже идет другая игра. Сначала завершите её (/stop).")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Города", callback_data="cities_mode:cities")],
        [InlineKeyboardButton("Страны", callback_data="cities_mode:countries")],
    ])
    await update.message.reply_text("Выберите режим игры:", reply_markup=keyboard)


async def handle_cities_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("cities_mode:"):
        return

    mode = data.split(":")[1]
    chat_id = query.message.chat.id
    word_pool = CITIES if mode == "cities" else COUNTRIES
    first_word = random.choice(word_pool)

    try:
        await query.message.delete()
    except BadRequest:
        pass

    join_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Присоединиться", callback_data="join_cities")]
    ])

    try:
        user_name = await mention_user(query.from_user.id, query.from_user.full_name)
    except BadRequest:
        user_name = query.from_user.full_name

    join_message = await context.bot.send_message(
        chat_id,
        f"🎮 Режим: {'Города' if mode == 'cities' else 'Страны'}\n"
        f"⏳ На присоединение дается {JOIN_TIMEOUT} секунд\n\n"
        f"Игроки:\n1. {user_name}",
        parse_mode="HTML",
        reply_markup=join_keyboard
    )

    games[chat_id] = {
        "type": "cities",
        "mode": mode,
        "players": [query.from_user.id],
        "used_words": [first_word],
        "current_player": 0,
        "word_pool": word_pool,
        "join_message_id": join_message.message_id,
        "timer": None,
        "game_started": False,
        "active_timer": None
    }

    games[chat_id]['timer'] = asyncio.create_task(cities_join_timer(chat_id, context))


async def cities_join_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(JOIN_TIMEOUT)
    game = games.get(chat_id)
    if not game or game["type"] != "cities" or game["game_started"]:
        return

    game["game_started"] = True

    try:
        await context.bot.delete_message(chat_id, game["join_message_id"])
    except BadRequest:
        pass

    await start_cities_game(chat_id, context)


async def start_cities_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = games.get(chat_id)
    if not game:
        return

    first_word = game["used_words"][0]
    last_letter = find_available_letter(
        game["used_words"],
        game["word_pool"],
        first_word
    )

    current_player_id = game["players"][game["current_player"]]

    try:
        player = await context.bot.get_chat_member(chat_id, current_player_id)
        player_name = await mention_user(current_player_id, player.user.full_name)
    except BadRequest:
        player_name = "Игрок"

    await context.bot.send_message(
        chat_id,
        f"🎮 Игра начинается!\n"
        f"Первое слово: *{first_word}*\n"
        f"Следующее слово на букву *{last_letter.upper()}*\n\n"
        f"Первый ход: {player_name}\n"
        f"⏳ У вас есть {CITIES_ANSWER_TIMEOUT} секунд!",
        parse_mode="HTML"
    )

    game["active_timer"] = asyncio.create_task(cities_turn_timer(chat_id, context))


async def cities_turn_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(CITIES_ANSWER_TIMEOUT)
    game = games.get(chat_id)
    if not game or game["type"] != "cities" or not game["game_started"]:
        return

    current_player_id = game["players"][game["current_player"]]
    try:
        player = await context.bot.get_chat_member(chat_id, current_player_id)
        player_name = await mention_user(current_player_id, player.user.full_name)
    except BadRequest:
        player_name = "Игрок"

    last_word = game["used_words"][-1]
    next_letter = find_available_letter(
        game["used_words"],
        game["word_pool"],
        last_word
    )

    next_word = find_next_word(
        next_letter,
        game["used_words"],
        game["word_pool"]
    )

    if not next_word:
        await context.bot.send_message(
            chat_id,
            f"🏁 Игра окончена! Больше нет подходящих слов.\n"
            f"Всего названо: {len(game['used_words'])} слов.",
            parse_mode="HTML"
        )
        games.pop(chat_id, None)
        return

    game["current_player"] = (game["current_player"] + 1) % len(game["players"])
    next_player_id = game["players"][game["current_player"]]

    try:
        next_player = await context.bot.get_chat_member(chat_id, next_player_id)
        next_player_name = await mention_user(next_player_id, next_player.user.full_name)
    except BadRequest:
        next_player_name = "Игрок"

    await context.bot.send_message(
        chat_id,
        f"⏰ Время вышло! {player_name} не успел.\n"
        f"Следующий игрок: {next_player_name}. Буква: *{next_letter.upper()}*\n"
        f"⏳ У вас есть {CITIES_ANSWER_TIMEOUT} секунд!",
        parse_mode="HTML"
    )

    game["active_timer"] = asyncio.create_task(cities_turn_timer(chat_id, context))


async def handle_join_cities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user_id = query.from_user.id
    game = games.get(chat_id)

    if not game or game["type"] != "cities" or game["game_started"]:
        await query.answer("Игра не найдена или уже началась.", show_alert=True)
        return

    if user_id in game["players"]:
        await query.answer("Вы уже в игре!", show_alert=True)
        return

    game["players"].append(user_id)

    players_list = []
    for i, player_id in enumerate(game["players"]):
        try:
            player = await context.bot.get_chat_member(chat_id, player_id)
            players_list.append(f"{i + 1}. {await mention_user(player_id, player.user.full_name)}")
        except BadRequest:
            players_list.append(f"{i + 1}. Игрок")

    try:
        await query.edit_message_text(
            f"🎮 Режим: {'Города' if game['mode'] == 'cities' else 'Страны'}\n"
            f"⏳ На присоединение дается {JOIN_TIMEOUT} секунд\n\n"
            f"Игроки:\n" + "\n".join(players_list),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Присоединиться", callback_data="join_cities")]
            ])
        )
    except BadRequest:
        pass

    await query.answer(f"{query.from_user.full_name} присоединился к игре!")


async def handle_cities_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    game = games.get(chat_id)

    if not game or game["type"] != "cities" or not game["game_started"]:
        return

    if user_id != game["players"][game["current_player"]]:
        return

    word = update.message.text.strip().capitalize()
    last_word = game["used_words"][-1]

    required_letter = find_available_letter(
        game["used_words"],
        game["word_pool"],
        last_word
    )

    if word[0].lower() != required_letter:
        await update.message.reply_text(f"❌ Неверно! Слово должно начинаться на букву '{required_letter.upper()}'.")
        return

    if word not in game["word_pool"]:
        await update.message.reply_text("❌ Этого слова нет в списке!")
        return

    if word in game["used_words"]:
        await update.message.reply_text("❌ Это слово уже называли!")
        return

    if game.get("active_timer"):
        game["active_timer"].cancel()

    game["used_words"].append(word)

    next_letter = find_available_letter(
        game["used_words"],
        game["word_pool"],
        word
    )

    next_word = find_next_word(
        next_letter,
        game["used_words"],
        game["word_pool"]
    )

    if not next_word:
        await update.message.reply_text(
            f"🏁 Игра окончена! Больше нет подходящих слов.\n"
            f"Всего названо: {len(game['used_words'])} слов.",
            parse_mode="HTML"
        )
        games.pop(chat_id, None)
        return

    game["current_player"] = (game["current_player"] + 1) % len(game["players"])
    next_player_id = game["players"][game["current_player"]]

    try:
        next_player = await context.bot.get_chat_member(chat_id, next_player_id)
        next_player_name = await mention_user(next_player_id, next_player.user.full_name)
    except BadRequest:
        next_player_name = "Игрок"

    await update.message.reply_text(
        f"✅ Принято: {word}\n"
        f"Следующее слово на букву *{next_letter.upper()}*\n"
        f"Ход игрока: {next_player_name}\n"
        f"⏳ У вас есть {CITIES_ANSWER_TIMEOUT} секунд!",
        parse_mode="HTML"
    )

    game["active_timer"] = asyncio.create_task(cities_turn_timer(chat_id, context))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bot_username = context.bot.username

    if query.data == 'games_list':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Викторина", callback_data="game_info:Викторина")],
            [InlineKeyboardButton("Крокодил", callback_data="game_info:Крокодил")],
            [InlineKeyboardButton("Города и страны", callback_data="game_info:Города и страны")],
            [InlineKeyboardButton("◀ Назад", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            "Доступные мини-игры:",
            reply_markup=keyboard
        )
        return

    if query.data == 'main_menu':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить в группу", url=f"https://t.me/{bot_username}?startgroup=true")],
            [InlineKeyboardButton("Мини-игры", callback_data="games_list")]
        ])
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=keyboard
        )
        return

    if query.data.startswith('game_info:'):
        game_name = query.data.split(':', 1)[1]
        description = game_descriptions.get(game_name, "Описание игры не найдено.")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀ Назад", callback_data="games_list")]
        ])
        await query.edit_message_text(
            description,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    if query.data.startswith('croc_word:'):
        await handle_crocodile_word_choice(update, context)
        return

    if query.data.startswith('quiz_answer:'):
        await handle_quiz_answer(update, context)
        return

    if query.data.startswith('cities_mode:'):
        await handle_cities_mode(update, context)
        return

    if query.data == 'join_cities':
        await handle_join_cities(update, context)
        return


async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == 'Назад':
        await update.message.reply_text('Отмена. Возвращаемся в начало.', reply_markup=ReplyKeyboardRemove())
        kb = ReplyKeyboardMarkup([['Мини-игры']], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text('Выберите действие:', reply_markup=kb)
        return

    if text == 'Мини-игры':
        kb = ReplyKeyboardMarkup(
            [
                ['Викторина', 'Крокодил'],
                ['Города и страны', 'Назад'],
            ], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text('**Выберите мини-игру:**', parse_mode="Markdown", reply_markup=kb)
        return

    if text in game_descriptions:
        description = game_descriptions[text]
        keyboard = InlineKeyboardMarkup([])
        await update.message.reply_text(
            description,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    game = games.get(chat_id)
    if not game:
        return

    if game["type"] == "cities":
        await handle_cities_answer(update, context)
    elif game["type"] == "crocodile":
        await handle_crocodile_guess(update, context)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f'Ошибка: {context.error}', exc_info=True)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(f'Произошла ошибка: {context.error}')
        except BadRequest:
            pass


def signal_handler(_signum: Any, _frame: Any) -> None:
    logging.info("Получен сигнал завершения. Остановка бота...")
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app = ApplicationBuilder().token(API_KEY).build()

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('stop', stop_command))
    app.add_handler(CommandHandler('quiz', quiz_command))
    app.add_handler(CommandHandler('crocodile', crocodile_command))
    app.add_handler(CommandHandler('cities', cities_command))
    app.add_handler(CommandHandler('menu', menu_command))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))

    logging.info('Bot started polling...')
    app.run_polling()


if __name__ == '__main__':
    main()
