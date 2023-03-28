import json
from urllib.request import urlopen
import os
import matplotlib.pyplot as plt
import plotly
import twelvedata
from bs4 import BeautifulSoup as bs
from flask import render_template, request, redirect, url_for, session, g
from twelvedata import TDClient
from Stock_Investors_Diary import app, db
import pandas_datareader as pdr
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import numpy as np
import io
import random
from flask import Response
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure


API_KEY = os.getenv("API_KEY")
TIINGO_KEY = os.getenv("TIINGO_KEY")
global graph_5m
global graph
td = TDClient(API_KEY)
model = tf.keras.models.load_model("../LSTM.h5")


@app.route('/')
def login_page():
    if g.user in session['user']:
        return redirect(url_for("home_page"))
    print("Homepage")
    print(g.user)
    print(session)
    return render_template('login1.html', msg='')


@app.route('/logout')
def logout():
    session.pop(g.user, None)
    print("logged out")
    print(session)
    return render_template("login1.html", msg="SUCCESSFULLY LOGGED OUT")


@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']
    else:
        session['user'] = []


@app.route('/login', methods=['GET', 'POST'])
def login():
    collection = db["Accounts"]
    if request.method == 'POST':
        try:
            user_name = request.form['u']
            password = request.form['p']
            session.pop("user", None)
            authenticate = collection.find_one({"Username": user_name, "Password": password})
            if authenticate is not None:
                session.permanent = True
                session['user'] = str(authenticate['_id'])
                print("Logged in")
                print(session)
                return redirect(url_for('home_page')) # redirect('/')
            else:
                print("User not Found")
                return render_template('login1.html', msg='INVALID USER')

        except RuntimeError as e:
            print(e, " : Login Authentication Failed")

    else:
        if g.user in session:
            return redirect(url_for("home_page"))
        return render_template('login1.html', msg='PLEASE LOGIN AGAIN')


@app.route('/home', methods=['GET', 'POST'])
def home_page():
    if g.user:
        user = get_user()
        if not user['watchlist']:
            return render_template('index1.html', stock="Add stocks to watchlist to view Graphs")
        stock = user['watchlist'][0]
        stk_name, stk_symbol = stock.split("#")
        details = get_stock_details(stk_symbol)
        stk_symbols = []
        watchlist = []
        for i in user["watchlist"]:
            name, symbol = i.split("#")
            watchlist.append(name)
            stk_symbols.append(symbol)
        try:
            ts = td.time_series(
                symbol=stk_symbol,
                outputsize=15,
                interval="5min",
            )
            fig = ts.as_plotly_figure()
            global graph
            graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            return render_template('index.html', stock=stk_name.upper(), graph=graph, symbol=stk_symbol,
                                   userstock=watchlist, stk_symbols=stk_symbols, details=details, zip=zip)
        except twelvedata.exceptions.TwelveDataError:
            print("Try later")
            return render_template('index.html', stock=stk_name.upper(), symbol=stk_symbol,
                                   userstock=watchlist, stk_symbols=stk_symbols, details=details, zip=zip)


@app.route('/add_watchlist', methods=['GET', 'POST'])
def add_watchlist():
    collection = db["Accounts"]
    # user = collection.find_one({"_id": session['user']})
    user = get_user()
    added_stock = request.form['StockName']
    # print(user["watchlist"])
    if added_stock not in user["watchlist"]:
        # old = {"_id": session['user']}
        old = {"_id": user['_id']}
        user['watchlist'].append(added_stock)
        new = {"$set": {"watchlist": user['watchlist']}}
        collection.update_one(old, new)
        stk_symbols = []
        watchlist = []
        for i in user["watchlist"]:
            name, symbol = i.split("#")
            watchlist.append(name)
            stk_symbols.append(symbol)
        return redirect(url_for('home_page'))
    return redirect(url_for('home_page'))


@app.route('/remove_watchlist', methods=['GET', 'POST'])
def remove_watchlist():
    collection = db["Accounts"]
    # user = collection.find_one({"_id": session['user']})
    user = get_user()
    stock = request.args['symbol']
    for i in user['watchlist']:
        if stock == i.split("#")[1]:
            user['watchlist'].remove(i)
    old = {"_id": user['_id']}
    new = {"$set": {"watchlist": user['watchlist']}}
    collection.update_one(old, new)
    stk_symbols = []
    for i in user["watchlist"]:
        stk_symbols.append(i.split('#')[1])
    return redirect(url_for('home_page'))


@app.route('/display_stock', methods=['GET', 'POST'])
def display_stock_graph():
    stock = request.args['symbol']
    details = get_stock_details(stock)
    user = get_user()
    watchlist = user["watchlist"]
    stk_symbols = []
    stk_names = []
    stk_name = ""
    for i in watchlist:
        name, symbol = i.split('#')
        if stock == symbol:
            stk_name = name
        stk_names.append(name)
        stk_symbols.append(symbol)

    # interval : 5 min
    try:
        ts = td.time_series(
            symbol=stock,
            outputsize=15,
            interval="5min",
        )
        fig = ts.as_plotly_figure()
        global graph
        graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template("index.html", stock=stk_name.upper(), symbol=stock,
                               graph=graph, userstock=stk_names, details=details,
                               stk_symbols=stk_symbols, zip=zip)
    except twelvedata.exceptions.TwelveDataError:
        print("Try later")
        return render_template("index.html", stock=stk_name.upper(), symbol=stock,
                               graph=graph, userstock=stk_names, details=details,
                               stk_symbols=stk_symbols, zip=zip)


@app.route('/interval_graph', methods=['GET', 'POST'])
def interval_graph():
    user = get_user()
    stock = request.args['symbol']
    interval = request.args['interval']
    details = get_stock_details(stock)
    watchlist = user["watchlist"]
    stk_symbols = []
    stk_names = []
    stk_name = ""
    for i in watchlist:
        name, symbol = i.split('#')
        if stock == symbol:
            stk_name = name
        stk_names.append(name)
        stk_symbols.append(symbol)
    try:
        # interval : 5 min
        ts = td.time_series(
            symbol=stock,
            outputsize=15,
            interval=interval,
        )
        fig = ts.as_plotly_figure()
        global graph
        graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return render_template("index.html", stock=stk_name.upper(), symbol=stock,
                               graph=graph, userstock=stk_names, details=details,
                               stk_symbols=stk_symbols, zip=zip)
    except twelvedata.exceptions.TwelveDataError:
        print("Try again")
        return render_template("index.html", stock=stk_name.upper(), symbol=stock,
                               graph=graph, userstock=stk_names, details=details,
                               stk_symbols=stk_symbols, zip=zip)


@app.route('/view_genNews', methods=['GET', 'POST'])
def scrap_news():
    news_url = "https://www.bing.com/news/search?q=stock+news&FORM=HDRSC6"
    u_client = urlopen(news_url)  # requesting the webpage from the internet
    news_page = u_client.read()  # reading the webpage
    u_client.close()  # closing the connection to the web server
    news_html = bs(news_page, "html.parser")  # parsing the webpage as HTML
    big_boxes = news_html.findAll("div", {"class": "news-card newsitem cardcommon b_cards2"})
    image_urls = ["https://drive.google.com/uc?export=view&id=1lsgisum9wNDqDgVrPy3_GtsqQCWXzxfA",
                  "https://drive.google.com/uc?export=view&id=1m7imAoSXRMZ7od9hjJzWy3MUmXIqCDCz",
                  "https://drive.google.com/uc?export=view&id=1n5KvqRNqqcKU3lOoHsKB4Xl1RUoP3y8W",
                  "https://drive.google.com/uc?export=view&id=1n63y6qYzrNw-UJ33Y6WYST-uNR9-VMqw",
                  "https://drive.google.com/uc?export=view&id=1n5hH1WM9oj9xTRJ7HHI2PQImopGbdNM1",
                  "https://drive.google.com/uc?export=view&id=1n51b5l5I8E08hPjxPOGAgAexMrTR27Lk",
                  "https://drive.google.com/uc?export=view&id=1n47LNq3dOXGuECy66cN7c6Vnznc0Yopd",
                  "https://drive.google.com/uc?export=view&id=1mxQ1y6OgCucevF5Qq9kyLc0KRFSQsmVx",
                  "https://drive.google.com/uc?export=view&id=1mvs5a193fG8wUaaDHDvLS-czx5TOAqFn",
                  "https://drive.google.com/uc?export=view&id=1mrf9njqJaqTIE6a5NgwOqyZT_s0l1WKw",
                  "https://drive.google.com/uc?export=view&id=1mglL44rLmLul_h8hHdJr2rm3eptWt4_w",
                  "https://drive.google.com/uc?export=view&id=1mcSQVwAJp0d9lMON5fJxFf77n9-SLuu_",
                  "https://drive.google.com/uc?export=view&id=1mXkwNt37HTgnAogCbMmj1Y0wLwMhs9l0",
                  "https://drive.google.com/uc?export=view&id=1mV73MSb2dO22DVHqyA9xeyvBFc4go258",
                  "https://drive.google.com/uc?export=view&id=1mQ7QWeIc-gxc1K8prt_E_kj0MQpOp24q",
                  "https://drive.google.com/uc?export=view&id=1mP-IZdj30Keb34emPm_HuyvJxfeYuFsP",
                  "https://drive.google.com/uc?export=view&id=1m2YFd5D3dkgjgSDK0BYE71g71-sh6iMt"]
    news = []
    i = 0
    for box in big_boxes:

        """Headlines"""
        try:
            box1 = box.div.find_all('div', {'class': 'caption'})[0]
            headlines = box1.div.div.a.text
        except:
            headlines = "Click to view Detailed article"

        """News source"""
        try:
            box1 = box.div.find_all('div', {'class': 'source'})[0]
            news_source = box1.a.text
        except:
            news_source = "Unknown"

        """Content"""
        try:
            box1 = box.div.find_all('div', {'class': 'snippet'})[0]
            news_content = box1.text
        except:
            news_content = ""

        """News url"""
        try:
            news_source_url = box['url']
        except:
            news_source_url = ""

        image_url = image_urls[i]
        i = (i + 1) % len(image_urls)

        my_dict = {"headline": headlines, "content": news_content,
                   "news_source": news_source, "news_url": news_source_url, "image": image_url}

        news.append(my_dict)
    return render_template('news.html', news=news)


@app.route('/view_watchlist_news', methods=['GET', 'POST'])
def scrap_w_news():
    user = get_user()
    watchlist = user['watchlist']
    watch_list = []
    special_characters = ['!', '#', '$', '%', '&', '@', '[', ']', ']', '_', '-', ' ']
    for x in watchlist:
        x = x.split("#")[0]
        x = ''.join(filter(lambda j: j not in special_characters, x))
        watch_list.append(x)
    base_url = "https://www.bing.com/news/search?q="
    i = 0
    news = []
    image_urls = ["https://drive.google.com/uc?export=view&id=1lsgisum9wNDqDgVrPy3_GtsqQCWXzxfA",
                  "https://drive.google.com/uc?export=view&id=1m7imAoSXRMZ7od9hjJzWy3MUmXIqCDCz",
                  "https://drive.google.com/uc?export=view&id=1n5KvqRNqqcKU3lOoHsKB4Xl1RUoP3y8W",
                  "https://drive.google.com/uc?export=view&id=1n63y6qYzrNw-UJ33Y6WYST-uNR9-VMqw",
                  "https://drive.google.com/uc?export=view&id=1n5hH1WM9oj9xTRJ7HHI2PQImopGbdNM1",
                  "https://drive.google.com/uc?export=view&id=1n51b5l5I8E08hPjxPOGAgAexMrTR27Lk",
                  "https://drive.google.com/uc?export=view&id=1n47LNq3dOXGuECy66cN7c6Vnznc0Yopd",
                  "https://drive.google.com/uc?export=view&id=1mxQ1y6OgCucevF5Qq9kyLc0KRFSQsmVx",
                  "https://drive.google.com/uc?export=view&id=1mvs5a193fG8wUaaDHDvLS-czx5TOAqFn",
                  "https://drive.google.com/uc?export=view&id=1mrf9njqJaqTIE6a5NgwOqyZT_s0l1WKw",
                  "https://drive.google.com/uc?export=view&id=1mglL44rLmLul_h8hHdJr2rm3eptWt4_w",
                  "https://drive.google.com/uc?export=view&id=1mcSQVwAJp0d9lMON5fJxFf77n9-SLuu_",
                  "https://drive.google.com/uc?export=view&id=1mXkwNt37HTgnAogCbMmj1Y0wLwMhs9l0",
                  "https://drive.google.com/uc?export=view&id=1mV73MSb2dO22DVHqyA9xeyvBFc4go258",
                  "https://drive.google.com/uc?export=view&id=1mQ7QWeIc-gxc1K8prt_E_kj0MQpOp24q",
                  "https://drive.google.com/uc?export=view&id=1mP-IZdj30Keb34emPm_HuyvJxfeYuFsP",
                  "https://drive.google.com/uc?export=view&id=1m2YFd5D3dkgjgSDK0BYE71g71-sh6iMt"]

    for stocks in watch_list:
        news_url = base_url + stocks
        try:
            u_client = urlopen(news_url)  # requesting the webpage from the internet
            news_page = u_client.read()  # reading the webpage
            u_client.close()  # closing the connection to the web server
            news_html = bs(news_page, "html.parser")  # parsing the webpage as HTML
            big_boxes = news_html.findAll("div", {"class": "news-card newsitem cardcommon b_cards2"})
            for box in big_boxes:

                """Headlines"""
                try:
                    box1 = box.div.find_all('div', {'class': 'caption'})[0]
                    headlines = box1.div.div
                    headlines = headlines.find_all('a', {'target': '_blank'})
                    headlines = headlines.text
                    print(headlines)
                except:
                    headlines = "Click to view Detailed article"

                """News source"""
                try:
                    box1 = box.div.find_all('div', {'class': 'source'})[0]
                    news_source = box1.a.text
                except:
                    news_source = "Unknown"

                """Content"""
                try:
                    box1 = box.div.find_all('div', {'class': 'snippet'})[0]
                    news_content = box1.text
                except:
                    news_content = ""

                """News url"""
                try:
                    news_source_url = box['url']
                except:
                    news_source_url = ""

                image_url = image_urls[i]
                i = (i + 1) % len(image_urls)

                my_dict = {"headline": headlines, "content": news_content,
                           "news_source": news_source, "news_url": news_source_url, "image": image_url}

                news.append(my_dict)
        except:
            print("problem"+stocks)
            continue
    return render_template('news.html', news=news)


@app.route('/about', methods=['GET', 'POST'])
def about_page():
    return render_template("about.html")


@app.route('/prediction_page', methods=['GET', 'POST'])
def prediction_page():
    user = get_user()
    if not user['watchlist']:
        return render_template("notification1.html")
    return render_template("notification.html", watchlist=user['watchlist'])


@app.route('/predict', methods=['GET', 'POST'])
def predict_page():
    user = get_user()
    stock_name = request.form['Stock_Name']
    stock_code = stock_name.split("#")[1]
    os.environ["STOCK_CODE"] = stock_code
    df = pdr.get_data_tiingo(stock_code, api_key=TIINGO_KEY)
    df = df.reset_index()['close']
    df = df[1158:]
    scaler = MinMaxScaler(feature_range=(0, 1))
    df1 = scaler.fit_transform(np.array(df).reshape(-1, 1))
    x_test = np.array(df1)
    test_predict = model.predict(x_test)
    test_predict = scaler.inverse_transform(test_predict)
    res = "Tomorrow's closing price for "+stock_name+" is $"+str(test_predict[0][0])
    return render_template("notification.html", res=res, watchlist=user['watchlist'])


@app.route('/plot.png')
def plot_png():
    fig = create_figure()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


def create_figure():
    stock_code = os.environ.get("STOCK_CODE")
    df = pdr.get_data_tiingo(stock_code, api_key=TIINGO_KEY)
    df.reset_index(inplace=True)
    df = df[1158:]
    ndf1 = df[1:91]
    ndf2 = df[90:]
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis.plot(ndf1['date'], ndf1['close'], color='tab:blue')
    axis.plot(ndf2['date'], ndf2['close'], color='tab:orange')
    plt.xticks([])
    plt.xlabel('Date')
    return fig


def get_stock_details(symbol):
    collection = db["Stocks"]
    stock_detail = collection.find_one({"symbol": symbol})
    stock_detail.pop("_id")
    return stock_detail


def get_user():
    collection = db["Accounts"]
    # print(session['user'])
    user = collection.find_one({"Username": "Sai"})
    # print(user)
    return user
