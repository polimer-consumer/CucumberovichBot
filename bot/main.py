import asyncio
import logging
import os
import random
import re
import sqlite3

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineQuery, InputTextMessageContent, InlineQueryResultArticle

logging.basicConfig(level=logging.DEBUG)

con_user = sqlite3.connect('/home/worker/cucum/users.db')
con_cuc = sqlite3.connect('/home/worker/cucum/cucumbers.db')
cur_user = con_user.cursor()
cur_cuc = con_cuc.cursor()

cucumbers = ['basic', 'salad', 'gherkin', 'holland', 'asian', 'gachi', 'chernobyl', 'gopnik', 'tomato']


async def main(**kwargs):
    bot = Bot(os.environ.get('API_TOKEN'))
    dp = Dispatcher(bot=bot)
    await register_handlers(dp)
    update = types.Update.to_object(kwargs)
    Bot.set_current(dp.bot)
    await dp.process_update(update)
    return 'ok'


async def register_handlers(dp: Dispatcher):
    dp.register_inline_handler(handle_command)
    dp.register_message_handler(wipe_for_debug, commands='wipe')


async def add_user(user):
    cur_user.execute('''INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)''', (user.id, user.username, None, 0, 0, 0, 0))
    con_user.commit()


async def gop(user_id):
    rating = cur_user.execute('''SELECT rating FROM users WHERE user_id = ?''', (user_id,)).fetchone()[0]
    gop_points = 0
    gop_text = ''
    gop_bonus = cur_user.execute('''SELECT squat FROM users WHERE user_id = ?''', (user_id,)).fetchone()[0]

    if gop_bonus == 1:
        top = cur_user.execute('''SELECT user_id, tag, rating FROM users ORDER BY rating DESC''').fetchone()
        if top[0] != user_id:
            gop_points = round(top[2] * 0.1)
            cur_user.execute('''UPDATE users SET rating = ? WHERE user_id = ?''', (top[2] - gop_points, top[0],))
            con_user.commit()
            gop_text = '\n\n<b>{tag}</b> зашел не на ту грядку и поплатился за это!' \
                       'Ты отжимаешь у <b>{tag}</b> <b>{pt}</b> кукумберов!'.format(tag=top[1], pt=gop_points)

    cur_user.execute('''UPDATE users SET rating = ?, squat = 0 WHERE user_id = ?''', (rating + gop_points, user_id,))
    con_user.commit()
    con_cuc.commit()

    return gop_text


async def set_cucumber(user_id):
    weights = [300, 10, 15, 20, 20, 4, 6, 10, 15]
    cucumber = random.choices(cucumbers, weights=weights, k=1)[0]
    if cucumber == 'basic':
        cucumber += str(random.randint(1, 20))

    rating = cur_user.execute('''SELECT rating FROM users WHERE user_id = ?''', (user_id,)).fetchone()[0]
    cur_user.execute('''UPDATE users SET cucumber = ? WHERE user_id = ?''', (cucumber, user_id))
    con_user.commit()

    cur_cuc.execute('''SELECT points, brine, squat, mutation FROM cucumbers WHERE cucumber = ?''', (cucumber,))
    update = cur_cuc.fetchone()

    factor = 1
    bonus_text = ''
    bonus = cur_user.execute('''SELECT brine, squat, mutation FROM users WHERE user_id = ?''', (user_id,)).fetchone()
    if bonus[0] == 1:
        factor = 2
        bonus_text = '\n\nДа ты ещё и малосольный! <b>+{}</b> кукумберов!'.format(update[0] * factor)
    elif bonus[2] == 1:
        factor = round(random.uniform(-2.0, 4.0))
        bonus_text = '\n\nТы мутировал! И {} <b>{}</b> кукумберов!' \
            .format(('получаешь', 'теряешь')[update[0] * factor < 0], abs(update[0] * factor))

    rating += update[0] * factor
    brine = update[1]
    squat = update[2]
    mutation = update[3]
    cur_user.execute('''UPDATE users SET rating = ?, brine = ?, squat = ?, mutation = ? WHERE user_id = ?''',
                     (rating, brine, squat, mutation, user_id,))
    con_user.commit()
    con_cuc.commit()

    return bonus_text


async def get_top():
    cur_user.execute('''SELECT tag, rating FROM users ORDER BY rating DESC''')
    pairs = cur_user.fetchmany(10)
    table = ''
    for i in range(0, len(pairs)):
        table += '<b>{tag}: {rate}</b> 🥒🥒🥒\n'.format(tag=pairs[i][0], rate=pairs[i][1])
    con_user.commit()
    con_cuc.commit()
    return table


async def wipe_for_debug(message: types.Message):
    user = message.from_user
    cur_user.execute('''SELECT cucumber FROM users WHERE user_id = (?) AND cucumber IS NOT NULL''', (user.id,))
    if cur_user.fetchone() is None:
        status = 'У тебя и так не было огурчика('
    else:
        cur_user.execute('''UPDATE users SET cucumber = NULL WHERE user_id = (?)''', (user.id,))
        con_user.commit()
        status = '<b>{},</b> ты успешно съеден!'.format(user.first_name)

    con_user.commit()
    con_cuc.commit()

    await message.answer(status, parse_mode='html')


async def handle_command(inline_query: InlineQuery):
    text = inline_query.query
    user = inline_query.from_user
    bonus_text = ''
    cur_user.execute('''SELECT * FROM users WHERE user_id = (?)''', (user.id,))
    if re.fullmatch(r'@\w*', text):
        await gop(user_id)
    if cur_user.fetchone() is None:
        await add_user(user)
    cur_user.execute('''SELECT cucumber FROM users WHERE user_id = (?) AND cucumber IS NOT NULL''', (user.id,))
    if cur_user.fetchone() is None:
        bonus_text = await set_cucumber(user.id) + await gop(user.id)
    cucumber = cur_user.execute('''SELECT cucumber FROM users WHERE user_id = (?)''', (user.id,)).fetchone()[0]
    about = cur_cuc.execute('''SELECT description FROM cucumbers WHERE cucumber = (?)''', (cucumber,)).fetchone()[0]
    con_user.commit()
    con_cuc.commit()
    button_cuc = types.InlineKeyboardButton(text='Узнать свой огурчик', switch_inline_query_current_chat='огурчик')
    button_top = types.InlineKeyboardButton(text='Топ-10 кукумберов', switch_inline_query_current_chat='топ')
    keyboard = types.InlineKeyboardMarkup().add(button_cuc, button_top)
    top = await get_top()

    results = [
        InlineQueryResultArticle(
            id='239',
            title='Какой я сегодня огурчик?',
            description='Раскрой свою огуречность\n🥒🥒🥒',
            thumb_url='https://i.ibb.co/026Q1nd/image.jpg',
            thumb_width=200,
            thumb_height=200,
            input_message_content=InputTextMessageContent(
                message_text=about + bonus_text,
                parse_mode='html'
            ),
            reply_markup=keyboard
        ),
        InlineQueryResultArticle(
            id='566',
            title='Топ 10 огурчиков на грядке',
            description='Самые сочные кукумберы\n🥒🥒🥒',
            thumb_url='https://i.ibb.co/kKzpZX0/cucumber1.jpg',
            thumb_width=200,
            thumb_height=200,
            input_message_content=InputTextMessageContent(
                message_text=top,
                parse_mode='html'
            )
        ),
        InlineQueryResultArticle(
            id='366',
            title='Отжать огурчки у ' + text,
            descrition='Гоп-стоп ха-ха',
            thumb_height=200,
            thumb_width=200,
            input_message_content=InputTextMessageContent(
                message_text=bonus_text,
                parse_mode='html'
            )
        )
    ]

    if text == 'огурчик':
        await inline_query.answer(results=[results[0]], cache_time=1, is_personal=True)
    elif text == 'топ':
        await inline_query.answer(results=[results[1]], cache_time=1, is_personal=True)
    elif re.fullmatch(r'@\w*', text):
        await inline_query.answer(results=[results[2]], cache_time=1, is_personal=True)
    else:
        await inline_query.answer(results=results[0:2], cache_time=1, is_personal=True)


async def wipe_cucumbers():
    cur_user.execute('''UPDATE users SET cucumber = NULL''')
    con_user.commit()
