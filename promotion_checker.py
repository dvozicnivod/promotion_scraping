import requests
from bs4 import BeautifulSoup
import instaloader
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Configure logging
logging.basicConfig(filename='logs.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

# Function to scrape websites
def scrape_website(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    # Extract relevant data (customize as needed)
    promotions = soup.find_all('div', class_='promotion')
    return [promo.text for promo in promotions]

# Function to scrape Instagram
def scrape_instagram(username, password, target_account):
    loader = instaloader.Instaloader()
    loader.login(username, password)
    profile = instaloader.Profile.from_username(loader.context, target_account)
    posts = profile.get_posts()
    promotions = []
    for post in posts:
        if 'promotion' in post.caption.lower():
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

# Main function
def main():
    website_url = 'https://example.com'
    insta_username = 'your_instagram_username'
    insta_password = 'your_instagram_password'
    insta_target_account = 'target_account'
    email_subject = 'New Promotions Detected'
    email_to = 'recipient@example.com'
    email_from = 'sender@example.com'
    smtp_server = 'smtp.example.com'
    smtp_port = 587
    smtp_user = 'smtp_user'
    smtp_password = 'smtp_password'

    # Scrape website
    website_promotions = scrape_website(website_url)
    logging.info(f'Website promotions: {website_promotions}')

    # Scrape Instagram
    instagram_promotions = scrape_instagram(insta_username, insta_password, insta_target_account)
    logging.info(f'Instagram promotions: {instagram_promotions}')

    # Compare results
    new_promotions = compare_results(website_promotions, instagram_promotions)
    logging.info(f'New promotions: {new_promotions}')

    # Send email if new promotions are found
    if new_promotions:
        email_body = '\n'.join(new_promotions)
        send_email(email_subject, email_body, email_to, email_from, smtp_server, smtp_port, smtp_user, smtp_password)
        logging.info('Email sent with new promotions')

if __name__ == '__main__':
    main()