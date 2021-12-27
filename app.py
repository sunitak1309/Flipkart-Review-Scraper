from time import sleep
from random import random, randint
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib.parse as urlparse
from urllib.parse import parse_qs

from flask import Flask, render_template, request
from flask_cors import CORS,cross_origin

app = Flask(__name__)
app.static_folder = 'static'

BASE_URL = "https://www.flipkart.com/"
dataset = []

def get_popular_product_s_titles_and_urls(search_query: str, popular_products_count_limit: int = None):
    search_url = f"{BASE_URL}search?q={search_query}&sort=popularity"
    search_response = requests.get(search_url)

    # Pause the loop for 1-3 seconds to simulate natural setting not overwhelm the server
    # with back to back requests without any pause
    sleep(randint(1, 3))

    search_html_soup = BeautifulSoup(search_response.content, 'html.parser')
    search_results_products = search_html_soup.find_all('div', attrs={'class': '_4ddWXP'})

    product_titles, product_urls = [], []

    product_count = 0

    for product in search_results_products:

        ad_mention_subrow = product.find("div", attrs={"class": "_4HTuuX"})

        is_ad = not not ad_mention_subrow

        if not is_ad:

            title_mention_subrow = product.find("a", attrs={"class": "s1Q9rs"})

            product_title = title_mention_subrow["title"]
            product_relative_url = title_mention_subrow["href"]
            product_url = urljoin(BASE_URL, product_relative_url)

            parsed_url = urlparse.urlparse(product_url)
            parsed_url_path = parsed_url.path
            parsed_url_path_split = parsed_url_path.split("/")
            parsed_url_path_split[2] = "product-reviews"
            parsed_url_path_modified = "/".join(parsed_url_path_split)
            parsed_url_modified = parsed_url._replace(path=parsed_url_path_modified)
            product_url = parsed_url_modified.geturl()

            product_titles.append(product_title)
            product_urls.append(product_url)

            product_count += 1

            if popular_products_count_limit and (product_count >= popular_products_count_limit):
                break

    return product_titles, product_urls


def create_summary(df: pd.DataFrame):
    grouped = [pd.DataFrame(y) for x, y in df.groupby('product_id', as_index=False)]
    for i in range(len(grouped)):
        grouped[i].index = np.arange(1, len(grouped[i]) + 1)

    summary_reviews = []
    for i in range(len(grouped)):
        pid = grouped[i]['product_id'].unique()[0]
        ptitle = grouped[i]['product_title'].unique()[0]
        total = len(grouped[i])
        series = grouped[i]['sentiment'].value_counts()
        try:
            pos = series['positive']
        except:
            pos = 0
        try:
            neg = series['negative']
        except:
            neg = 0
        try:
            neu = series['neutral']
        except:
            neu = 0
        summary_reviews.append({'id': pid, 'title': ptitle, 'total reviews': total,
                                '# positive': pos, '# neutral': neu, '# negative': neg})

    return summary_reviews


@app.route('/', methods=['GET'])
@cross_origin()
def homePage():
	return render_template('index.html')

@app.route('/review', methods=('POST', 'GET'))
@cross_origin()
def index():
    if request.method == 'POST':
        try:
            SEARCH_QUERY = request.form['content'].replace(' ','')
            TOP_N_PRODUCTS = 5
            REVIEW_PAGES_TO_SCRAPE_FROM_PER_PRODUCT = 3

            product_titles, product_urls = get_popular_product_s_titles_and_urls(SEARCH_QUERY, TOP_N_PRODUCTS)

            if len(product_urls) == 0:
                return render_template('error.html')

            for idx, url in enumerate(product_urls):
                # iterating over review pages
                for i in range(1, REVIEW_PAGES_TO_SCRAPE_FROM_PER_PRODUCT + 1):
                    parsed = urlparse.urlparse(url)
                    pid = parse_qs(parsed.query)['pid'][0]
                    URL = f"{url}&page={i}"

                    r = requests.get(URL)

                    # Pause the loop for 0-1 seconds to simulate natural setting not overwhelm the server
                    # with back to back requests without any pause
                    sleep(random())
                    soup = BeautifulSoup(r.content, 'html.parser')

                    rows = soup.find_all('div', attrs={'class': 'col _2wzgFH K0kLPL'})

                    for row in rows:

                        # finding all rows within the block
                        sub_row = row.find_all('div', attrs={'class': 'row'})

                        # extracting text from 1st 2nd and 4th row
                        rating = sub_row[0].find('div').text
                        summary = sub_row[0].find('p').text
                        summary = summary.strip()
                        review = sub_row[1].find_all('div')[2].text
                        review = review.strip()
                        location = ""
                        location_row = sub_row[3].find('p', attrs={'class': '_2mcZGG'})
                        if location_row:
                            location_row = location_row.find_all('span')
                            if len(location_row) >= 2:
                                location = location_row[1].text
                                location = "".join(location.split(",")[1:]).strip()
                        date = sub_row[3].find_all('p', attrs={'class': '_2sc7ZR'})[1].text

                        sub_row_2 = row.find_all('div', attrs={'class': '_1e9_Zu'})[0].find_all('span', attrs={'class': '_3c3Px5'})

                        upvotes = sub_row_2[0].text
                        downvotes = sub_row_2[1].text
                        sentiment = ""

                        if int(rating) > 3:
                            sentiment = 'positive'
                        elif int(rating) == 3:
                            sentiment = 'neutral'
                        else:
                            sentiment = 'negative'

                        # appending to dataset
                        dataset.append(
                            {'product_id': pid, 'product_title': product_titles[idx], 'rating': rating, 'summary': summary,
                            'review': review, 'location': location, 'date': date, 'upvotes': upvotes,
                            'downvotes': downvotes, 'sentiment': sentiment})

            if len(dataset) == 0:
                return render_template('error.html')

            df = pd.DataFrame(dataset)

            summary_reviews = create_summary(df)

            return render_template('summaries.html', summaries=summary_reviews)


        except:
            return render_template('error.html')


@app.route('/review/<p_id>')
@cross_origin()
def my_view_func(p_id):
    specific_data = []
    for d in dataset:
        if d['product_id'] == p_id:
            specific_data.append(d)
    return render_template('reviews.html', reviews=specific_data)



if __name__ == '__main__':
	app.run(debug=True)