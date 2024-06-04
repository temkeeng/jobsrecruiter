import logging
import os
from re import sub

import pandas as pd
import telebot
from telebot.util import split_string
from dotenv import load_dotenv
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import EventData, EventMetrics, Events
from linkedin_jobs_scraper.filters import (
    OnSiteOrRemoteFilters, RelevanceFilters, SalaryBaseFilters, TimeFilters)
from linkedin_jobs_scraper.query import Query, QueryFilters, QueryOptions
from slugify import slugify

load_dotenv()
logging.basicConfig(level=logging.INFO)

# List to store the scraped data
scraped_data = []
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
QUERY = os.getenv('QUERY')
CHAT_ID = os.getenv("TELEGRAM_CHANNEL_ID")
LOCATION = os.getenv('LOCATION')


def on_data(data: EventData):
    print('[ON_DATA]', data.title, data.company, data.description, data.date, data.link)
    # Append the data to the list
    scraped_data.append({
        'title': data.title,
        'company': data.company,
        'description': data.description,
        'date': data.date,
        'link': data.link
    })


def on_metrics(metrics: EventMetrics):
    print('[ON_METRICS]', str(metrics))
    bot.send_message(
        chat_id=CHAT_ID,
        text=f'🔍 #{slugify(QUERY, separator='_')}\nДоступно: {metrics.processed} вакансий',
    )


def on_error(error):
    print('[ON_ERROR]', error)


def on_end():
    print('[ON_END]')
    # Save the data to a CSV file
    df = pd.DataFrame(scraped_data)
    if os.path.isfile('linkedin_jobs.csv'):
        df.to_csv(
            'linkedin_jobs.csv', mode='a',
            header=False, index=False, encoding='utf-8')
    else:
        df.to_csv('linkedin_jobs.csv', mode='w',
                  header=True, index=False, encoding='utf-8')

    pd.DataFrame().to_csv('linkedin_jobs.csv',
                          mode='a', header=False, index=False)
    print('Data saved to linkedin_jobs.csv')
    return scraped_data


def get_jobs():
    scraper = LinkedinScraper(
        chrome_executable_path=None,
        chrome_binary_location=None,
        chrome_options=None,
        headless=True,
        max_workers=1,
        slow_mo=0.5,
        page_load_timeout=40
    )
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)
    scraper.on(Events.METRICS, on_metrics)
    queries = [
        Query(
            query=QUERY,
            options=QueryOptions(
                locations=[LOCATION],
                apply_link=True,
                limit=10,
                filters=QueryFilters(
                    # company_jobs_url='https://www.linkedin.com/jobs/search/?f_C=1441%2C'
                    #                  '17876832%2C791962%2C2374003%2C18950635%2C16140%2C10440912&geoId=92000000',
                    relevance=RelevanceFilters.RECENT,
                    time=TimeFilters.MONTH,
                    on_site_or_remote=[OnSiteOrRemoteFilters.REMOTE],
                    base_salary=SalaryBaseFilters.SALARY_180K
                )
            )
        )
    ]
    scraper.run(queries)


def send_jobs():
    for job in scraped_data:
        job_description = remove_extra_spaces(
            job['title'] + job['description'])
        try:
            bot.send_message(
                chat_id=CHAT_ID,
                text=f'*{job['title']}*\n```{job_description}```\n',
                parse_mode="Markdown"
            )
        except telebot.apihelper.ApiTelegramException:
            splitted_text = split_string(job_description, 4096)
            page = 1
            for text in splitted_text:
                if page > 1:
                    job_title = f'*{job['title']}*\nPage *{page}* 👇'
                else:
                    job_title = f'*{job['title']}*'
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=job_title,
                    parse_mode="Markdown"
                )
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f'```{text}```',
                    parse_mode="Markdown")
                page += 1


def remove_extra_spaces(text):
    paragraphs = text.split('\n\n')
    cleaned = []
    for paragraph in paragraphs:
        cleaned.append(sub(r'\s+', ' ', paragraph))
    return '\n'.join(cleaned)


if __name__ == '__main__':
    get_jobs()
    send_jobs()
