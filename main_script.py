import requests
import json
from hashlib import sha256
import time
import gspread


# получение временного токена
def get_token():
    headers = {
        'Content-Type': "application/json",
        'Accept': "application/json"
    }

    timestamp = time.time()
    sign = sha256(('4D4FEE8E99C341CE9790AE405BF93629' + str(round(timestamp))).encode('utf-8')).hexdigest()

    token_json_request = {
        "seller_id": 479276,
        "timestamp": timestamp,
        "sign": sign
    }

    req = requests.post(url=f'https://api.digiseller.ru/api/apilogin', json=token_json_request, headers=headers)
    return json.loads(req.text).get('token')


# получение словаря с информацией по операциям
def get_operations_list(tk):
    headers = {
        'Accept': "application/json"
    }

    requests_list = []

    for i in range(1, 31):
        req = requests.get(
            url=f'https://api.digiseller.ru/api/sellers/account/receipts?token={tk}&page={i}&count=200&currency=WMZ&codeFilter=hide_waiting_code_check&allowType=exclude&start=2021-12-01T00:00:00.000&finish={time.strftime("%Y-%m-%d" + "T" + "%H:%M:%S" + ".000", time.gmtime())}',
            headers=headers
        )
        if not req:
            break
        else:
            requests_list.append(
                json.loads(req.text).get('content').get('items')
            )
    return requests_list


# получение словаря со статистикой по товарам
def get_statistics_list(tk):
    headers = {
        'Content-Type': "application/json",
        'Accept': "application/json"
    }

    statistics_list = []

    for i in range(3):
        statistics_json_request = {
            "token": tk,
            "date_start": "2017-01-01 00:00:00",
            "date_finish": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
            "returned": 0,
            "page": i,
            "rows": 2000
        }

        req = requests.post(url=f'https://api.digiseller.ru/api/seller-sells/v2?token={tk}',
                            json=statistics_json_request,
                            headers=headers)

        if req:
            statistics_list.append(json.loads(req.text).get('rows'))
        else:
            break

    return statistics_list


# плучение словаря с продуктами продавца
def get_products_list(tk):
    headers = {
        'Content-Type': "application/json",
        'Accept': "application/json"
    }

    products_json_request = {
        "id_seller": 479276,
        "order_col": "cntsell",
        "order_dir": "desc",
        "rows": 2000,
        "page": 1,
        "currency": "RUR",
        "lang": "ru-RU",
        "show_hidden": 1,
        "token": tk
    }

    req = requests.post(url=f'https://api.digiseller.ru/api/seller-goods?token={tk}', json=products_json_request,
                        headers=headers)

    return json.loads(req.text).get('rows')


# получение конечного списка с операциями
def get_operations_result_list(rows):
    result_list = []

    for row in rows:
        for item in row:
            operation = item.get('operation')
            result_list.append(
                {
                    'ID операции': operation.get('id'),
                    'Тип операции': operation.get('type'),
                    'ID товара': item.get('product').get('id') if item.get(
                        'product') is not None else '',
                    'Название': item.get('product').get('name')[0].get('value') if item.get(
                        'product') is not None else '',
                    'Дата': f"{operation.get('datetime').split('T')[0].split('-')[2]}.{operation.get('datetime').split('T')[0].split('-')[1]}.{operation.get('datetime').split('T')[0].split('-')[0]}",
                    'Время': operation.get('datetime').split('T')[1][:8],
                    'Сумма': operation.get('price'),
                    'Комиссия': f"{int(operation.get('percent'))}%",
                    'На баланс': operation.get('on_account')
                }
            )

    return result_list


# получение конечного списка со статистикой по каждому продукту
def get_result_statistics_list(rows):
    result_list = []

    curr_dict = {
        'WMZ': 'USD',
        'WMR': 'RUB',
        'WME': 'EUR',
        'WMU': 'UAH',
        'WML': 'LTC',
        'WMX': 'BTC'
    }

    for row in rows:
        for item in row:
            result_list.append(
                {
                    'ID товара': item.get('product_id'),
                    'Название': item.get('product_name'),
                    'Площадка': item.get('referer'),
                    'Дата': f"{item.get('date_pay').split()[0].split('-')[2]}.{item.get('date_pay').split()[0].split('-')[1]}.{item.get('date_pay').split()[0].split('-')[0]}",
                    'Время': item.get('date_pay').split()[1],
                    'Покупатель': item.get('email'),
                    'Способ оплаты': item.get('aggregator_pay'),
                    'Оплачено': item.get('amount_in'),
                    'Зачислено': item.get('amount_out'),
                    'Валюта': curr_dict[item.get('amount_currency')]
                }
            )

    return result_list


# получение нужнй информации по каждому продукту
def get_products_info(products_list):
    result = []
    for product in products_list:

        payment = 'OFF'
        if product.get('num_in_stock') and product.get('in_stock'):
            payment = 'ON'
        if product.get('num_in_stock') and not product.get('in_stock'):
            payment = 'ON(нет в наличии)'

        result.append(
            {
                'Оплата': payment,
                'ID товара': product.get('id_goods'),
                'Название товара': product.get('name_goods'),
                'Площадка': 'Plati.Market',
                'Цена': product.get('price_usd'),
                'Продано': product.get('cnt_sell'),
                'Содержимое': product.get('num_in_stock'),
            }
        )

    return result


# загрузка в products_info_sheet
def products_info_sheet():
    token = get_token()
    products = get_products_list(token)
    products_result_list = get_products_info(products)

    # загрузка информации в google sheets
    sa = gspread.service_account(filename='gspread/service_account.json')
    sh = sa.open('DiggisellerInfoBook')

    wks = sh.worksheet('Сводная')

    lst = [[product.get('Оплата'), product.get('ID товара'), product.get('Название товара'), product.get('Площадка'),
            product.get('Цена'), product.get('Продано'), product.get('Содержимое')] for product
           in products_result_list]

    wks.update(f'A2:G{len(lst) + 1}', lst)


# загрузка в statistics_sheet
def statistics_sheet():
    token = get_token()
    statistics_rows = get_statistics_list(token)
    result = get_result_statistics_list(statistics_rows)

    # запись данных в google sheets
    sa = gspread.service_account(filename='gspread/service_account.json')
    sh = sa.open('DiggisellerInfoBook')

    wks = sh.worksheet('Продажи')

    lst = [[product.get('ID товара'), product.get('Название'), product.get('Площадка'), product.get('Дата'),
            product.get('Время'), product.get('Покупатель'), product.get('Способ оплаты'), product.get('Оплачено'),
            product.get('Зачислено'), product.get('Валюта')] for product in result]

    wks.update(f'A2:J{len(lst) + 1}', lst[::-1])


# загрузка в operations_sheet
def operations_sheet():
    token = get_token()
    op_list = get_operations_list(token)
    result = get_operations_result_list(op_list)

    # запись данных в google sheets
    sa = gspread.service_account(filename='gspread/service_account.json')
    sh = sa.open('DiggisellerInfoBook')

    wks = sh.worksheet('Операции')

    lst = [[operation.get('ID операции'), operation.get('Тип операции'), operation.get('ID товара'), operation.get('Название'), operation.get('Дата'),
            operation.get('Время'), operation.get('Сумма'), operation.get('Комиссия'), operation.get('На баланс')]
           for operation in result]

    wks.update(f'A2:I{len(lst) + 1}', lst[1:])


def main():
    while True:
        products_info_sheet()
        statistics_sheet()
        operations_sheet()

        time.sleep(300)


if __name__ == '__main__':
    main()
