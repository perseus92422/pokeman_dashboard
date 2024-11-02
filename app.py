from flask import Flask, jsonify, render_template, request
from flask_mongoengine import MongoEngine
from flask_cors import CORS, cross_origin
from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import json
import requests

app = Flask(__name__,static_folder='public')
CORS(app)

# MongoDB configuration
app.config['MONGODB_SETTINGS'] = {
    'db': 'pokeman',
    'host': 'localhost',
    'port': 27017
}

db = MongoEngine()
db.init_app(app)

# Define a model
class Item(db.Document):
    condition = db.StringField(required=True)
    variant = db.StringField(required=True)
    language = db.StringField(required=True)
    quantity = db.FloatField(required=True)
    title = db.StringField(required=True)
    listingType = db.StringField(required=True)
    customListingId = db.StringField(required=True)
    purchasePrice = db.FloatField(required=True)
    shippingPrice = db.FloatField(required=True)
    orderDate = db.DateTimeField(required=True)
    productId = db.IntField(required=True)

    # Explicitly define the collection name
    meta = {
        'collection': 'sales_data'
    }

class Product(db.Document):
    productId = db.IntField(required=True)
    title = db.StringField(required=True)
    trending = db.DictField(required=True)
    buckets = db.StringField(required=True)
    skuId = db.StringField(required=True)
    listingType = db.StringField(required=True)
    totalQuantitySold = db.StringField(required=True)
    totalTransactionCount = db.StringField(required=True)
    averageDailyQuantitySold = db.StringField(required=True)
    averageDailyTransactionCount = db.StringField(required=True)
    dailyDrop = db.FloatField(required=False)
    lastPrice = db.FloatField(required=False)
    listingCount = db.StringField(required=False)


    # Explicitly define the collection name
    meta = {
        'collection': 'products'
    }

def get_unique_titles():
    pipeline = [
        {
            '$group': {
                '_id': '$title',  # Group by the 'title' field
                'totalQuantity': { '$sum': '$quantity' }  # Sum the 'quantity' field
            }
        },
        {
            '$sort': { 'totalQuantity': -1 }  # Optional: Sort by total quantity in descending order
        }
    ]
    result = list(Item.objects.aggregate(*pipeline))
    unique_titles = [f'{item["_id"]}___Qty : {item["totalQuantity"]}' for item in result]
    return unique_titles

def process_items(items_list,productId):
    # Dictionary to hold the aggregated results
    aggregated_data = defaultdict(lambda: {'totalQuantity': 0, 'totalPrice': 0, 'count': 0, 'title' : '', 'totalShippingPrice' : 0, 'listings' : []})
    now = datetime.now()
    today = now.date()
    # start_date = today - timedelta(days=period)

    productData = Product.objects(productId=productId).first().to_mongo().to_dict()
    listingCount = json.loads(productData['listingCount'])

    for item in items_list:
        # Parse the ISO 8601 date string
        order_date = item['orderDate'].date()  # Extract only the date part
        # if(order_date < start_date):
        #     continue
        quantity = item['quantity']
        price = item['purchasePrice']
        shippingPrice = item['shippingPrice']
        # Format date to exclude time component (using YYYY-MM-DD)
        date_str = order_date.strftime('%Y-%m-%d')
        
        # Update the dictionary with total quantity and total price
        aggregated_data[date_str]['title'] = item['title']
        aggregated_data[date_str]['totalQuantity'] += quantity
        aggregated_data[date_str]['totalPrice'] += price * quantity
        aggregated_data[date_str]['totalShippingPrice'] += shippingPrice * quantity
        aggregated_data[date_str]['count'] += 1

    # Calculate the average price per item per data
    result = []
    for date_str, data in aggregated_data.items():
        avg_price = data['totalPrice'] / data['totalQuantity'] if data['totalQuantity'] > 0 else 0
        avg_shipping = data['totalShippingPrice'] / data['totalQuantity'] if data['totalQuantity'] > 0 else 0
        listings = listingCount[date_str] if date_str in listingCount else 0
        result.append({
            'title' : data['title'],
            'orderDate': date_str,
            'quantity': data['totalQuantity'],
            'count' : data['count'],
            'purchasePrice': round(avg_price,6),
            'shippingPrice' : round(avg_shipping,6),
            'listings' : listings
        })

    # Optional: Sort by date
    result.sort(key=lambda x: datetime.strptime(x['orderDate'], '%Y-%m-%d'),reverse=True)

    return result

def getLatestSalesByID(product_id, offset,limit, mpfev = 2698):
    url = f"https://mpapi.tcgplayer.com/v2/product/{product_id}/latestsales?mpfev={mpfev}"
    timestamp_now = datetime.now().timestamp()

    payload = json.dumps({
        "conditions": [],
        "languages": [],
        "variants": [],
        "listingType": "All",
        "offset": offset,
        "limit": limit,
        "time": int(timestamp_now*1000)
    })
    headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    'origin': 'https://www.tcgplayer.com',
    'priority': 'u=1, i',
    'referer': 'https://www.tcgplayer.com/',
    'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return response.json()

@app.route('/', methods=['GET'])
def home():
    products = Product.objects()
    return render_template('dashboard.html', products=products)

@app.route('/details', methods=['GET'])
def details():
    productId = request.args.get('product')
    skuId = request.args.get('skuId')
    product = Product.objects(productId=productId,skuId=skuId).first().to_mongo().to_dict()
    return render_template('details.html',product=product)

# API route to get data for DataTable
@app.route('/api/getSalesData', methods=['GET','POST'])
@cross_origin()
def get_items():
    # server side processing
    # productId = request.args.get('productId')
    # skuId = request.args.get('skuId')
    # page = request.args.get('page')
    # page = int(page) if(page != 'NaN') else 1
    # today = datetime.now().date()
    # latest_order = Item.obejcts(productId=productId,orderDate__gte=today).order_by('-orderDate').first()
    # tableData = []
    # if(latest_order):
    #     sales_data = getLatestSalesByID(productId,0,24)
    #     sales_data = sales_data['data']
    #     new_data = [item for item in sales_data if item['orderDate'] > latest_order['orderDate']]
    #     if(len(new_data)> 0):
    #         data = []
    #         for item in new_data:
    #             item['productId'] = productId
    #             data.append(item)
    #         Item.objects.insert(data)
    #         tableData += new_data
    
    # tableData = Item.objecst(productId=productId)

    # chartData = process_items(tableData)

    # totalRecords = int(tableData['totalResults'])

    productId = request.args.get('productId')
    skuId = request.args.get('skuId')
    today = datetime.now().date()
    latest_order = Item.objects(productId=productId).order_by('-orderDate').first()
    tableData = []
    if(latest_order):
        sales_data = getLatestSalesByID(productId,0,24)
        sales_data = sales_data['data']
        new_data  =[]
        for item in sales_data:
            order_str = item['orderDate']
            if '.' in order_str:
                    # Format with fractional seconds
                order_date_dt = datetime.strptime(order_str, "%Y-%m-%dT%H:%M:%S.%f+00:00")
            else:
                # Format without fractional seconds
                order_date_dt = datetime.strptime(order_str, "%Y-%m-%dT%H:%M:%S+00:00")
            if(order_date_dt > latest_order['orderDate']):
                item['productId'] = productId
                new_item = Item(
                    condition= item['condition'],
                    variant = item['variant'],
                    language = item['language'],
                    quantity = item['quantity'],
                    title = item['title'],
                    listingType = item['listingType'],
                    customListingId = item['customListingId'],
                    purchasePrice = item['purchasePrice'],
                    shippingPrice = item['shippingPrice'],
                    orderDate = order_date_dt,
                    productId = productId,
                )
                new_data.append(new_item)
        if(len(new_data)> 0):
            Item.objects.insert(new_data)
    
    tableData = Item.objects(productId=productId)

    chartData = process_items(tableData,productId)

    

    return jsonify({"tableData" : tableData, "chartData" : chartData})

def process_cards(todayData, thirtyData):
    cards = []
    for card in todayData:
        thirty_cards = [item for item in thirtyData if item['title'] == card['title']]
        if(len(thirty_cards) > 0):
            currentPrice = card['totalPrice']/card['totalQuantity'] if card['totalQuantity'] !=0 else card['totalPrice']
            thirty_card = thirty_cards[0]
            previousPrice = thirty_card['totalPrice']/thirty_card['totalQuantity'] if thirty_card['totalQuantity'] !=0 else thirty_card['totalPrice']
            drop = round((currentPrice-previousPrice)/previousPrice*100,2) if previousPrice != 0 else -101
            data = {
                'title' : card['title'],
                'currentPrice' : currentPrice,
                'previousPrice' : previousPrice,
                'drop' : drop
            }
            cards.append(data)
    cards = sorted(cards,key=lambda x: x['drop'],reverse=True)
    return cards
            


@app.route('/api/products', methods=['GET'])
def get_cards():
    result = Product.objects()
    cards = []
    for doc in result:
        bucket = json.loads(doc['buckets'])
        price = bucket[0]['marketPrice']
        if('lastPrice' in doc):
            price = doc['lastPrice']
        cards.append({
            'title' : doc['title'],
            'productId' : doc['productId'],
            '1day' : float(doc['dailyDrop']) if 'dailyDrop' in doc else 0,
            '7day' : float(doc['trending']['sevenDay']) if 'sevenDay' in doc['trending'] else 0,
            '30day' : float(doc['trending']['thirtyDay']) if 'thirtyDay' in doc['trending'] else 0,
            '60day' : float(doc['trending']['sixtyDay']) if 'sixtyDay' in doc['trending'] else 0,
            '90day' : float(doc['trending']['ninetyDay']) if 'ninetyDay' in doc['trending'] else 0,
            'price' : price,
            'totalQty' : float(doc['totalQuantitySold']),
            'totalTx' : float(doc['totalTransactionCount']),
            'avgQty' : float(doc['averageDailyQuantitySold']),
            'avgTx' : float(doc['averageDailyTransactionCount']),
            'skuId' : doc['skuId']
        })
    return jsonify(cards)

# API route to get chart data
@app.route('/api/chart-data', methods=['GET'])
def get_chart_data():
    items = Item.objects()  # Fetch the data from MongoDB
    labels = [item.name for item in items]
    prices = [item.price for item in items]
    
    # Return data in the format Chart.js expects
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Item Prices',
            'data': prices,
            'backgroundColor': 'rgba(75, 192, 192, 0.2)',
            'borderColor': 'rgba(75, 192, 192, 1)',
            'borderWidth': 1
        }]
    }
    return jsonify(chart_data)

if __name__ == '__main__':
    app.run(debug=True)

