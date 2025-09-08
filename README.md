# horime
simple anime streaming platform (similar to anig\*, anicr\*sh or animek\*i without directly hosting the content)

# features
- stream anime episodes by entering embed links from hosting platforms
- browse and search anime collection
- request missing animes and submit feedback
- rate limiting and spam protection using altcha
- simple but responsive design with modern ui
- json-based data storage for animes, requests and feedback

# how to use
1. install python3
2. install requirements: `pip install -r requirements.txt`
3. add environment variables in .env.example
4. rename the `.env.example` to `.env`
5. start the app: `python3 app.py`

## required environment variables
- `ALTCHA_HMAC_KEY`: hmac key for altcha spam protection (random 32-byte string)
- `EMAIL`: your contact email address
- `SECRET_KEY`: flask secret key (random 32-byte string)
- `SITE_NAME`: name of the website
- `TELEGRAM_USER`: telegram username for contact

## optional environment variables
- `FLASK_ENV`: set to `development` for debug mode