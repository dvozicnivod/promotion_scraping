import requests
from bs4 import BeautifulSoup
import instaloader
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
from dotenv import load_dotenv
import pytz
from datetime import datetime, timedelta
import sys
import json
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(filename='logs.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

# Load .env file locally
load_dotenv()
email_user = os.getenv('EMAIL_USER')
email_password = os.getenv('EMAIL_PASSWORD')
ig_user = os.getenv('INSTAGRAM_USER')
ig_password = os.getenv('INSTAGRAM_PASSWORD')

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
def scrape_website(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()  # Raise HTTP errors
    soup = BeautifulSoup(response.content, 'html.parser')
    # Find the promotion link using "JYSK/rs/CampaignPaper" string
    promotion_link = None
    for link in soup.find_all('a', href=True):
        if "JYSK/rs/CampaignPaper" in link['href']:
            promotion_link = link['href']
            break
    if promotion_link:
        promotion_response = requests.get(promotion_link, timeout=10)
        promotion_response.raise_for_status()
        promotion_soup = BeautifulSoup(promotion_response.content, 'html.parser')
        # Extract relevant data from promotion page (customize as needed)
        promotions = promotion_soup.find_all('div', class_='promotion')
        return [promo.text for promo in promotions]
    return []

def is_new_post(post):
    now = datetime.now(pytz.timezone("Europe/Belgrade"))  # Your timezone
    return post.date > (now - timedelta(days=1))

# Function to scrape Instagram
def scrape_instagram(username, password, target_account):
    loader = instaloader.Instaloader()
    loader.login(username, password)
    profile = instaloader.Profile.from_username(loader.context, target_account)
    
    try:
        with open('last_check.txt', 'r') as f:
            last_check = datetime.fromisoformat(f.read())
    except FileNotFoundError:
        last_check = datetime.now() - timedelta(days=7)  # Default to 1 week

    posts = profile.get_posts(since=last_check)
    
    # Save current time as last check
    with open('last_check.txt', 'w') as f:
        f.write(datetime.now().isoformat())

    promotions = []
    for post in posts:
        if 'promotion' in post.caption.lower() and is_new_post(post):
            promotions.append(post.caption)
    return promotions

# Function to compare results
def compare_results(old_promotions, new_promotions):
    return [promo for promo in new_promotions if promo not in old_promotions]

# Function to send emails via SMTP
def send_email(subject, body, to_email, from_email, smtp_server, smtp_port, smtp_user, smtp_password):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_password)
    text = msg.as_string()
    server.sendmail(from_email, to_email, text)
    server.quit()

def load_last_promotions():
    try:
        with open('last_promotions.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_promotions(promotions):
    with open('last_promotions.json', 'w') as f:
        json.dump(promotions, f)

def main():
    # Load previous promotions
    last_promotions = load_last_promotions()
    try:
        website_url = 'https://yisk.rs'
        insta_username = ig_user
        insta_password = ig_password
        insta_target_account = 'jyskrs'
        email_subject = 'New Promotions Detected'
        email_to = 'recipient@example.com'
        email_from = email_user
        smtp_server = 'smtp.mail.yahoo.com'
        smtp_port = 587
        smtp_user = email_user
        smtp_password = email_password

         # Load previous promotions
        last_promotions = load_last_promotions()

        # Scrape new promotions
        website_promotions = scrape_website(website_url)
        logging.info(f'Website promotions: {website_promotions}')

        # Scrape Instagram
        instagram_promotions = scrape_instagram(insta_username, insta_password, insta_target_account)
        logging.info(f'Instagram promotions: {instagram_promotions}')

        all_new_promotions = website_promotions + instagram_promotions

        # Compare with last run
        new_promotions = [p for p in all_new_promotions if p not in last_promotions]
        
        # Compare results
        new_promotions = compare_results(website_promotions, instagram_promotions)
        logging.info(f'New promotions: {new_promotions}')

        # Send email if new promotions are found
        if new_promotions:
            email_body = '\n'.join(new_promotions)
            send_email(email_subject, email_body, email_to, email_from, smtp_server, smtp_port, smtp_user, smtp_password)
            logging.info('Email sent with new promotions')
            save_promotions(all_new_promotions)

        # Inside main()
        global no_promotion_days  # Or store in a file

        if new_promotions:
            # Reset counter
            no_promotion_days = 0
        else:
            no_promotion_days += 1

        # Weekly debug email (add separate workflow for this)
        if no_promotion_days >= 7:
            send_email("Weekly Summary", "No promotions found this week.", ...)
            no_promotion_days = 0

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()