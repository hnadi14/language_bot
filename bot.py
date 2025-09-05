import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sys
import os
from urllib.parse import quote
from gtts import gTTS
import io
import random
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database_manager import DatabaseManager

# !!! توکن ربات شما !!!
TOKEN = "8374214672:AAHEJ-haQEqqlQNE4MpozGNR7Tl-ct1GRhs"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db_manager = DatabaseManager()


# --- توابع کمکی ---
def create_progress_bar(progress_percent):
    filled_blocks = int(progress_percent / 10)
    empty_blocks = 10 - filled_blocks
    return f"[{'█' * filled_blocks}{'░' * empty_blocks}] {progress_percent:.0f}%"


# ✅ تابع اصلاح‌شده برای رفع مشکل
def get_key_from_item(item, subject):
    """بر اساس موضوع، کلمه کلیدی صحیح را برای سوال برمی‌گرداند."""
    if subject == 'english':
        return item.get('english')
    elif subject == 'arabic':
        return item.get('arabic')
    elif subject == 'persian_spelling':
        return item.get('word')
    # بازگشت یک مقدار پیش‌فرض در صورت بروز خطا
    return "آیتم یافت نشد"


def get_answer_from_item(item, subject):
    """پاسخ صحیح را برای آیتم برمی‌گرداند (معنی فارسی)."""
    return item.get('farsi') or item.get('meaning')


# --- توابع اصلی ربات (شروع و منوها) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("سلام! به ربات هوشمند یادگیری خوش آمدید.")
    keyboard = [
        [InlineKeyboardButton("آموزش زبان عربی 🇮🇶", callback_data="select_subject:arabic")],
        [InlineKeyboardButton("آموزش زبان انگلیسی 🇬🇧", callback_data="select_subject:english")],
        [InlineKeyboardButton("املای دشوار فارسی 🇮🇷", callback_data="select_subject:persian_spelling")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفا موضوع درسی مورد نظر خود را انتخاب کنید:", reply_markup=reply_markup)


async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subject = query.data.split(':')[1]
    context.user_data['current_subject'] = subject
    subject_names = {"arabic": "زبان عربی", "english": "زبان انگلیسی", "persian_spelling": "املای فارسی"}
    keyboard = [
        [
            InlineKeyboardButton("پایه هفتم", callback_data=f"select_grade:{subject}:7th_grade"),
            InlineKeyboardButton("پایه هشتم", callback_data=f"select_grade:{subject}:8th_grade"),
            InlineKeyboardButton("پایه نهم", callback_data=f"select_grade:{subject}:9th_grade"),
        ],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"شما **{subject_names.get(subject)}** را انتخاب کردید. لطفاً پایه را انتخاب کنید:",
                                  reply_markup=reply_markup, parse_mode='Markdown')


async def select_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, subject, grade = query.data.split(':')
    context.user_data['current_grade'] = grade
    lessons_keyboard = [InlineKeyboardButton(f"درس {i}", callback_data=f"select_lesson:{subject}:{grade}:lesson_{i}")
                        for i in range(1, 13)]
    keyboard = [lessons_keyboard[i:i + 3] for i in range(0, len(lessons_keyboard), 3)]
    keyboard.append([InlineKeyboardButton("بازگشت به انتخاب پایه", callback_data=f"select_subject:{subject}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً درس مورد نظر را انتخاب کنید:", reply_markup=reply_markup)


async def select_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, subject, grade, lesson = query.data.split(':')
    context.user_data.update({'current_lesson': lesson, 'current_content_type': 'words'})

    keyboard = [
        [InlineKeyboardButton("📖 مرور و تلفظ", callback_data="show_content")],
        [InlineKeyboardButton("✍️ تمرین هوشمند", callback_data="start_practice")],
        [InlineKeyboardButton("📝 شروع آزمون", callback_data="setup_quiz")],
        [InlineKeyboardButton("بازگشت به انتخاب درس", callback_data=f"select_grade:{subject}:{grade}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً فعالیت مورد نظر را برای این درس انتخاب کنید:", reply_markup=reply_markup)


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_message = update.effective_message

    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("آموزش زبان عربی 🇮🇶", callback_data="select_subject:arabic")],
        [InlineKeyboardButton("آموزش زبان انگلیسی 🇬🇧", callback_data="select_subject:english")],
        [InlineKeyboardButton("املای دشوار فارسی 🇮🇷", callback_data="select_subject:persian_spelling")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await target_message.edit_text("به منوی اصلی بازگشتید. لطفا موضوع درسی را انتخاب کنید:", reply_markup=reply_markup)


# --- بخش تمرین هوشمند ---

async def start_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    subject, grade, lesson, content_type = ud['current_subject'], ud['current_grade'], ud['current_lesson'], ud[
        'current_content_type']

    full_list = db_manager.get_vocabulary_by_lesson(subject, grade, lesson, content_type)
    if not full_list:
        await query.edit_message_text("محتوایی برای تمرین این بخش یافت نشد.")
        return

    learned_indices = db_manager.load_user_progress(query.from_user.id, subject, grade, lesson, content_type)

    ud['practice_full_list'] = full_list
    ud['practice_learned_indices'] = learned_indices
    ud['practice_unlearned_indices'] = [i for i in range(len(full_list)) if i not in learned_indices]
    random.shuffle(ud['practice_unlearned_indices'])

    await show_practice_item(update, context)


async def show_practice_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ud = context.user_data

    if 'practice_unlearned_indices' not in ud or not ud['practice_unlearned_indices']:
        await query.edit_message_text("🎉 تبریک! شما تمام آیتم‌های این درس را یاد گرفته‌اید یا دور تمرین تمام شده است!")
        return

    current_item_index = ud['practice_unlearned_indices'][0]
    ud['current_practice_item_index'] = current_item_index
    item = ud['practice_full_list'][current_item_index]

    total_count = len(ud['practice_full_list'])
    learned_count = len(ud['practice_learned_indices'])
    progress_percent = (learned_count / total_count) * 100 if total_count > 0 else 0
    progress_bar = create_progress_bar(progress_percent)

    message_text = f"**{get_key_from_item(item, ud['current_subject'])}**\n\n"
    message_text += f"پیشرفت شما در این درس:\n{progress_bar}\n_{learned_count} از {total_count} آیتم یاد گرفته شده_"

    keyboard = [
        [
            InlineKeyboardButton("✅ بلدم", callback_data="practice:know"),
            InlineKeyboardButton("❌ بلد نیستم", callback_data="practice:dont_know")
        ],
        [InlineKeyboardButton("بازگشت به منوی درس",
                              callback_data=f"select_lesson:{ud['current_subject']}:{ud['current_grade']}:{ud['current_lesson']}")]
    ]
    await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_practice_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    answer = query.data.split(':')[1]

    current_item_index = ud.pop('current_practice_item_index')
    ud['practice_unlearned_indices'].pop(0)

    if answer == 'know':
        ud['practice_learned_indices'].add(current_item_index)
        db_manager.save_user_progress(
            query.from_user.id, ud['current_subject'], ud['current_grade'], ud['current_lesson'],
            ud['current_content_type'], ud['practice_learned_indices']
        )

    await show_practice_item(update, context)


# --- بخش آزمون ---

async def setup_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    subject, grade, lesson, content_type = ud['current_subject'], ud['current_grade'], ud['current_lesson'], ud[
        'current_content_type']

    full_list = db_manager.get_vocabulary_by_lesson(subject, grade, lesson, content_type)
    if not full_list or len(full_list) < 4:
        await query.edit_message_text("تعداد آیتم‌ها برای برگزاری آزمون در این درس کافی نیست (حداقل ۴ مورد نیاز است).")
        return

    ud['quiz_full_list'] = full_list
    ud['next_step'] = 'get_quiz_length'
    await query.edit_message_text(f"لطفاً تعداد سؤالات آزمون را وارد کنید (بین ۱ تا {len(full_list)}):")


async def handle_quiz_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    if ud.get('next_step') != 'get_quiz_length':
        return

    try:
        num_questions = int(update.message.text)
        max_questions = len(ud['quiz_full_list'])
        if not 1 <= num_questions <= max_questions:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(f"لطفاً یک عدد معتبر بین ۱ تا {len(ud['quiz_full_list'])} وارد کنید.")
        return

    ud['next_step'] = None
    ud['quiz_length'] = num_questions
    ud['quiz_score'] = 0
    ud['quiz_current_q'] = 0

    question_indices = random.sample(range(len(ud['quiz_full_list'])), num_questions)
    ud['quiz_question_indices'] = question_indices

    await update.message.reply_text(f"بسیار خب! آزمون با {num_questions} سؤال شروع می‌شود.")
    await send_quiz_question(update, context)


async def send_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data

    if 'quiz_current_q' not in ud or ud['quiz_current_q'] >= ud['quiz_length']:
        await end_quiz(update, context)
        return

    q_index = ud['quiz_question_indices'][ud['quiz_current_q']]
    question_item = ud['quiz_full_list'][q_index]
    correct_answer = get_answer_from_item(question_item, ud['current_subject'])
    ud['quiz_correct_answer'] = correct_answer

    options = {correct_answer}
    all_answers = {get_answer_from_item(item, ud['current_subject']) for item in ud['quiz_full_list']}
    all_answers.discard(correct_answer)

    while len(options) < 4 and all_answers:
        options.add(all_answers.pop())

    shuffled_options = random.sample(list(options), len(options))
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz_ans:{opt}")] for opt in shuffled_options]

    question_text = f"سوال {ud['quiz_current_q'] + 1} از {ud['quiz_length']}:\n\n"
    question_text += f"معنی **{get_key_from_item(question_item, ud['current_subject'])}** چیست؟"

    if isinstance(update, CallbackQuery):
        target = update.message
    else:
        target = update.effective_message

    await target.reply_text(question_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    selected_answer = query.data.split(':', 1)[1]

    feedback = ""
    if selected_answer == ud['quiz_correct_answer']:
        ud['quiz_score'] += 1
        feedback = "✅ پاسخ صحیح!"
    else:
        feedback = f"❌ اشتباه بود! پاسخ صحیح: **{ud['quiz_correct_answer']}**"

    await query.edit_message_text(f"{query.message.text}\n\nپاسخ شما: {selected_answer}\n{feedback}",
                                  parse_mode='Markdown')

    ud['quiz_current_q'] += 1
    await asyncio.sleep(2)
    await send_quiz_question(query, context)


async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    score = ud.get('quiz_score', 0)
    total = ud.get('quiz_length', 0)
    if total == 0:
        return

    percent = (score / total) * 100

    message = f"🎉 آزمون تمام شد! 🎉\n\n"
    message += f"نمره شما: **{score}** از **{total}**\n"
    message += f"درصد موفقیت: **{percent:.1f}%**\n\n"

    if percent == 100:
        message += "عالی بود! 🏆"
    elif percent >= 70:
        message += "خیلی خوب بود! 👍"
    else:
        message += "نیاز به تمرین بیشتری دارید. 💪"

    await update.effective_message.reply_text(message, parse_mode='Markdown')

    for key in [k for k in ud if k.startswith('quiz_')]:
        ud.pop(key)


# --- بخش مرور و تلفظ ---
async def show_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ud = context.user_data

    current_list = db_manager.get_vocabulary_by_lesson(ud['current_subject'], ud['current_grade'], ud['current_lesson'],
                                                       ud['current_content_type'])
    ud['browse_list'] = current_list
    ud['browse_index'] = -1

    if not current_list:
        await query.edit_message_text("محتوایی برای مرور یافت نشد.")
        return

    await handle_next_item_click(update, context)


async def handle_next_item_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    item_index = ud.get('browse_index', -1)
    current_list = ud.get('browse_list', [])

    if item_index + 1 < len(current_list):
        item_index += 1
        ud['browse_index'] = item_index
        current_item = current_list[item_index]
        subject = ud['current_subject']

        message_text = ""
        if subject == 'arabic':
            message_text = f"**عربی:** {current_item.get('arabic', '')}\n**فارسی:** {current_item.get('farsi', '')}\n**انگلیسی:** {current_item.get('english', '')}"
        elif subject == 'english':
            message_text = f"**English:** {current_item.get('english', '')}\n**فارسی:** {current_item.get('farsi', '')}\n**عربی:** {current_item.get('arabic', '')}"
        elif subject == 'persian_spelling':
            message_text = f"**کلمه:** {current_item.get('word', '')}\n**معنی:** {current_item.get('meaning', '')}\n**مثال:** {current_item.get('example', '')}"

        keyboard = [
            [InlineKeyboardButton("آیتم بعدی ▶️", callback_data="next_item")],
            [
                InlineKeyboardButton("🇮🇷", callback_data="pronounce:fa"),
                InlineKeyboardButton("🇬🇧", callback_data="pronounce:en"),
                InlineKeyboardButton("🇮🇶", callback_data="pronounce:ar"),
            ]
        ]
        keyboard.append([InlineKeyboardButton("بازگشت ↩️",
                                              callback_data=f"select_lesson:{ud['current_subject']}:{ud['current_grade']}:{ud['current_lesson']}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode='Markdown')

    else:
        await query.edit_message_text("✅ مرور این بخش تمام شد.")


async def pronounce_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال آماده‌سازی تلفظ...", show_alert=False)

    ud = context.user_data
    if 'browse_index' in ud and ud['browse_index'] != -1:
        current_item = ud['browse_list'][ud['browse_index']]
    else:
        await query.answer("لطفاً ابتدا یک آیتم را برای مرور انتخاب کنید.", show_alert=True)
        return

    try:
        lang_code = query.data.split(':')[1]
    except IndexError:
        return

    text_to_pronounce = ""
    if lang_code == 'ar':
        text_to_pronounce = current_item.get('arabic')
    elif lang_code == 'en':
        text_to_pronounce = current_item.get('english')
    elif lang_code == 'fa':
        text_to_pronounce = current_item.get('word') or current_item.get('farsi')

    if not text_to_pronounce:
        await query.answer("متن معادل برای این زبان یافت نشد.", show_alert=True)
        return

    try:
        mp3_fp = io.BytesIO()
        tts = gTTS(text=text_to_pronounce, lang=lang_code)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        await query.message.reply_voice(voice=mp3_fp, caption=f"تلفظ ({lang_code}): **{text_to_pronounce}**",
                                        parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error generating audio with gTTS for '{text_to_pronounce}': {e}")
        await query.answer("خطا در تولید یا ارسال فایل صوتی.", show_alert=True)


def main():
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(select_subject, pattern="^select_subject:.*$"))
    application.add_handler(CallbackQueryHandler(select_grade, pattern="^select_grade:.*$"))
    application.add_handler(CallbackQueryHandler(select_lesson, pattern="^select_lesson:.*$"))

    # Activity Handlers
    application.add_handler(CallbackQueryHandler(show_content, pattern="^show_content$"))
    application.add_handler(CallbackQueryHandler(handle_next_item_click, pattern="^next_item$"))
    application.add_handler(CallbackQueryHandler(pronounce_handler, pattern="^pronounce:.*$"))
    application.add_handler(CallbackQueryHandler(start_practice, pattern="^start_practice$"))
    application.add_handler(CallbackQueryHandler(handle_practice_answer, pattern="^practice:.*$"))
    application.add_handler(CallbackQueryHandler(setup_quiz, pattern="^setup_quiz$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_length))
    application.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern="^quiz_ans:.*$"))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()