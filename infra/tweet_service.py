import os, tweepy
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ.get('TWEET_SERVICE_TOKEN', '')

CK  = os.environ.get('X_CONSUMER_KEY',        'TFPEAHckzih8MAnK9hbNqsuIC')
CS  = os.environ.get('X_CONSUMER_SECRET',      'WZmprWlBBwr1q48ddeolRVlkTJqpFE4o58kO9b5xoYrslj8npt')
AT  = os.environ.get('X_ACCESS_TOKEN',         '2058924783073460224-sOpAU1VjBTJNdgwK8E47qVZs1EGsVk')
ATS = os.environ.get('X_ACCESS_TOKEN_SECRET',  'YyoeVZ1ZRLZbOokCJ5a9Eybi3bdSs82RuQXIo5r4imlX7')


@app.post('/tweet')
def post_tweet():
    auth = request.headers.get('Authorization', '')
    if TOKEN and auth != f'Bearer {TOKEN}':
        return jsonify({'error': 'unauthorized'}), 401
    body = request.get_json(force=True)
    text = (body or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': 'text required'}), 400
    client = tweepy.Client(consumer_key=CK, consumer_secret=CS,
                           access_token=AT, access_token_secret=ATS)
    resp = client.create_tweet(text=text)
    tweet_id = resp.data['id']
    return jsonify({'ok': True, 'tweet_id': tweet_id,
                    'url': f'https://x.com/ALphaForgeAIio/status/{tweet_id}'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9127)
