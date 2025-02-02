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
from time import sleep

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
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find campaign paper link
        campaign_link = None
        for link in soup.find_all('a', href=True):
            if "JYSK/rs/CampaignPaper" in link['href']:
                campaign_link = link['href']
                break
        
        if not campaign_link:
            logging.warning("No campaign link found")
            return []
        
        # Scrape campaign page
        campaign_response = requests.get(campaign_link, timeout=10)
        campaign_response.raise_for_status()
        campaign_soup = BeautifulSoup(campaign_response.content, 'html.parser')
        
        # Extract promotions - adjust selector based on actual page structure
        promotions = []
        for item in campaign_soup.select('.product-item'):  # Update this selector
            title = item.select_one('.product-title')
            if title:
                promotions.append(title.text.strip())
        
        return promotions

    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        raise

def is_new_post(post):
    now = datetime.now(pytz.timezone("Europe/Belgrade"))  # Your timezone
    return post.date > (now - timedelta(days=1))

def scrape_instagram(username, password, target_account):
    loader = instaloader.Instaloader()
    
    # Try loading session
    try:
        loader.load_session_from_file(username)
    except FileNotFoundError:
        loader.login(username, password)
        loader.save_session_to_file()
    profile = instaloader.Profile.from_username(loader.context, target_account)
    
    posts = profile.get_posts()  # Remove 'since' parameter
    
    promotions = []
    for post in posts:
        # Keep date filtering in the loop
        if 'promotion' in post.caption.lower() and is_new_post(post):
            promotions.append(post.caption)
            # Break loop if we reach posts older than 1 day
            if not is_new_post(post):
                break
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

def read_counter():
    try:
        with open('counter.txt', 'r') as f:
            return int(f.read())
    except FileNotFoundError:
        return 0

def write_counter(value):
    with open('counter.txt', 'w') as f:
        f.write(str(value))

def main():
    # Load previous promotions
    last_promotions = load_last_promotions()
    try:
        website_url = 'https://jysk.rs/'
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

        # Combine all new promotions
        all_new_promotions = website_promotions + instagram_promotions
        
        # Find actually new promotions
        new_promotions = [p for p in all_new_promotions if p not in last_promotions]
        
        # Update stored promotions
        if new_promotions:
            save_promotions(all_new_promotions)
            email_body = '\n'.join(new_promotions)
            send_email(email_subject, email_body, email_to, email_from, smtp_server, smtp_port, smtp_user, smtp_password)
            logging.info('Email sent with new promotions')

        # Weekly email logic
        no_promotion_days = read_counter()
        
        if new_promotions:
            no_promotion_days = 0
            # Send email with new promotions
        else:
            no_promotion_days += 1
        
        if no_promotion_days >= 7:
            send_email("Weekly Summary", "No promotions found this week", ...)
            no_promotion_days = 0
        
        write_counter(no_promotion_days)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()