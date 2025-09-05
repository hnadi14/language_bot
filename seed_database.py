import sys
import os

# اطمینان از اینکه database_manager در مسیر پایتون قرار دارد
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager
import logging

# وارد کردن داده‌ها از فایل‌های جداگانه
from arabic_data import ARABIC_DATA
from english_data import ENGLISH_DATA
from persian_data import PERSIAN_DATA


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
seed_logger = logging.getLogger(__name__)

# تجمیع تمام داده‌ها در یک دیکشنری اصلی
ALL_COURSES_DATA = {
    "arabic": ARABIC_DATA,
    "english": ENGLISH_DATA,
    "persian_spelling": PERSIAN_DATA
}


def seed_data():
    """
    داده‌های آموزشی را از دیکشنری ALL_COURSES_DATA به پایگاه داده وارد می‌کند.
    """
    db_manager = DatabaseManager()
    total_inserted = 0
    total_duplicates = 0

    try:
        for subject, subject_data in ALL_COURSES_DATA.items():
            for grade, grade_data in subject_data.items():
                for lesson_key, lesson_content in grade_data.items():
                    if isinstance(lesson_content, dict):
                        for content_type, items in lesson_content.items():
                            if content_type in ["words", "sentences"]:
                                for item_data in items:
                                    inserted = db_manager.insert_vocabulary_item(
                                        subject=subject,
                                        grade=grade,
                                        lesson=lesson_key,
                                        content_type=content_type,
                                        item_data=item_data
                                    )
                                    if inserted:
                                        total_inserted += 1
                                    else:
                                        total_duplicates += 1

        seed_logger.info(f"Data seeding complete. Total inserted: {total_inserted}, Total duplicates ignored: {total_duplicates}")

    except Exception as e:
        seed_logger.error(f"An error occurred during data seeding: {e}")
    finally:
        db_manager.close()


if __name__ == '__main__':
    seed_logger.info("Starting database seeding...")
    seed_data()
    seed_logger.info("Database seeding finished.")