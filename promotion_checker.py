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
import ssl

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
    now = datetime.now(pytz.timezone("Europe/Belgrade"))
    post_time = post.date.astimezone(pytz.timezone("Europe/Belgrade"))  # Convert to your tz
    return post_time > (now - timedelta(days=7))

# Instagram scraping function
def scrape_instagram_profiles(target_accounts):
    loader = instaloader.Instaloader()
    session_file = "instagram_session"
    
    # Try loading existing session
    try:
        if os.path.exists(session_file):
            loader.load_session_from_file(os.getenv('INSTAGRAM_USER'), session_file)
            logging.info("Loaded existing Instagram session")
        else:
            raise FileNotFoundError
    except Exception as e:
        logging.warning(f"Session load failed: {e}. Attempting login...")
        loader.login(os.getenv('INSTAGRAM_USER'), os.getenv('INSTAGRAM_PASSWORD'))
        loader.save_session_to_file(session_file)
        logging.info("Created new Instagram session")
        sleep(10)  # Critical: Add delay after login

    all_promotions = []
    for account in target_accounts:
        try:
            profile = instaloader.Profile.from_username(loader.context, account)
            posts = profile.get_posts()
            
            account_promotions = []
            for post in posts:
                if is_new_post(post):
                    post_url = f"https://www.instagram.com/p/{post.shortcode}/"
                    account_promotions.append({
                        'account': account,
                        'caption': post.caption,
                        'url': post_url
                    })
                    sleep(5)  # Add delay between posts
                
                if not is_new_post(post):
                    break
                
            all_promotions.extend(account_promotions)
            logging.info(f"Scraped {len(account_promotions)} promotions from {account}")
            sleep(15)  # Add delay between accounts
            
        except Exception as e:
            logging.error(f"Error scraping {account}: {e}")
            sleep(60)  # Backoff on errors
            continue
    
    return all_promotions

def compare_results(old_promotions, new_promotions):
    old_urls = {p['url'] for p in old_promotions}
    return [p for p in new_promotions if p['url'] not in old_urls]

def load_last_promotions():
    try:
        with open('last_promotions.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_promotions(promotions):
    with open('last_promotions.json', 'w') as f:
        json.dump(promotions, f, indent=2)

def send_email(subject, body, to_emails, from_email, smtp_server, smtp_port, smtp_user, smtp_password):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = ", ".join(to_emails)  # Convert list to comma-separated string
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_emails, msg.as_string())  # Keep as list here
    except Exception as e:
        logging.error(f"Email sending failed: {e}")
        raise

def main():
    # Load previous promotions
    last_promotions = load_last_promotions()
    try:
        insta_username = ig_user
        insta_password = ig_password
        # Instagram target accounts list
        insta_target_accounts = [
            'jyskrs',
            'jyskme',
            'okov.me',
            'commodo.me',
            'kompanija_cerovo',
            'multicom.me',
            'datika.me',
            'eurotehnika.mn',
            'tehnomax.me',
            'tehno.lux',
            'tehnoplus',
            'loudshop.me',
            'pcgamer.me'
        ]
        email_subject = 'New Promotions Detected'
        email_to = ['radovan40@yahoo.com', 'ivana50@live.com']
        email_from = email_user
        smtp_server = 'smtp.mail.yahoo.com'
        smtp_port = 465  # Yahoo requires SSL on port 465 (not 587)
        smtp_user = email_user
        smtp_password = email_password

         # Load previous promotions
        last_promotions = load_last_promotions()
        
        # Scrape Instagram (without login in CI)
        instagram_promotions = scrape_instagram_profiles(
            insta_target_accounts
        )
        logging.info(f'Instagram promotions: {instagram_promotions}')
        
        # Find new promotions by URL
        new_promotions = compare_results(last_promotions, instagram_promotions)
        
        # email body formatting
        if new_promotions:
            email_body = "📢 New Promotions Found! 🎉\n\n"
            for idx, promo in enumerate(new_promotions, 1):
                email_body += (f"{idx}. [{promo['account']}] {promo['caption']}\n"
                            f"   🔗 {promo['url']}\n\n")
            email_body += "Happy shopping! 🛒"
            # Update saving to store full promo data
            save_promotions(instagram_promotions)
            # email sending call
            send_email(
                email_subject, 
                email_body, 
                email_to,  # Now a list
                email_from,
                smtp_server,
                smtp_port,
                smtp_user,
                smtp_password
            )
            logging.info('Email sent with new promotions')

        # Ub case of no new promotions
        if not new_promotions:
            send_email(
                "No New Promotions Today",
                "No new promotions found in the latest check.",
                email_to,
                email_from,
                smtp_server,
                smtp_port,
                smtp_user,
                smtp_password
            )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()